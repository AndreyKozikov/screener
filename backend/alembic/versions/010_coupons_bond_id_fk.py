"""Coupons: replace secid with bond_id FK.

Revision ID: 010
Revises: 009
Create Date: 2026-02-07

Удаление колонки secid из coupons, добавление bond_id (INTEGER) с FK на bonds.id.
Составной PK (bond_id, coupondate). Миграция данных: связь по bonds.secid = coupons.secid.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _coupons_has_column(conn, column_name: str) -> bool:
    """Проверяет наличие колонки в таблице coupons через PRAGMA table_info."""
    rp = conn.execute(sa.text("PRAGMA table_info(coupons)"))
    for row in rp:
        if row[1] == column_name:  # row[1] is name
            return True
    return False


def upgrade() -> None:
    """Заменяет secid на bond_id с FK, сохраняя данные через JOIN с bonds."""
    conn = op.get_bind()

    rp = conn.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'"
    ))
    table_exists = rp.fetchone() is not None

    if table_exists:
        has_bond_id = _coupons_has_column(conn, "bond_id")
        has_secid = _coupons_has_column(conn, "secid")
        if has_bond_id and not has_secid:
            # Таблица уже в новой схеме (bond_id), перенос не нужен
            pass
        elif has_secid:
            # Старая схема (secid): преобразование в новую. SQLite не позволяет сменить PK
            # и удалить колонку одним ALTER — создаём таблицу с целевой схемой под
            # внутренним именем, переносим данные, удаляем старую, переименовываем.
            _tmp = "_alembic_010_coupons"
            op.create_table(
                _tmp,
                sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id", ondelete="CASCADE"), nullable=False),
                sa.Column("coupondate", sa.Date(), nullable=True),
                sa.Column("recorddate", sa.Date(), nullable=True),
                sa.Column("startdate", sa.Date(), nullable=True),
                sa.Column("initialfacevalue", sa.Integer(), nullable=True),
                sa.Column("facevalue", sa.Integer(), nullable=True),
                sa.Column("faceunit", sa.Text(), nullable=True),
                sa.Column("value", sa.REAL(), nullable=True),
                sa.Column("valueprc", sa.REAL(), nullable=True),
                sa.Column("value_rub", sa.REAL(), nullable=True),
                sa.PrimaryKeyConstraint("bond_id", "coupondate", name="pk_coupons"),
            )
            conn.execute(sa.text(f"""
                INSERT INTO {_tmp} (
                    bond_id, coupondate, recorddate, startdate,
                    initialfacevalue, facevalue, faceunit, value, valueprc, value_rub
                )
                SELECT
                    b.id, c.coupondate, c.recorddate, c.startdate,
                    c.initialfacevalue, c.facevalue, c.faceunit, c.value, c.valueprc, c.value_rub
                FROM coupons c
                INNER JOIN bonds b ON b.secid = c.secid
            """))
            op.drop_table("coupons")
            op.rename_table(_tmp, "coupons")
        else:
            # Неожиданная схема — считаем, что нужно пересоздать (нет ни bond_id, ни secid)
            op.drop_table("coupons")
            op.create_table(
                "coupons",
                sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id", ondelete="CASCADE"), nullable=False),
                sa.Column("coupondate", sa.Date(), nullable=True),
                sa.Column("recorddate", sa.Date(), nullable=True),
                sa.Column("startdate", sa.Date(), nullable=True),
                sa.Column("initialfacevalue", sa.Integer(), nullable=True),
                sa.Column("facevalue", sa.Integer(), nullable=True),
                sa.Column("faceunit", sa.Text(), nullable=True),
                sa.Column("value", sa.REAL(), nullable=True),
                sa.Column("valueprc", sa.REAL(), nullable=True),
                sa.Column("value_rub", sa.REAL(), nullable=True),
                sa.PrimaryKeyConstraint("bond_id", "coupondate", name="pk_coupons"),
            )
    else:
        op.create_table(
            "coupons",
            sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("coupondate", sa.Date(), nullable=True),
            sa.Column("recorddate", sa.Date(), nullable=True),
            sa.Column("startdate", sa.Date(), nullable=True),
            sa.Column("initialfacevalue", sa.Integer(), nullable=True),
            sa.Column("facevalue", sa.Integer(), nullable=True),
            sa.Column("faceunit", sa.Text(), nullable=True),
            sa.Column("value", sa.REAL(), nullable=True),
            sa.Column("valueprc", sa.REAL(), nullable=True),
            sa.Column("value_rub", sa.REAL(), nullable=True),
            sa.PrimaryKeyConstraint("bond_id", "coupondate", name="pk_coupons"),
        )

    # Индекс создаём только если его ещё нет (idempotent: SQLite создаёт с IF NOT EXISTS нет, проверяем через sqlite_master)
    rp_idx = conn.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_coupons_bond_id'"
    ))
    if rp_idx.fetchone() is None:
        op.create_index(
            "idx_coupons_bond_id",
            "coupons",
            ["bond_id"],
            unique=False,
        )


def downgrade() -> None:
    """Восстанавливает таблицу coupons с колонкой secid."""
    conn = op.get_bind()

    op.create_table(
        "coupons_old",
        sa.Column("secid", sa.Text(), nullable=False),
        sa.Column("coupondate", sa.Date(), nullable=True),
        sa.Column("recorddate", sa.Date(), nullable=True),
        sa.Column("startdate", sa.Date(), nullable=True),
        sa.Column("initialfacevalue", sa.Integer(), nullable=True),
        sa.Column("facevalue", sa.Integer(), nullable=True),
        sa.Column("faceunit", sa.Text(), nullable=True),
        sa.Column("value", sa.REAL(), nullable=True),
        sa.Column("valueprc", sa.REAL(), nullable=True),
        sa.Column("value_rub", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("secid", "coupondate", name="pk_coupons_old"),
    )

    conn.execute(sa.text("""
        INSERT INTO coupons_old (
            secid, coupondate, recorddate, startdate,
            initialfacevalue, facevalue, faceunit, value, valueprc, value_rub
        )
        SELECT
            b.secid, c.coupondate, c.recorddate, c.startdate,
            c.initialfacevalue, c.facevalue, c.faceunit, c.value, c.valueprc, c.value_rub
        FROM coupons c
        INNER JOIN bonds b ON b.id = c.bond_id
    """))

    # Индекс может отсутствовать, если upgrade попал в ветку "уже новая схема"
    rp_idx = conn.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_coupons_bond_id'"
    ))
    if rp_idx.fetchone() is not None:
        op.drop_index("idx_coupons_bond_id", table_name="coupons")
    op.drop_table("coupons")
    op.rename_table("coupons_old", "coupons")
