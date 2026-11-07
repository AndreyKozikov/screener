"""Логирование сессий ИИ-агента для анализа запросов и поведения модели.

Каждый диалог (session_id) пишется в отдельную папку
`{AGENT_LOG_DIR}/{session_id}/`:
- session.json — метаданные сессии (создание/обновление, число реплик);
- events.jsonl — построчный JSON журнал событий: запросы пользователя,
  уточняющие вопросы, JSON-решения модели (raw и распарсенные), вызовы
  инструментов и итоговые ответы.

Журнал нужен, чтобы анализировать, какие запросы и уточнения приходят
пользователям и какие инструменты стоит добавить на сервис.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from config.paths import BACKEND_DIR

_UNSAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9_-]+")
logger = logging.getLogger(__name__)


def _resolve_log_dir(log_dir: str | Path) -> Path:
    """Resolve relative session log paths from the backend root."""
    path = Path(log_dir).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


class AgentSessionLogger:
    def __init__(self, log_dir: str | Path, enabled: bool = True) -> None:
        self._log_dir = _resolve_log_dir(log_dir)
        self._enabled = enabled
        self._write_lock = Lock()
        self._failure_lock = Lock()
        self._failure_reported = False

    @property
    def config(self) -> tuple[Path, bool]:
        return self._log_dir, self._enabled

    def session_dir(self, session_id: str) -> Path:
        safe_id = _UNSAFE_CHARS_RE.sub("_", session_id) or "unknown"
        return self._log_dir / safe_id

    def write_event(self, session_id: str, event: Dict[str, Any]) -> None:
        """Дописывает событие в events.jsonl сессии."""
        if not self._enabled:
            return
        path = self.session_dir(session_id) / "events.jsonl"
        try:
            record = {"ts": _now_iso(), **event, "session_id": session_id}
            serialized = json.dumps(record, ensure_ascii=False, default=str) + "\n"
            with self._write_lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(serialized)
            self._clear_failure()
        except Exception:
            # Logging must not break the agent, but failures must be visible.
            self._report_failure(session_id, path)

    def write_meta(self, session_id: str, meta: Dict[str, Any]) -> None:
        """Записывает метаданные сессии (создаются один раз)."""
        if not self._enabled:
            return
        path = self.session_dir(session_id) / "session.json"
        try:
            record = {"ts": _now_iso(), **meta}
            serialized = json.dumps(record, ensure_ascii=False, indent=2, default=str)
            with self._write_lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(serialized)
            self._clear_failure()
        except Exception:
            self._report_failure(session_id, path)

    def _report_failure(self, session_id: str, path: Path) -> None:
        with self._failure_lock:
            if self._failure_reported:
                return
            self._failure_reported = True
            logger.exception(
                "Failed to write agent session log for session %s to %s",
                session_id,
                path,
            )

    def _clear_failure(self) -> None:
        with self._failure_lock:
            self._failure_reported = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_default_logger: Optional[AgentSessionLogger] = None
_default_logger_lock = Lock()


def get_session_logger() -> AgentSessionLogger:
    """Возвращает singleton-логгер сессий агента (по настройкам settings)."""
    global _default_logger
    with _default_logger_lock:
        from config.settings import settings

        configured = AgentSessionLogger(
            log_dir=settings.AGENT_LOG_DIR,
            enabled=settings.AGENT_LOG_ENABLED,
        )
        if _default_logger is None or _default_logger.config != configured.config:
            _default_logger = configured
        return _default_logger


def reset_session_logger() -> None:
    """Сбрасывает singleton (для тестов/перезагрузки настроек)."""
    global _default_logger
    with _default_logger_lock:
        _default_logger = None
