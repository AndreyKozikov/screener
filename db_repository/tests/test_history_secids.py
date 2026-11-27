"""Тесты отбора SECID для обновления истории торгов."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from db_repository.repository.operations.bonds_repository import BondsRepository


class HistorySecidsSelectionTests(unittest.TestCase):
    def test_get_all_secids_excludes_matured_and_pact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bonds.db"
            today = date.today()
            with closing(sqlite3.connect(path)) as conn:
                conn.executescript(
                    """
                    CREATE TABLE bonds(
                        id INTEGER,
                        secid TEXT,
                        boardid TEXT,
                        maturity_date TEXT
                    );
                    """
                )
                conn.executemany(
                    "INSERT INTO bonds VALUES (?, ?, ?, ?)",
                    [
                        (1, "ACTIVE", "TQCB", "2099-01-01"),
                        (2, "MATURED", "TQCB", "2020-01-01"),
                        (3, "TODAY", "TQCB", today.isoformat()),
                        (4, "YESTERDAY", "TQCB", (today - timedelta(days=1)).isoformat()),
                        (5, "NULL_MATURITY", "TQCB", None),
                        (6, "EMPTY_MATURITY", "TQCB", ""),
                        (7, "ZERO_MATURITY", "TQCB", "0000-00-00"),
                        (8, "PACT", " pact ", "2099-01-01"),
                        (9, "ACTIVE", "TQCB", "2099-01-01"),
                    ],
                )
                conn.commit()

            repository = BondsRepository(path)
            try:
                self.assertEqual(
                    repository.get_all_secids(),
                    [
                        "ACTIVE",
                        "EMPTY_MATURITY",
                        "NULL_MATURITY",
                        "ZERO_MATURITY",
                    ],
                )
            finally:
                repository._engine.dispose()


if __name__ == "__main__":
    unittest.main()
