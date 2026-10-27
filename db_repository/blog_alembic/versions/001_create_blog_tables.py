"""Create blog tables.

Revision ID: 001_create_blog_tables
Revises:
Create Date: 2026-05-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_create_blog_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создает таблицу статей блога."""
    op.create_table(
        "blog_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("content_markdown", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_blog_articles_slug", "blog_articles", ["slug"])
    op.create_index("ix_blog_articles_category", "blog_articles", ["category"])
    op.create_index("ix_blog_articles_status", "blog_articles", ["status"])
    op.create_index("ix_blog_articles_published_at", "blog_articles", ["published_at"])


def downgrade() -> None:
    """Удаляет таблицу статей блога."""
    op.drop_index("ix_blog_articles_published_at", table_name="blog_articles")
    op.drop_index("ix_blog_articles_status", table_name="blog_articles")
    op.drop_index("ix_blog_articles_category", table_name="blog_articles")
    op.drop_index("ix_blog_articles_slug", table_name="blog_articles")
    op.drop_table("blog_articles")
