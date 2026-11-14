"""User account persistence owned by the database microservice."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlmodel import create_engine

from db_repository.config.paths import DB_PATH


class UsersRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self._engine = create_engine(
            f"sqlite:///{Path(db_path or DB_PATH).resolve()}",
            connect_args={"check_same_thread": False},
        )

    def create(self, user_id: str, email: str, password_hash: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, password_hash, created_at, updated_at, role) "
                "VALUES (:id, :email, :password_hash, :now, :now, :role)"
            ), {"id": user_id, "email": email, "password_hash": password_hash, "now": now, "role": "user"})
        return self.get_by_id(user_id)

    def get_by_email(self, email: str) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(text(
                "SELECT id, email, password_hash, created_at, updated_at, role FROM users WHERE email = :email"
            ), {"email": email}).mappings().first()
            return dict(row) if row else None

    def get_by_id(self, user_id: str) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(text(
                "SELECT id, email, password_hash, created_at, updated_at, role FROM users WHERE id = :id"
            ), {"id": user_id}).mappings().first()
            return dict(row) if row else None
