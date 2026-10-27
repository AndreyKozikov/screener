"""Create emission_documents table.

Revision ID: 020
Revises: 019
Create Date: 2026-02-28

Таблица для хранения эмиссионных документов эмитентов с e-disclosure.ru.
Связь с emitent_edisclosure через FK на emitent_edisclosure.id.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу emission_documents с FK на emitent_edisclosure.id."""
    op.create_table(
        "emission_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "emitent_edisclosure_id",
            sa.Integer(),
            sa.ForeignKey("emitent_edisclosure.id"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("reg_number", sa.Text(), nullable=True),
        sa.Column("date_registration", sa.Text(), nullable=True),
        sa.Column("registering_org", sa.Text(), nullable=True),
        sa.Column("date_ground_publication", sa.Text(), nullable=True),
        sa.Column("date_placement", sa.Text(), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_emission_documents_emitent_edisclosure_id",
        "emission_documents",
        ["emitent_edisclosure_id"],
    )


def downgrade() -> None:
    """Удаляет таблицу emission_documents."""
    op.drop_index("ix_emission_documents_emitent_edisclosure_id", table_name="emission_documents")
    op.drop_table("emission_documents")
