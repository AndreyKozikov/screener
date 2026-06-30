"""Репозитории для работы с JSON файлами."""

from app.repository.files.file_storage import FileStorage
from app.repository.files.markdown_repository import MarkdownFileRepository

from pathlib import Path
from typing import Optional

markdownfile_repository: Optional[MarkdownFileRepository] = None
file_storage: Optional[FileStorage] = None


def init_markdownfile_repository(path: Path) -> None:
    global markdownfile_repository
    markdownfile_repository = MarkdownFileRepository(path)


def get_markdownfile_repository() -> MarkdownFileRepository:
    if markdownfile_repository is None:
        raise RuntimeError("MarkdownFileRepository not initialized. Call init_markdownfile_repository first.")
    return markdownfile_repository


def init_file_storage() -> None:
    global file_storage
    file_storage = FileStorage()


def get_file_storage() -> FileStorage:

    global file_storage

    if file_storage is None:
        file_storage = FileStorage()

    return file_storage
