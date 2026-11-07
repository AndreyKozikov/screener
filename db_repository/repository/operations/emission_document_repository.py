"""Репозиторий для таблицы emission_documents.

Содержит только операции доступа к БД: пакетная вставка эмиссионных
документов и удаление записей по emitent_edisclosure_id.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from db_repository.config.paths import DB_PATH


# Невидимые символы, которые могут попасть в значения из HTML e-disclosure.
_INVISIBLE_CHARS: Tuple[str, ...] = (
    "\u00ad",  # soft hyphen
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\ufeff",  # BOM
    "\u2060",  # word joiner
)

# Разные виды дефисов/минусов, встречающиеся в регномерах.
_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\ufe58": "-",  # small em dash
    "\ufe63": "-",  # small hyphen-minus
    "\uff0d": "-",  # fullwidth hyphen-minus
})

# Кириллические буквы, визуально совпадающие с латинскими, в регномерах.
_CYRILLIC_TO_LATIN = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m",
    "н": "h", "о": "o", "р": "p", "с": "c", "т": "t", "х": "x",
})


def _strip_invisible(value: Any) -> str:
    """Убирает невидимые символы и заменяет NBSP обычным пробелом."""
    s = str(value or "")
    for ch in _INVISIBLE_CHARS:
        s = s.replace(ch, "")
    return s.replace("\u00a0", " ")


def normalize_inn(value: Any) -> str:
    """Нормализует ИНН: убирает невидимые символы и пробелы."""
    return re.sub(r"\s+", "", _strip_invisible(value))


def normalize_reg_number(value: Any) -> str:
    """Нормализует регномер для устойчивого сравнения.

    Убирает невидимые символы и пробелы, унифицирует дефисы и
    кириллические буквы, приводит к верхнему регистру.
    """
    s = _strip_invisible(value).translate(_DASH_TRANSLATION).translate(_CYRILLIC_TO_LATIN)
    s = re.sub(r"\s+", "", s)
    return s.upper()


class EmissionDocumentRepository:
    """CRUD-операции с таблицей emission_documents.

    Бизнес-логика (парсинг HTML, HTTP-запросы) выполняется в сервисном слое.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = DB_PATH
        self.db_path: Path = Path(db_path)
        self._engine: Engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger: logging.Logger = logging.getLogger(__name__)

    def insert_batch(
        self,
        emitent_edisclosure_id: int,
        documents: List[Dict[str, Optional[Union[str, int]]]],
    ) -> int:
        """Вставляет список эмиссионных документов для одного эмитента.

        Перед вставкой удаляет существующие записи для данного
        emitent_edisclosure_id (полная перезапись).

        Args:
            emitent_edisclosure_id: FK на emitent_edisclosure.id.
            documents: Список словарей с ключами doc_type, reg_number,
                date_registration, registering_org, date_ground_publication,
                date_placement, file_url.

        Returns:
            Количество вставленных записей.
        """
        if not documents:
            return 0

        delete_stmt = text(
            "DELETE FROM emission_documents "
            "WHERE emitent_edisclosure_id = :eid"
        )
        insert_stmt = text(
            "INSERT INTO emission_documents ("
            "  emitent_edisclosure_id, doc_type, reg_number,"
            "  date_registration, registering_org,"
            "  date_ground_publication, date_placement, file_url"
            ") VALUES ("
            "  :emitent_edisclosure_id, :doc_type, :reg_number,"
            "  :date_registration, :registering_org,"
            "  :date_ground_publication, :date_placement, :file_url"
            ")"
        )

        inserted: int = 0
        with Session(self._engine) as session:
            session.execute(delete_stmt, {"eid": emitent_edisclosure_id})

            for doc in documents:
                session.execute(insert_stmt, {
                    "emitent_edisclosure_id": emitent_edisclosure_id,
                    "doc_type": doc.get("doc_type") or "",
                    "reg_number": doc.get("reg_number"),
                    "date_registration": doc.get("date_registration"),
                    "registering_org": doc.get("registering_org"),
                    "date_ground_publication": doc.get("date_ground_publication"),
                    "date_placement": doc.get("date_placement"),
                    "file_url": doc.get("file_url"),
                })
                inserted += 1

            session.commit()

        return inserted

    def get_by_inn_and_reg_number(
        self,
        inn: str,
        reg_number: str,
        diagnose_other_issuers: bool = True,
    ) -> List[Dict[str, Any]]:
        """Возвращает записи emission_documents по ИНН эмитента и рег. номеру облигации.

        Сначала выполняется точное сравнение (быстрый путь), затем — сравнение
        после нормализации регномера (невидимые символы, разные дефисы,
        кириллические/латинские буквы, пробелы, регистр).

        Связь: emitents.inn -> emitent_edisclosure -> emission_documents.reg_number.
        Возвращаются только записи с непустым file_url, отсортированные по
        date_registration DESC (новые первыми).

        Args:
            inn: ИНН эмитента.
            reg_number: Регистрационный номер облигации.
            diagnose_other_issuers: Выполнять дорогой диагностический поиск
                того же регномера у других ИНН (для одиночных запросов; в
                пакетном режиме отключается, чтобы не сканировать таблицу
                для каждой облигации без документов).

        Returns:
            Список словарей с ключами id, file_url и date_registration.

        Raises:
            Exception: ошибки БД не проглатываются, чтобы не выглядеть как
                «документов нет».
        """
        if not inn or not str(inn).strip() or not reg_number or not str(reg_number).strip():
            return []
        inn_trimmed: str = normalize_inn(inn)
        reg_trimmed: str = normalize_reg_number(reg_number)
        if not inn_trimmed or not reg_trimmed:
            return []

        # INN сравниваем с удалением пробелов/NBSP/мягких переносов, чтобы
        # грязные значения в БД не мешали найти документы эмитента.
        inn_sql = (
            "REPLACE(REPLACE(REPLACE(TRIM(e.inn), ' ', ''), CHAR(160), ''), CHAR(173), '')"
        )
        exact_query = text(
            "SELECT ed.id, ed.file_url, ed.date_registration "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            f"WHERE {inn_sql} = :inn AND trim(ed.reg_number) = :reg_number "
            "AND ed.file_url IS NOT NULL AND trim(ed.file_url) != '' "
            "ORDER BY ed.date_registration DESC"
        )
        fallback_query = text(
            "SELECT ed.id, ed.file_url, ed.date_registration, ed.reg_number "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            f"WHERE {inn_sql} = :inn "
            "ORDER BY ed.date_registration DESC"
        )

        try:
            with Session(self._engine) as session:
                exact_rows = session.execute(
                    exact_query,
                    {"inn": inn_trimmed, "reg_number": str(reg_number).strip()},
                ).fetchall()
                if exact_rows:
                    return self._rows_to_documents(exact_rows)

                fallback_rows = session.execute(
                    fallback_query,
                    {"inn": inn_trimmed},
                ).fetchall()
        except Exception:
            self.logger.exception(
                "Ошибка при получении документов по ИНН и рег.номеру: inn=%r, reg_number=%r",
                inn,
                reg_number,
            )
            raise

        if not fallback_rows:
            other_mappings = (
                self._find_docs_under_other_inns(inn_trimmed, reg_trimmed)
                if diagnose_other_issuers
                else []
            )
            if other_mappings:
                self.logger.warning(
                    "У ИНН %s нет документов, но регномер %r найден у другого ИНН: %r. "
                    "Похоже на неверный mapping в emitent_edisclosure (чужой edisclosure_id).",
                    inn_trimmed,
                    str(reg_number).strip(),
                    other_mappings,
                )
            else:
                self.logger.warning(
                    "В emission_documents нет ни одной строки для ИНН %s. "
                    "Метаданные документов эмитента не загружены, либо страница e-disclosure "
                    "была пустой/заблокирована антибот-защитой.",
                    inn_trimmed,
                )
            return []

        matching_rows = [
            row for row in fallback_rows if normalize_reg_number(row[3]) == reg_trimmed
        ]
        if not matching_rows:
            other_mappings = (
                self._find_docs_under_other_inns(inn_trimmed, reg_trimmed)
                if diagnose_other_issuers
                else []
            )
            if other_mappings:
                self.logger.warning(
                    "У ИНН %s есть документы (%d строк), но регномер %r не найден. "
                    "При этом тот же регномер найден у другого ИНН: %r. "
                    "Похоже на неверный mapping в emitent_edisclosure.",
                    inn_trimmed,
                    len(fallback_rows),
                    str(reg_number).strip(),
                    other_mappings,
                )
            else:
                stored_samples = sorted({str(row[3]) for row in fallback_rows if row[3]})[:10]
                self.logger.warning(
                    "Документы эмитента (ИНН %s) есть (%d строк), но регномер %r не найден "
                    "даже после нормализации. Примеры сохранённых регномеров: %r",
                    inn_trimmed,
                    len(fallback_rows),
                    str(reg_number).strip(),
                    stored_samples,
                )
            return []

        downloadable_rows = [
            row for row in matching_rows if row[1] and str(row[1]).strip()
        ]
        if not downloadable_rows:
            self.logger.warning(
                "Для ИНН %s и регномера %r найдено %d строк(и) emission_documents, "
                "но у всех пустой file_url — скачивать нечего "
                "(на странице e-disclosure нет ссылки на файл).",
                inn_trimmed,
                str(reg_number).strip(),
                len(matching_rows),
            )
            return []
        if len(downloadable_rows) != len(matching_rows):
            self.logger.info(
                "Для ИНН %s и регномера %r: %d строк(и) без file_url отфильтрованы.",
                inn_trimmed,
                str(reg_number).strip(),
                len(matching_rows) - len(downloadable_rows),
            )

        self.logger.warning(
            "Точное совпадение регномера не найдено для ИНН %s: запрошен %r, "
            "после нормализации совпало %d строк (пример сохранённого значения: %r). "
            "Сработал нормализованный поиск.",
            inn_trimmed,
            str(reg_number).strip(),
            len(downloadable_rows),
            downloadable_rows[0][3],
        )
        return self._rows_to_documents(downloadable_rows)

    def _find_docs_under_other_inns(
        self,
        current_inn: str,
        reg_trimmed: str,
    ) -> List[Dict[str, Any]]:
        """Ищет тот же регномер у других ИНН — диагностика неверного маппинга.

        Если документы по регномеру есть, но привязаны к другому ИНН, значит
        в emitent_edisclosure, скорее всего, записан чужой edisclosure_id.
        Метод ничего не меняет, только возвращает найденные совпадения для лога.
        """
        digit_groups = re.findall(r"\d+", reg_trimmed)
        if len(digit_groups) < 2:
            return []
        pattern = f"%{digit_groups[-2]}%{digit_groups[-1]}%"
        query = text(
            "SELECT e.id, e.inn, ed.reg_number, ed.file_url "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            "WHERE ed.reg_number LIKE :pattern "
            "LIMIT 200"
        )
        try:
            with Session(self._engine) as session:
                rows = session.execute(query, {"pattern": pattern}).fetchall()
        except Exception:
            self.logger.exception(
                "Не удалось выполнить диагностический поиск регномера %r",
                reg_trimmed,
            )
            return []

        found: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str]] = set()
        for row in rows:
            other_inn = normalize_inn(row[1])
            if other_inn == current_inn:
                continue
            if normalize_reg_number(row[2]) != reg_trimmed:
                continue
            key = (other_inn, str(row[2]))
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "emitent_id": int(row[0]),
                "inn": other_inn,
                "reg_number": str(row[2]),
                "file_url": str(row[3]) if row[3] else "",
            })
        return found

    @staticmethod
    def _rows_to_documents(rows: List[Any]) -> List[Dict[str, Any]]:
        """Приводит строки SQL-запроса к словарям документов."""
        return [
            {
                "id": int(row[0]),
                "file_url": str(row[1]).strip() if row[1] else "",
                "date_registration": str(row[2]) if row[2] else None,
            }
            for row in rows
            if row[0] is not None and row[1]
        ]

    def get_all_documents_by_metadata(self) -> List[Tuple[str, str, List[str]]]:
        """Возвращает список кортежей (inn, reg_number, file_urls) для всех документов.

        Выбираются только записи с непустым file_url.
        """
        query = text(
            "SELECT trim(e.inn), trim(ed.reg_number), ed.file_url "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            "WHERE ed.file_url IS NOT NULL AND trim(ed.file_url) != ''"
        )
        result_map: Dict[Tuple[str, str], List[str]] = {}
        try:
            with Session(self._engine) as session:
                rows = session.execute(query).fetchall()
            for row in rows:
                if row[0] and row[1] and row[2]:
                    key = (str(row[0]).strip(), str(row[1]).strip())
                    url = str(row[2]).strip()
                    result_map.setdefault(key, []).append(url)
            return [(k[0], k[1], urls) for k, urls in result_map.items()]
        except Exception:
            self.logger.exception("Failed to fetch all documents by metadata")
            raise


