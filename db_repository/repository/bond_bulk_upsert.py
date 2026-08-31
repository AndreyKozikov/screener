"""Оптимизированный модуль bulk upsert облигаций (data-driven подход).

Содержит класс BondBulkUpsert — замену группы методов
bonds_data_update / _create_temp_tables / _insert_temp_data /
_bulk_insert / _upsert_bonds / _upsert_related
из bond_repository.py.

Вся конфигурация таблиц вынесена в _RELATED_TABLES, что устраняет
дублирование SQL-шаблонов и упрощает добавление новых связанных таблиц.
"""

from typing import Any, Dict, List, Sequence

from sqlalchemy import text
from sqlmodel import Session

from db_repository.core.database_init import get_session
from db_repository.models.bond import (
    Bond,
    BondMarketData,
    BondMarketDataYield,
    BondSecurity,
)


class BondBulkUpsert:
    """Bulk upsert облигаций и связанных таблиц через временные таблицы.

    Паттерн:
        1. CREATE TEMP TABLE … AS SELECT * FROM <target> WHERE 0
        2. Bulk INSERT во временные таблицы
        3. INSERT … ON CONFLICT DO UPDATE из временных в целевые

    Конфигурация связанных таблиц задаётся в _RELATED_TABLES —
    для добавления новой связанной таблицы достаточно добавить запись.
    """

    # ------------------------------------------------------------------
    # Конфигурация: связанные с bonds таблицы (one-to-one по bond_id)
    # ------------------------------------------------------------------
    _RELATED_TABLES: List[Dict[str, Any]] = [
        {
            "temp_table": "tmp_bondsecurity",
            "target_table": "bondsecurity",
            "model": BondSecurity,
            "data_key": "securities",
        },
        {
            "temp_table": "tmp_bondmarketdata",
            "target_table": "bondmarketdata",
            "model": BondMarketData,
            "data_key": "marketdata",
        },
        {
            "temp_table": "tmp_bondmarketdatayield",
            "target_table": "bondmarketdatayield",
            "model": BondMarketDataYield,
            "data_key": "marketdata_yields",
        },
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bonds_data_update(
        self,
        data: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """Массовое обновление (upsert) облигаций и связанных таблиц.

        Все операции выполняются в одной транзакции.
        При ошибке — автоматический rollback.

        Args:
            data: Словарь с ключами ``"bonds"``, ``"securities"``,
                  ``"marketdata"``, ``"marketdata_yields"``.
                  Каждое значение — список словарей (строк для вставки).
        """
        with get_session() as session:
            self._create_temp_tables(session)
            self._insert_all_temp_data(session, data)
            self._upsert_bonds(session)

            for cfg in self._RELATED_TABLES:
                self._upsert_related(
                    session,
                    temp_table=cfg["temp_table"],
                    target_table=cfg["target_table"],
                    model=cfg["model"],
                )

            session.commit()


    # ------------------------------------------------------------------
    # Temp tables
    # ------------------------------------------------------------------

    def _create_temp_tables(self, session: Session) -> None:
        """Создаёт временные таблицы для bonds и всех связанных таблиц.

        Структура каждой temp-таблицы клонируется из целевой
        (``SELECT * … WHERE 0``).  Для связанных таблиц дополнительно
        добавляется колонка ``secid`` — она нужна для JOIN при upsert.
        """
        # bonds — без дополнительной колонки secid
        session.exec(text(
            "CREATE TEMP TABLE tmp_bonds AS "
            "SELECT * FROM bonds WHERE 0"
        ))

        # Связанные таблицы — с колонкой secid
        for cfg in self._RELATED_TABLES:
            session.exec(text(
                f"CREATE TEMP TABLE {cfg['temp_table']} AS "
                f"SELECT * FROM {cfg['target_table']} WHERE 0"
            ))
            session.exec(text(
                f"ALTER TABLE {cfg['temp_table']} ADD COLUMN secid TEXT"
            ))

    # ------------------------------------------------------------------
    # Bulk insert
    # ------------------------------------------------------------------

    def _insert_all_temp_data(
        self,
        session: Session,
        data: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """Вставляет данные во все временные таблицы.

        Args:
            session: Активная SQLAlchemy-сессия.
            data: Данные для вставки (см. ``bonds_data_update``).
        """
        self._bulk_insert(session, "tmp_bonds", data["bonds"])

        for cfg in self._RELATED_TABLES:
            self._bulk_insert(
                session,
                cfg["temp_table"],
                data[cfg["data_key"]],
            )

    @staticmethod
    def _bulk_insert(
        session: Session,
        table_name: str,
        rows: List[Dict[str, Any]],
    ) -> None:
        """Массовая вставка строк в таблицу через executemany.

        Args:
            session: Активная SQLAlchemy-сессия.
            table_name: Имя целевой (временной) таблицы.
            rows: Список словарей — строк для вставки.
                  Ключи первого элемента определяют набор колонок.
        """
        if not rows:
            return

        columns: Sequence[str] = list(rows[0].keys())

        column_names = ", ".join(f'"{col}"' for col in columns)
        placeholders = ", ".join(f":{col}" for col in columns)

        session.execute(
            text(
                f'INSERT INTO "{table_name}" ({column_names}) '
                f"VALUES ({placeholders})"
            ),
            rows,
        )

    # ------------------------------------------------------------------
    # Upsert: bonds
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_bonds(session: Session) -> None:
        """INSERT … ON CONFLICT (secid, boardid) DO UPDATE для таблицы bonds.

        Колонки берутся из метаданных модели Bond, исключая ``id``
        (autoincrement PK) и conflict-ключи ``secid``, ``boardid``.
        """
        columns = [
            col.name
            for col in Bond.__table__.columns
            if col.name != "id"
        ]

        column_names = ", ".join(columns)

        update_set = ", ".join(
            f"{col} = excluded.{col}"
            for col in columns
            if col not in {"secid", "boardid"}
        )

        session.exec(text(f"""
            INSERT INTO bonds ({column_names})
            SELECT {column_names}
            FROM tmp_bonds
            ON CONFLICT (secid, boardid)
            DO UPDATE SET {update_set}
        """))

    # ------------------------------------------------------------------
    # Upsert: related (universal)
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_related(
        session: Session,
        temp_table: str,
        target_table: str,
        model: Any,
    ) -> None:
        """Универсальный INSERT … ON CONFLICT (bond_id) DO UPDATE.

        Связывает записи из временной таблицы с ``bonds`` через
        JOIN по ``secid + boardid`` для получения ``bond_id``.

        Args:
            session: Активная SQLAlchemy-сессия.
            temp_table: Имя временной таблицы (с колонкой ``secid``).
            target_table: Имя целевой таблицы в БД.
            model: SQLModel-класс целевой таблицы (для получения колонок).
        """
        columns = [
            col.name
            for col in model.__table__.columns
            if col.name not in {"id", "bond_id"}
        ]

        target_columns = ", ".join(["bond_id", *columns])
        select_columns = ", ".join(["b.id", *(f"t.{col}" for col in columns)])
        update_set = ", ".join(f"{col} = excluded.{col}" for col in columns)

        session.exec(text(f"""
            INSERT INTO {target_table} ({target_columns})
            SELECT {select_columns}
            FROM {temp_table} AS t
            JOIN bonds AS b
              ON b.secid = t.secid
             AND b.boardid = t.boardid
            ON CONFLICT (bond_id)
            DO UPDATE SET {update_set}
        """))
