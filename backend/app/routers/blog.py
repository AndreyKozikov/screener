"""Публичные и скрытые API блога."""

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError

from app.models.entities.blog import BlogArticle
from app.repository.db.blog_repository import BlogRepository
from config.paths import BLOG_UPLOADS_DIR

public_router = APIRouter(prefix="/api/blog", tags=["blog"])
admin_router = APIRouter(prefix="/api/blog-admin", tags=["blog-admin"])

_repository = BlogRepository()
_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024


class BlogArticlePayload(BaseModel):
    """Данные для создания или обновления статьи."""

    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    summary: str = ""
    content_markdown: str = ""
    category: str = "Облигации"
    cover_image_url: Optional[str] = None
    status: str = "draft"

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        slug = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("Slug may contain lowercase latin letters, numbers and hyphens")
        return slug

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"draft", "published"}:
            raise ValueError("Status must be draft or published")
        return value

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return value.strip() or "Облигации"


class BlogArticleResponse(BaseModel):
    """Ответ API со статьей блога."""

    id: int
    slug: str
    title: str
    summary: str
    content_markdown: str
    category: str
    cover_image_url: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]


class UploadResponse(BaseModel):
    """Ответ API загрузки изображения."""

    url: str
    filename: str


def _to_response(article: BlogArticle) -> BlogArticleResponse:
    return BlogArticleResponse(
        id=article.id or 0,
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        content_markdown=article.content_markdown,
        category=article.category,
        cover_image_url=article.cover_image_url,
        status=article.status,
        created_at=article.created_at,
        updated_at=article.updated_at,
        published_at=article.published_at,
    )


@public_router.get("/articles", response_model=List[BlogArticleResponse])
async def list_published_articles(
    category: Optional[str] = Query(default=None),
) -> List[BlogArticleResponse]:
    """Возвращает опубликованные статьи."""
    return [
        _to_response(article)
        for article in _repository.list_articles(status="published", category=category)
    ]


@public_router.get("/articles/{slug}", response_model=BlogArticleResponse)
async def get_published_article(slug: str) -> BlogArticleResponse:
    """Возвращает опубликованную статью по slug."""
    article = _repository.get_by_slug(slug, status="published")
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return _to_response(article)


@public_router.get("/uploads/{filename}")
async def get_uploaded_image(filename: str) -> FileResponse:
    """Отдает загруженное изображение блога."""
    safe_name = Path(filename).name
    path = BLOG_UPLOADS_DIR / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@admin_router.get("/articles", response_model=List[BlogArticleResponse])
async def list_admin_articles() -> List[BlogArticleResponse]:
    """Возвращает все статьи для скрытой админки."""
    return [_to_response(article) for article in _repository.list_articles()]


@admin_router.post("/articles", response_model=BlogArticleResponse)
async def create_article(payload: BlogArticlePayload) -> BlogArticleResponse:
    """Создает статью."""
    article = BlogArticle(**payload.model_dump())
    try:
        return _to_response(_repository.create(article))
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Article slug already exists") from exc


@admin_router.put("/articles/{article_id}", response_model=BlogArticleResponse)
async def update_article(article_id: int, payload: BlogArticlePayload) -> BlogArticleResponse:
    """Обновляет статью."""
    try:
        article = _repository.update(article_id, payload.model_dump())
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Article slug already exists") from exc
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return _to_response(article)


@admin_router.delete("/articles/{article_id}")
async def delete_article(article_id: int) -> dict[str, bool]:
    """Удаляет статью."""
    deleted = _repository.delete(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"success": True}


@admin_router.post("/uploads", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)) -> UploadResponse:
    """Загружает изображение для статьи."""
    original_name = file.filename or ""
    ext = Path(original_name).suffix.lower()
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Image is too large")

    BLOG_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = BLOG_UPLOADS_DIR / filename
    path.write_bytes(content)
    return UploadResponse(url=f"/api/blog/uploads/{filename}", filename=filename)
