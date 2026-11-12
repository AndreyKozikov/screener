"""Baseline current blog schema

Revision ID: 002_baseline_blog_schema
Revises:
Create Date: 2026-11-08

Baseline текущей схемы. Создан по фактическому состоянию базы.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "002_baseline_blog_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE blog_articles (
	id INTEGER NOT NULL, 
	slug VARCHAR(160) NOT NULL, 
	title VARCHAR(240) NOT NULL, 
	summary VARCHAR NOT NULL, 
	content_markdown VARCHAR NOT NULL, 
	category VARCHAR(120) NOT NULL, 
	cover_image_url VARCHAR(500), 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	published_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
)"""
    )
    op.execute(
        """CREATE INDEX ix_blog_articles_category ON blog_articles (category)"""
    )
    op.execute(
        """CREATE INDEX ix_blog_articles_published_at ON blog_articles (published_at)"""
    )
    op.execute(
        """CREATE INDEX ix_blog_articles_slug ON blog_articles (slug)"""
    )
    op.execute(
        """CREATE INDEX ix_blog_articles_status ON blog_articles (status)"""
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_blog_articles_status"')
    op.execute('DROP INDEX IF EXISTS "ix_blog_articles_slug"')
    op.execute('DROP INDEX IF EXISTS "ix_blog_articles_published_at"')
    op.execute('DROP INDEX IF EXISTS "ix_blog_articles_category"')
    op.execute('DROP TABLE IF EXISTS "blog_articles"')
