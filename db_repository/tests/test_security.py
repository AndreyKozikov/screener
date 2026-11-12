"""Offline tests for db_repository API-key enforcement."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import SecretStr

from db_repository.core.security import is_authorized, require_api_key


def _settings(*, required: bool, key: str) -> SimpleNamespace:
    return SimpleNamespace(
        require_api_key=required,
        api_key=SecretStr(key),
    )


class AuthorizationTests(unittest.TestCase):
    def test_health_style_when_key_is_not_required(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=False, key="")):
            self.assertTrue(is_authorized(None))

    def test_missing_key_is_rejected_when_required(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=True, key="secret")):
            self.assertFalse(is_authorized(None))
            self.assertFalse(is_authorized("wrong"))

    def test_correct_key_is_accepted(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=True, key="secret")):
            self.assertTrue(is_authorized("secret"))

    def test_empty_configured_key_fails_closed(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=True, key="")):
            self.assertFalse(is_authorized(""))

    def test_dependency_returns_401_for_wrong_key(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=True, key="secret")):
            with self.assertRaises(HTTPException) as raised:
                require_api_key("wrong")
        self.assertEqual(raised.exception.status_code, 401)

    def test_dependency_returns_503_for_missing_configuration(self) -> None:
        with patch("db_repository.core.security.settings", _settings(required=True, key="")):
            with self.assertRaises(HTTPException) as raised:
                require_api_key(None)
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
