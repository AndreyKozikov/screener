"""Durable, user-scoped transcript storage for agent chats."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    from redis import Redis
except ImportError:  # dependency can be installed independently of the API package
    Redis = None  # type: ignore[assignment,misc]

from config.settings import settings


class AgentChatRepository:
    def __init__(self) -> None:
        self.path = Path(settings.DATA_DIR).resolve() / "agent_chats.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redis = Redis.from_url(settings.AGENT_REDIS_URL, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2) if settings.AGENT_REDIS_URL and Redis else None
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agent_chats (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Новый чат',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_agent_chats_user_updated
                    ON agent_chats(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS agent_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES agent_chats(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    intent TEXT,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_messages_session
                    ON agent_chat_messages(session_id, id);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def ensure_chat(self, user_id: str, session_id: str) -> bool:
        now = self._now()
        with self._connect() as db:
            row = db.execute("SELECT user_id FROM agent_chats WHERE session_id=?", (session_id,)).fetchone()
            if row:
                return row["user_id"] == user_id
            db.execute("INSERT INTO agent_chats(session_id,user_id,created_at,updated_at) VALUES(?,?,?,?)",
                       (session_id, user_id, now, now))
            return True

    def list_chats(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT c.session_id,c.title,c.created_at,c.updated_at,
                (SELECT content FROM agent_chat_messages m WHERE m.session_id=c.session_id
                 ORDER BY m.id DESC LIMIT 1) AS preview
                FROM agent_chats c WHERE c.user_id=? ORDER BY c.updated_at DESC""", (user_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_chat(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        cache_key = f"agent:chat:{user_id}:{session_id}"
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        with self._connect() as db:
            chat = db.execute("SELECT * FROM agent_chats WHERE user_id=? AND session_id=?",
                              (user_id, session_id)).fetchone()
            if not chat:
                return None
            messages = db.execute("SELECT role,content,intent,sources_json,created_at FROM agent_chat_messages WHERE session_id=? ORDER BY id",
                                  (session_id,)).fetchall()
            result = {**dict(chat), "messages": [{"role": m["role"], "content": m["content"],
                    "intent": m["intent"], "sources": json.loads(m["sources_json"]),
                    "timestamp": m["created_at"]} for m in messages]}
            if self.redis:
                try:
                    self.redis.setex(cache_key, 43200, json.dumps(result, ensure_ascii=False))
                except Exception:
                    pass
            return result

    def save_snapshot(self, user_id: str, session_id: str, turns: list[dict], state: dict | None = None) -> None:
        now = self._now()
        with self._connect() as db:
            db.execute("UPDATE agent_chats SET updated_at=?,state_json=? WHERE user_id=? AND session_id=?",
                       (now, json.dumps(state or {}, ensure_ascii=False), user_id, session_id))
            db.execute("DELETE FROM agent_chat_messages WHERE session_id=?", (session_id,))
            db.executemany("""INSERT INTO agent_chat_messages(session_id,role,content,intent,sources_json,created_at)
                VALUES(?,?,?,?,?,?)""", [(session_id, t.get("role", "user"), str(t.get("content", "")),
                t.get("intent"), json.dumps(t.get("sources", []), ensure_ascii=False), now) for t in turns])
        if self.redis:
            try:
                self.redis.delete(f"agent:chat:{user_id}:{session_id}")
                chat = self.get_chat(user_id, session_id)
                if chat:
                    chat["state_json"] = json.dumps(state or {}, ensure_ascii=False)
                    self.redis.setex(f"agent:chat:{user_id}:{session_id}", 43200,
                                     json.dumps(chat, ensure_ascii=False))
            except Exception:
                pass

    def set_title(self, user_id: str, session_id: str, title: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE agent_chats SET title=? WHERE user_id=? AND session_id=?",
                       (title[:80], user_id, session_id))
        if self.redis:
            try:
                self.redis.delete(f"agent:chat:{user_id}:{session_id}")
            except Exception:
                pass

    def delete_chat(self, user_id: str, session_id: str) -> bool:
        with self._connect() as db:
            cur = db.execute("DELETE FROM agent_chats WHERE user_id=? AND session_id=?", (user_id, session_id))
            if self.redis:
                try:
                    self.redis.delete(f"agent:chat:{user_id}:{session_id}")
                except Exception:
                    pass
            return cur.rowcount > 0


repository = AgentChatRepository()
