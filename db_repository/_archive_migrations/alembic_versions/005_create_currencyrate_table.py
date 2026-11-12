"""Create currencyrate table.

Revision ID: 005
Revises: 004
Create Date: 2026-02-02

Инициализирующая миграция для таблицы currencyrate (курсы валют ЦБ РФ).
Первичный ключ — поле dt (date). Поля source_date и курсы USD, EUR, CNY (rate, nominal, original_value).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу currencyrate с полем dt (PK), source_date и полями курсов USD, EUR, CNY."""
    op.create_table(
        "currencyrate",
        sa.Column("dt", sa.Date(), nullable=False),
        sa.Column("source_date", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("usd_rate", sa.Float(), nullable=True),
        sa.Column("usd_nominal", sa.Integer(), nullable=True),
        sa.Column("usd_original_value", sa.String(length=32), nullable=True),
        sa.Column("eur_rate", sa.Float(), nullable=True),
        sa.Column("eur_nominal", sa.Integer(), nullable=True),
        sa.Column("eur_original_value", sa.String(length=32), nullable=True),
        sa.Column("cny_rate", sa.Float(), nullable=True),
        sa.Column("cny_nominal", sa.Integer(), nullable=True),
        sa.Column("cny_original_value", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("dt"),
    )


def downgrade() -> None:
    """Удаляет таблицу currencyrate."""
    op.drop_table("currencyrate")
