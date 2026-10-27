"""Create forecast tables (Bank of Russia medium-term forecast).

Revision ID: 015
Revises: 014
Create Date: 2026-02-14

Таблицы для хранения среднесрочного прогноза Банка России:
- forecast — метаданные по дате выпуска прогноза
- forecast_indicator_name — названия показателей для отображения
- forecast_main_indicators — основные параметры прогноза (по годам, мин/макс)
- forecast_balance — показатели платёжного баланса (по годам)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Метаданные прогноза (одна запись на дату)
    op.create_table(
        "forecast",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )

    # 2. Названия показателей (ключ -> человекочитаемое название)
    op.create_table(
        "forecast_indicator_name",
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("section", "key"),
    )

    # 3. Основные показатели (по году и дате прогноза; мин/макс на показатель)
    op.create_table(
        "forecast_main_indicators",
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("inflation_dec_min", sa.Float(), nullable=True),
        sa.Column("inflation_dec_max", sa.Float(), nullable=True),
        sa.Column("inflation_avg_min", sa.Float(), nullable=True),
        sa.Column("inflation_avg_max", sa.Float(), nullable=True),
        sa.Column("key_rate_min", sa.Float(), nullable=True),
        sa.Column("key_rate_max", sa.Float(), nullable=True),
        sa.Column("gdp_min", sa.Float(), nullable=True),
        sa.Column("gdp_max", sa.Float(), nullable=True),
        sa.Column("gdp_q4_min", sa.Float(), nullable=True),
        sa.Column("gdp_q4_max", sa.Float(), nullable=True),
        sa.Column("consumption_min", sa.Float(), nullable=True),
        sa.Column("consumption_max", sa.Float(), nullable=True),
        sa.Column("household_consumption_min", sa.Float(), nullable=True),
        sa.Column("household_consumption_max", sa.Float(), nullable=True),
        sa.Column("accumulation_min", sa.Float(), nullable=True),
        sa.Column("accumulation_max", sa.Float(), nullable=True),
        sa.Column("capital_accumulation_min", sa.Float(), nullable=True),
        sa.Column("capital_accumulation_max", sa.Float(), nullable=True),
        sa.Column("export_min", sa.Float(), nullable=True),
        sa.Column("export_max", sa.Float(), nullable=True),
        sa.Column("import_min", sa.Float(), nullable=True),
        sa.Column("import_max", sa.Float(), nullable=True),
        sa.Column("money_supply_min", sa.Float(), nullable=True),
        sa.Column("money_supply_max", sa.Float(), nullable=True),
        sa.Column("claims_economy_min", sa.Float(), nullable=True),
        sa.Column("claims_economy_max", sa.Float(), nullable=True),
        sa.Column("claims_orgs_min", sa.Float(), nullable=True),
        sa.Column("claims_orgs_max", sa.Float(), nullable=True),
        sa.Column("claims_households_min", sa.Float(), nullable=True),
        sa.Column("claims_households_max", sa.Float(), nullable=True),
        sa.Column("mortgage_loans_min", sa.Float(), nullable=True),
        sa.Column("mortgage_loans_max", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("forecast_date", "year"),
        sa.ForeignKeyConstraint(["forecast_date"], ["forecast.date"], ondelete="CASCADE"),
    )

    # 4. Платёжный баланс (по году и дате прогноза; одно значение на показатель)
    op.create_table(
        "forecast_balance",
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("account_current_operations", sa.Float(), nullable=True),
        sa.Column("trade_balance", sa.Float(), nullable=True),
        sa.Column("goods_export", sa.Float(), nullable=True),
        sa.Column("goods_import", sa.Float(), nullable=True),
        sa.Column("services_balance", sa.Float(), nullable=True),
        sa.Column("services_export", sa.Float(), nullable=True),
        sa.Column("services_import", sa.Float(), nullable=True),
        sa.Column("income_balance", sa.Float(), nullable=True),
        sa.Column("financial_account", sa.Float(), nullable=True),
        sa.Column("liabilities_net", sa.Float(), nullable=True),
        sa.Column("assets_net", sa.Float(), nullable=True),
        sa.Column("errors_omissions", sa.Float(), nullable=True),
        sa.Column("reserves_change", sa.Float(), nullable=True),
        sa.Column("oil_price", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("forecast_date", "year"),
        sa.ForeignKeyConstraint(["forecast_date"], ["forecast.date"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("forecast_balance")
    op.drop_table("forecast_main_indicators")
    op.drop_table("forecast_indicator_name")
    op.drop_table("forecast")
