"""In-memory хранилище сессий ИИ-агента.

MVP хранит историю диалогов в памяти процесса (по session_id). Персистентное
хранение (таблица agent_messages в db_repository) подключается позже, без
изменения контракта DTO.
"""

import time
import uuid
from threading import Lock
from typing import Any, Dict, List, Optional

MAX_HISTORY_TURNS: int = 8
SESSION_TTL_SECONDS: int = 12 * 3600
_SESSION_CLEANUP_INTERVAL: int = 300


class AgentSession:
    """Сессия диалога агента."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.turns: List[dict] = []
        self.state: Dict[str, Any] = {}
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at


class AgentSessionStore:
    """Простое потокобезопасное хранилище сессий с автоочисткой по TTL."""

    def __init__(
        self,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        max_turns: int = MAX_HISTORY_TURNS,
    ) -> None:
        self._sessions: Dict[str, AgentSession] = {}
        self._ttl_seconds = ttl_seconds
        self._max_turns = max_turns
        self._lock = Lock()
        self._last_cleanup: float = time.time()

    def get_or_create(self, session_id: str) -> AgentSession:
        """Возвращает сессию по id, создавая новую при отсутствии."""
        self._maybe_cleanup()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = AgentSession(session_id)
                self._sessions[session_id] = session
            session.updated_at = time.time()
            return session

    def append_turn(self, session_id: str, turn: dict) -> None:
        """Добавляет реплику в историю, обрезая её до max_turns."""
        session = self.get_or_create(session_id)
        with self._lock:
            session.turns.append(turn)
            if len(session.turns) > self._max_turns * 2:
                session.turns = session.turns[-(self._max_turns * 2):]

    def get_history(self, session_id: str, limit: int = MAX_HISTORY_TURNS) -> List[dict]:
        """Возвращает последние `limit` реплик диалога для промпта."""
        session = self.get_or_create(session_id)
        with self._lock:
            return list(session.turns[-limit:])

    def get_state(self, session_id: str, key: str) -> Any:
        """Возвращает произвольное состояние сессии (или None)."""
        session = self.get_or_create(session_id)
        with self._lock:
            return session.state.get(key)

    def set_state(self, session_id: str, key: str, value: Any) -> None:
        """Сохраняет произвольное состояние сессии."""
        session = self.get_or_create(session_id)
        with self._lock:
            session.state[key] = value

    def clear_state(self, session_id: str, key: str) -> None:
        """Удаляет сохранённое состояние сессии."""
        session = self.get_or_create(session_id)
        with self._lock:
            session.state.pop(key, None)

    def _maybe_cleanup(self) -> None:
        """Периодически удаляет сессии старше TTL."""
        now = time.time()
        if now - self._last_cleanup < _SESSION_CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.updated_at > self._ttl_seconds
        ]
        if expired:
            with self._lock:
                for sid in expired:
                    self._sessions.pop(sid, None)


def new_session_id() -> str:
    """Генерирует новый идентификатор диалога."""
    return uuid.uuid4().hex