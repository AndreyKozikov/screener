"""Create describe_fields table and seed from describe.json.

Revision ID: 013
Revises: 012
Create Date: 2026-02-08

Таблица describe_fields хранит описания полей (секции securities, marketdata)
для отдачи на фронтенд вместо файла describe.json. Данные заполняются из
backend/app/data/describe.json при применении миграции.
"""

import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _describe_json_path() -> Path:
    """Путь к describe.json относительно корня backend."""
    # migrations/versions/013_...py -> alembic -> backend
    backend_dir = Path(__file__).resolve().parent.parent.parent
    return backend_dir / "app" / "data" / "describe.json"


def upgrade() -> None:
    """Создаёт таблицу describe_fields и заполняет данными из describe.json."""
    op.create_table(
        "describe_fields",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("section", sa.String(32), nullable=False, index=True),
        sa.Column("field_name", sa.String(128), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.UniqueConstraint("section", "field_name", name="uq_describe_fields_section_field"),
    )

    desc_path = _describe_json_path()
    if not desc_path.exists():
        return

    with open(desc_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return

    rows = []
    for section, fields in data.items():
        if not isinstance(fields, dict):
            continue
        for field_name, description in fields.items():
            rows.append({
                "section": section,
                "field_name": field_name,
                "description": description if isinstance(description, str) else str(description),
            })

    if rows:
        conn = op.get_bind()
        stmt = sa.text(
            "INSERT INTO describe_fields (section, field_name, description) "
            "VALUES (:section, :field_name, :description)"
        )
        for row in rows:
            conn.execute(stmt, row)


def downgrade() -> None:
    """Удаляет таблицу describe_fields."""
    op.drop_table("describe_fields")
