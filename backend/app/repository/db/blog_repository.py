"""Репозиторий статей блога в отдельной базе blog.db."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlmodel import Session, create_engine, select

from app.models.entities.blog import BlogArticle
from config.paths import BLOG_DB_PATH


class BlogRepository:
    """CRUD-операции со статьями блога."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or BLOG_DB_PATH)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    def list_articles(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[BlogArticle]:
        """Возвращает статьи с фильтрацией по статусу и категории."""
        with Session(self._engine) as session:
            stmt = select(BlogArticle)
            if status:
                stmt = stmt.where(BlogArticle.status == status)
            if category:
                stmt = stmt.where(BlogArticle.category == category)
            stmt = stmt.order_by(BlogArticle.published_at.desc(), BlogArticle.created_at.desc())
            return list(session.exec(stmt).all())

    def get_by_slug(self, slug: str, *, status: Optional[str] = None) -> Optional[BlogArticle]:
        """Возвращает статью по slug."""
        with Session(self._engine) as session:
            stmt = select(BlogArticle).where(BlogArticle.slug == slug)
            if status:
                stmt = stmt.where(BlogArticle.status == status)
            return session.exec(stmt).first()

    def get_by_id(self, article_id: int) -> Optional[BlogArticle]:
        """Возвращает статью по id."""
        with Session(self._engine) as session:
            return session.get(BlogArticle, article_id)

    def create(self, article: BlogArticle) -> BlogArticle:
        """Создает статью."""
        now = datetime.utcnow()
        article.created_at = now
        article.updated_at = now
        article.published_at = now if article.status == "published" else None
        with Session(self._engine) as session:
            session.add(article)
            session.commit()
            session.refresh(article)
            return article

    def update(self, article_id: int, updates: dict) -> Optional[BlogArticle]:
        """Обновляет статью."""
        with Session(self._engine) as session:
            article = session.get(BlogArticle, article_id)
            if article is None:
                return None
            previous_status = article.status
            for key, value in updates.items():
                if hasattr(article, key):
                    setattr(article, key, value)
            article.updated_at = datetime.utcnow()
            if previous_status != "published" and article.status == "published":
                article.published_at = article.updated_at
            if article.status != "published":
                article.published_at = None
            session.add(article)
            session.commit()
            session.refresh(article)
            return article

    def delete(self, article_id: int) -> bool:
        """Удаляет статью."""
        with Session(self._engine) as session:
            article = session.get(BlogArticle, article_id)
            if article is None:
                return False
            session.delete(article)
            session.commit()
            return True
