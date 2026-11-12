"""Offline tests for the backend database-service HTTP client."""

import unittest
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from app.repository.db.client import DBRepositoryClient
from app.repository.db.remote_repository import AttrDict, _decode, _encode


class WireFormatTests(unittest.TestCase):
    def test_scalar_tags_roundtrip(self) -> None:
        values = [
            date(2026, 11, 8),
            datetime(2026, 11, 8, 12, 30, 15),
            time(12, 30, 15),
            Decimal("123.45"),
            UUID("12345678-1234-5678-1234-567812345678"),
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(_decode(_encode(value)), value)

    def test_containers_roundtrip(self) -> None:
        value = {
            "tuple": (1, "two"),
            "set": {3, 4},
            "list": [date(2026, 1, 1)],
            "nested": {"decimal": Decimal("1.5")},
        }
        decoded = _decode(_encode(value))
        self.assertEqual(decoded["tuple"], (1, "two"))
        self.assertEqual(decoded["set"], {3, 4})
        self.assertEqual(decoded["list"], [date(2026, 1, 1)])
        self.assertEqual(decoded["nested"]["decimal"], Decimal("1.5"))
        self.assertIsInstance(decoded, AttrDict)


class ClientHeaderTests(unittest.TestCase):
    def test_api_key_header_is_added(self) -> None:
        client = DBRepositoryClient.__new__(DBRepositoryClient)
        client.api_key = "test-key"
        headers = client._headers({"Content-Type": "application/json"})
        self.assertEqual(headers["X-API-Key"], "test-key")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_empty_api_key_is_not_sent(self) -> None:
        client = DBRepositoryClient.__new__(DBRepositoryClient)
        client.api_key = ""
        self.assertNotIn("X-API-Key", client._headers())


if __name__ == "__main__":
    unittest.main()
