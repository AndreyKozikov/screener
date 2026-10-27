"""Add UNIQUE(secid, boardid), emitent_id and index on emitent_id to bonds.

Revision ID: 007
Revises: 006
Create Date: 2026-02-07

Изменения:
- Добавлено UNIQUE(secid, boardid) для стабильности id при INSERT ON CONFLICT DO UPDATE
- Добавлена колонка emitent_id (INTEGER)
- Создан индекс CREATE INDEX ix_bonds_emitent_id ON bonds(emitent_id)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет UNIQUE(secid, boardid), колонку emitent_id и индекс."""
    # SQLite не поддерживает ALTER TABLE ADD CONSTRAINT для UNIQUE.
    # Пересоздаём таблицу bonds с новой схемой.

    # 1. Удаляем дочерние таблицы (зависят от bonds)
    op.drop_table("bondmarketdatayield")
    op.drop_table("bondmarketdata")
    op.drop_table("bondsecurity")

    # 2. Создаём временную таблицу bonds_new с UNIQUE(secid, boardid) и emitent_id
    op.create_table(
        "bonds_new",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("secid", sa.String(length=64), nullable=False),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("isin", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("secname", sa.String(), nullable=True),
        sa.Column("rating", sa.String(length=32), nullable=True),
        sa.Column("rating_agency", sa.String(length=64), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("coupon_yield_to_price", sa.Float(), nullable=True),
        sa.Column("yield_to_maturity", sa.Float(), nullable=True),
        sa.Column("face_value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("face_unit", sa.String(length=16), nullable=True),
        sa.Column("coupon_value", sa.Float(), nullable=True),
        sa.Column("coupon_percent", sa.Float(), nullable=True),
        sa.Column("coupon_frequency", sa.Float(), nullable=True),
        sa.Column("coupon_period", sa.Integer(), nullable=True),
        sa.Column("accrued_interest", sa.Float(), nullable=True),
        sa.Column("duration_years", sa.Float(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("duration_waprice", sa.Integer(), nullable=True),
        sa.Column("has_put_option", sa.Integer(), nullable=True),
        sa.Column("has_call_option", sa.Integer(), nullable=True),
        sa.Column("maturity_date", sa.String(length=10), nullable=True),
        sa.Column("listing_level", sa.Integer(), nullable=True),
        sa.Column("bond_type", sa.Integer(), nullable=True),
        sa.Column("bond_kind", sa.Integer(), nullable=True),
        sa.Column("offer_date", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("trading_status", sa.String(length=32), nullable=True),
        sa.Column("next_coupon", sa.String(length=10), nullable=True),
        sa.Column("board_name", sa.String(length=128), nullable=True),
        sa.Column("call_option_date", sa.String(length=10), nullable=True),
        sa.Column("put_option_date", sa.String(length=10), nullable=True),
        sa.Column("emitent_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("secid", "boardid", name="uq_bonds_secid_boardid"),
    )

    # 3. Копируем данные из bonds в bonds_new (emitent_id = NULL)
    op.execute(
        sa.text("""
            INSERT INTO bonds_new (
                id, secid, boardid, isin, name, secname, rating, rating_agency,
                current_price, coupon_yield_to_price, yield_to_maturity, face_value,
                currency, face_unit, coupon_value, coupon_percent, coupon_frequency,
                coupon_period, accrued_interest, duration_years, duration, duration_waprice,
                has_put_option, has_call_option, maturity_date, listing_level,
                bond_type, bond_kind, offer_date, status, trading_status, next_coupon,
                board_name, call_option_date, put_option_date, emitent_id
            )
            SELECT
                id, secid, boardid, isin, name, secname, rating, rating_agency,
                current_price, coupon_yield_to_price, yield_to_maturity, face_value,
                currency, face_unit, coupon_value, coupon_percent, coupon_frequency,
                coupon_period, accrued_interest, duration_years, duration, duration_waprice,
                has_put_option, has_call_option, maturity_date, listing_level,
                bond_type, bond_kind, offer_date, status, trading_status, next_coupon,
                board_name, call_option_date, put_option_date, NULL
            FROM bonds
        """)
    )

    # 4. Удаляем старую таблицу bonds
    op.drop_table("bonds")

    # 5. Переименовываем bonds_new в bonds
    op.rename_table("bonds_new", "bonds")

    # 6. Создаём индекс на emitent_id
    op.create_index("ix_bonds_emitent_id", "bonds", ["emitent_id"], unique=False)

    # 7. Воссоздаём дочерние таблицы
    op.create_table(
        "bondsecurity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("prev_waprice", sa.Float(), nullable=True),
        sa.Column("yield_at_prev_waprice", sa.Float(), nullable=True),
        sa.Column("prev_price", sa.Float(), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("reg_number", sa.String(), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("issue_size", sa.Integer(), nullable=True),
        sa.Column("prev_legal_close_price", sa.Float(), nullable=True),
        sa.Column("prev_date", sa.Date(), nullable=True),
        sa.Column("remarks", sa.String(), nullable=True),
        sa.Column("market_code", sa.String(), nullable=True),
        sa.Column("instr_id", sa.String(), nullable=True),
        sa.Column("sector_id", sa.String(), nullable=True),
        sa.Column("min_step", sa.Float(), nullable=True),
        sa.Column("face_unit", sa.String(), nullable=True),
        sa.Column("buyback_price", sa.Float(), nullable=True),
        sa.Column("buyback_date", sa.Date(), nullable=True),
        sa.Column("lat_name", sa.String(), nullable=True),
        sa.Column("issue_size_placed", sa.Integer(), nullable=True),
        sa.Column("sec_type", sa.String(), nullable=True),
        sa.Column("settle_date", sa.Date(), nullable=True),
        sa.Column("lot_value", sa.Float(), nullable=True),
        sa.Column("face_value_on_settle_date", sa.Float(), nullable=True),
        sa.Column("date_yield_from_issuer", sa.Date(), nullable=True),
    )

    op.create_table(
        "bondmarketdata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("bid", sa.Float(), nullable=True),
        sa.Column("offer", sa.Float(), nullable=True),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("bid_depth", sa.Integer(), nullable=True),
        sa.Column("offer_depth", sa.Integer(), nullable=True),
        sa.Column("open_price", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("last_change", sa.Float(), nullable=True),
        sa.Column("last_change_prcnt", sa.Float(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("value_usd", sa.Float(), nullable=True),
        sa.Column("waprice", sa.Float(), nullable=True),
        sa.Column("last_cnt_to_last_waprice", sa.Float(), nullable=True),
        sa.Column("wap_to_prev_waprice_prcnt", sa.Float(), nullable=True),
        sa.Column("wap_to_prev_waprice", sa.Float(), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("market_price_today", sa.Float(), nullable=True),
        sa.Column("market_price", sa.Float(), nullable=True),
        sa.Column("last_to_prev_price", sa.Float(), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("vol_today", sa.Integer(), nullable=True),
        sa.Column("val_today", sa.Float(), nullable=True),
        sa.Column("val_today_usd", sa.Float(), nullable=True),
        sa.Column("etf_settle_price", sa.Float(), nullable=True),
        sa.Column("update_time", sa.String(), nullable=True),
    )

    op.create_table(
        "bondmarketdatayield",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("yield_date", sa.String(length=10), nullable=True),
        sa.Column("zcyc_moment", sa.String(length=32), nullable=True),
        sa.Column("yield_date_type", sa.String(length=32), nullable=True),
        sa.Column("effective_yield", sa.Float(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("zspread_bp", sa.Integer(), nullable=True),
        sa.Column("gspread_bp", sa.Integer(), nullable=True),
        sa.Column("waprice", sa.Float(), nullable=True),
        sa.Column("effective_yield_waprice", sa.Float(), nullable=True),
        sa.Column("duration_waprice", sa.Integer(), nullable=True),
        sa.Column("ir", sa.Float(), nullable=True),
        sa.Column("icpi", sa.Float(), nullable=True),
        sa.Column("bei", sa.Float(), nullable=True),
        sa.Column("cbr", sa.Float(), nullable=True),
        sa.Column("yield_to_offer", sa.Float(), nullable=True),
        sa.Column("yield_last_coupon", sa.Float(), nullable=True),
        sa.Column("trade_moment", sa.String(length=32), nullable=True),
        sa.Column("seqnum", sa.Integer(), nullable=True),
        sa.Column("systime", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    """Откат: удаление UNIQUE, emitent_id и индекса."""
    op.drop_table("bondmarketdatayield")
    op.drop_table("bondmarketdata")
    op.drop_table("bondsecurity")

    op.drop_index("ix_bonds_emitent_id", table_name="bonds")

    # Создаём bonds_old без UNIQUE и emitent_id для отката
    op.create_table(
        "bonds_old",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("secid", sa.String(length=64), nullable=False),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("isin", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("secname", sa.String(), nullable=True),
        sa.Column("rating", sa.String(length=32), nullable=True),
        sa.Column("rating_agency", sa.String(length=64), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("coupon_yield_to_price", sa.Float(), nullable=True),
        sa.Column("yield_to_maturity", sa.Float(), nullable=True),
        sa.Column("face_value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("face_unit", sa.String(length=16), nullable=True),
        sa.Column("coupon_value", sa.Float(), nullable=True),
        sa.Column("coupon_percent", sa.Float(), nullable=True),
        sa.Column("coupon_frequency", sa.Float(), nullable=True),
        sa.Column("coupon_period", sa.Integer(), nullable=True),
        sa.Column("accrued_interest", sa.Float(), nullable=True),
        sa.Column("duration_years", sa.Float(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("duration_waprice", sa.Integer(), nullable=True),
        sa.Column("has_put_option", sa.Integer(), nullable=True),
        sa.Column("has_call_option", sa.Integer(), nullable=True),
        sa.Column("maturity_date", sa.String(length=10), nullable=True),
        sa.Column("listing_level", sa.Integer(), nullable=True),
        sa.Column("bond_type", sa.Integer(), nullable=True),
        sa.Column("bond_kind", sa.Integer(), nullable=True),
        sa.Column("offer_date", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("trading_status", sa.String(length=32), nullable=True),
        sa.Column("next_coupon", sa.String(length=10), nullable=True),
        sa.Column("board_name", sa.String(length=128), nullable=True),
        sa.Column("call_option_date", sa.String(length=10), nullable=True),
        sa.Column("put_option_date", sa.String(length=10), nullable=True),
    )

    op.execute(
        sa.text("""
            INSERT INTO bonds_old (
                id, secid, boardid, isin, name, secname, rating, rating_agency,
                current_price, coupon_yield_to_price, yield_to_maturity, face_value,
                currency, face_unit, coupon_value, coupon_percent, coupon_frequency,
                coupon_period, accrued_interest, duration_years, duration, duration_waprice,
                has_put_option, has_call_option, maturity_date, listing_level,
                bond_type, bond_kind, offer_date, status, trading_status, next_coupon,
                board_name, call_option_date, put_option_date
            )
            SELECT
                id, secid, boardid, isin, name, secname, rating, rating_agency,
                current_price, coupon_yield_to_price, yield_to_maturity, face_value,
                currency, face_unit, coupon_value, coupon_percent, coupon_frequency,
                coupon_period, accrued_interest, duration_years, duration, duration_waprice,
                has_put_option, has_call_option, maturity_date, listing_level,
                bond_type, bond_kind, offer_date, status, trading_status, next_coupon,
                board_name, call_option_date, put_option_date
            FROM bonds
        """)
    )

    op.drop_table("bonds")
    op.rename_table("bonds_old", "bonds")

    op.create_table(
        "bondsecurity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("prev_waprice", sa.Float(), nullable=True),
        sa.Column("yield_at_prev_waprice", sa.Float(), nullable=True),
        sa.Column("prev_price", sa.Float(), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("reg_number", sa.String(), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("issue_size", sa.Integer(), nullable=True),
        sa.Column("prev_legal_close_price", sa.Float(), nullable=True),
        sa.Column("prev_date", sa.Date(), nullable=True),
        sa.Column("remarks", sa.String(), nullable=True),
        sa.Column("market_code", sa.String(), nullable=True),
        sa.Column("instr_id", sa.String(), nullable=True),
        sa.Column("sector_id", sa.String(), nullable=True),
        sa.Column("min_step", sa.Float(), nullable=True),
        sa.Column("face_unit", sa.String(), nullable=True),
        sa.Column("buyback_price", sa.Float(), nullable=True),
        sa.Column("buyback_date", sa.Date(), nullable=True),
        sa.Column("lat_name", sa.String(), nullable=True),
        sa.Column("issue_size_placed", sa.Integer(), nullable=True),
        sa.Column("sec_type", sa.String(), nullable=True),
        sa.Column("settle_date", sa.Date(), nullable=True),
        sa.Column("lot_value", sa.Float(), nullable=True),
        sa.Column("face_value_on_settle_date", sa.Float(), nullable=True),
        sa.Column("date_yield_from_issuer", sa.Date(), nullable=True),
    )

    op.create_table(
        "bondmarketdata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("bid", sa.Float(), nullable=True),
        sa.Column("offer", sa.Float(), nullable=True),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("bid_depth", sa.Integer(), nullable=True),
        sa.Column("offer_depth", sa.Integer(), nullable=True),
        sa.Column("open_price", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("last_change", sa.Float(), nullable=True),
        sa.Column("last_change_prcnt", sa.Float(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("value_usd", sa.Float(), nullable=True),
        sa.Column("waprice", sa.Float(), nullable=True),
        sa.Column("last_cnt_to_last_waprice", sa.Float(), nullable=True),
        sa.Column("wap_to_prev_waprice_prcnt", sa.Float(), nullable=True),
        sa.Column("wap_to_prev_waprice", sa.Float(), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("market_price_today", sa.Float(), nullable=True),
        sa.Column("market_price", sa.Float(), nullable=True),
        sa.Column("last_to_prev_price", sa.Float(), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("vol_today", sa.Integer(), nullable=True),
        sa.Column("val_today", sa.Float(), nullable=True),
        sa.Column("val_today_usd", sa.Float(), nullable=True),
        sa.Column("etf_settle_price", sa.Float(), nullable=True),
        sa.Column("update_time", sa.String(), nullable=True),
    )

    op.create_table(
        "bondmarketdatayield",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bond_id", sa.Integer(), sa.ForeignKey("bonds.id"), nullable=True),
        sa.Column("boardid", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("yield_date", sa.String(length=10), nullable=True),
        sa.Column("zcyc_moment", sa.String(length=32), nullable=True),
        sa.Column("yield_date_type", sa.String(length=32), nullable=True),
        sa.Column("effective_yield", sa.Float(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("zspread_bp", sa.Integer(), nullable=True),
        sa.Column("gspread_bp", sa.Integer(), nullable=True),
        sa.Column("waprice", sa.Float(), nullable=True),
        sa.Column("effective_yield_waprice", sa.Float(), nullable=True),
        sa.Column("duration_waprice", sa.Integer(), nullable=True),
        sa.Column("ir", sa.Float(), nullable=True),
        sa.Column("icpi", sa.Float(), nullable=True),
        sa.Column("bei", sa.Float(), nullable=True),
        sa.Column("cbr", sa.Float(), nullable=True),
        sa.Column("yield_to_offer", sa.Float(), nullable=True),
        sa.Column("yield_last_coupon", sa.Float(), nullable=True),
        sa.Column("trade_moment", sa.String(length=32), nullable=True),
        sa.Column("seqnum", sa.Integer(), nullable=True),
        sa.Column("systime", sa.String(length=32), nullable=True),
    )
