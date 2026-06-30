from pathlib import Path
from typing import List, Optional, Protocol


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(
        self,
        filenames: List[str],
        base_dir: Optional[Path] = None,
    ) -> str:
        """Читает и объединяет содержимое файлов."""
        ...