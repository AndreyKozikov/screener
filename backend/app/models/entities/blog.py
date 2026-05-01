"""Модели отдельной базы данных блога."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class BlogArticle(SQLModel, table=True):
    """Статья блога, хранящаяся в отдельной SQLite базе blog.db."""

    __tablename__ = "blog_articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(sa_column=Column(String(160), unique=True, index=True, nullable=False))
    title: str = Field(max_length=240)
    summary: str = Field(default="")
    content_markdown: str = Field(default="")
    category: str = Field(default="Облигации", index=True, max_length=120)
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    status: str = Field(default="draft", index=True, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = Field(default=None, index=True)
