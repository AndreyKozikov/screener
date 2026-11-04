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
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_UNSAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class AgentSessionLogger:
    def __init__(self, log_dir: str, enabled: bool = True) -> None:
        self._log_dir = Path(log_dir)
        self._enabled = enabled

    def session_dir(self, session_id: str) -> Path:
        safe_id = _UNSAFE_CHARS_RE.sub("_", session_id) or "unknown"
        return self._log_dir / safe_id

    def write_event(self, session_id: str, event: Dict[str, Any]) -> None:
        """Дописывает событие в events.jsonl сессии."""
        if not self._enabled:
            return
        try:
            directory = self.session_dir(session_id)
            directory.mkdir(parents=True, exist_ok=True)
            record = {"ts": _now_iso(), "session_id": session_id, **event}
            with open(directory / "events.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:
            # Логирование не должно ронять агента.
            pass

    def write_meta(self, session_id: str, meta: Dict[str, Any]) -> None:
        """Записывает метаданные сессии (создаются один раз)."""
        if not self._enabled:
            return
        try:
            directory = self.session_dir(session_id)
            directory.mkdir(parents=True, exist_ok=True)
            record = {"ts": _now_iso(), **meta}
            with open(directory / "session.json", "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_default_logger: Optional[AgentSessionLogger] = None


def get_session_logger() -> AgentSessionLogger:
    """Возвращает singleton-логгер сессий агента (по настройкам settings)."""
    global _default_logger
    if _default_logger is None:
        from config.settings import settings

        _default_logger = AgentSessionLogger(
            log_dir=settings.AGENT_LOG_DIR,
            enabled=settings.AGENT_LOG_ENABLED,
        )
    return _default_logger


def reset_session_logger() -> None:
    """Сбрасывает singleton (для тестов/перезагрузки настроек)."""
    global _default_logger
    _default_logger = None