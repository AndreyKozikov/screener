"""Transactional persistence for imported broker statement portfolios."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from db_repository.config.paths import PORTFOLIO_DB_PATH
from db_repository.core.portfolio_database_init import init_portfolio_database


class PortfolioRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or PORTFOLIO_DB_PATH)
        init_portfolio_database(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _key(value: Any) -> str | None:
        text = str(value or "").strip()
        return text.casefold() if text else None

    def find_duplicate(self, user_id: str, source_file_sha256: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id AS portfolio_id, name AS portfolio_name FROM portfolios WHERE user_id = ? AND source_file_sha256 = ?",
                (user_id, source_file_sha256),
            ).fetchone()
            return dict(row) if row else None

    def save_report_import(
        self,
        user_id: str,
        portfolio_name: str,
        source_file_name: str,
        source_file_sha256: str,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Save a complete import in a single transaction, or leave no rows."""
        now = datetime.now(timezone.utc).isoformat()
        summary = {
            "securities": len(report.get("securities", [])),
            "trades": len(report.get("trades", [])),
            "cash_operations": len(report.get("cash_operations", [])),
            "income_payments": len(report.get("income_payments", [])),
            "positions": len(report.get("positions", [])),
            "security_movements": len(report.get("security_movements", [])),
            "source_rows": len(report.get("source_rows", [])),
            "parse_errors": sum(1 for row in report.get("source_rows", []) if row.get("parse_status") == "error"),
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id, name FROM portfolios WHERE user_id = ? AND source_file_sha256 = ?",
                (user_id, source_file_sha256),
            ).fetchone()
            if existing:
                return {
                    "duplicate": True,
                    "portfolio_id": existing["id"],
                    "portfolio_name": existing["name"],
                    "records_summary": summary,
                }

            cursor = connection.execute(
                """INSERT INTO portfolios (
                    user_id, name, base_currency, source_file_name, source_file_sha256,
                    report_period_start, report_period_end, created_at, updated_at
                ) VALUES (?, ?, 'RUB', ?, ?, ?, ?, ?, ?)""",
                (user_id, portfolio_name, source_file_name, source_file_sha256,
                 report.get("report_period_start"), report.get("report_period_end"), now, now),
            )
            portfolio_id = int(cursor.lastrowid)
            import_cursor = connection.execute(
                """INSERT INTO portfolio_imports
                   (portfolio_id, parser_version, status, started_at)
                   VALUES (?, ?, 'processing', ?)""",
                (portfolio_id, "1.0.0", now),
            )
            import_id = int(import_cursor.lastrowid)

            security_ids: dict[str, int] = {}
            for item in report.get("securities", []):
                aliases = [item.get("isin"), item.get("security_code"), item.get("name")]
                # ISIN is authoritative when present; equal display names must not merge distinct issues.
                existing_id = security_ids.get(self._key(item.get("isin"))) if item.get("isin") else None
                if existing_id is None and item.get("isin"):
                    existing_row = connection.execute(
                        "SELECT id FROM portfolio_securities WHERE portfolio_id = ? AND isin = ?",
                        (portfolio_id, item["isin"]),
                    ).fetchone()
                    existing_id = int(existing_row["id"]) if existing_row else None
                if existing_id is None and not item.get("isin"):
                    existing_id = next((security_ids[self._key(alias)] for alias in aliases[1:]
                                        if self._key(alias) in security_ids), None)
                if existing_id is None:
                    sec_cursor = connection.execute(
                        """INSERT INTO portfolio_securities (
                            portfolio_id, isin, security_code, name, currency_code, asset_type,
                            security_category, issuer, raw_data_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (portfolio_id, item.get("isin"), item.get("security_code"), item["name"],
                         item.get("currency_code"), item.get("asset_type"), item.get("security_category"),
                         item.get("issuer"), item.get("raw_data_json")),
                    )
                    existing_id = int(sec_cursor.lastrowid)
                for alias in aliases:
                    key = self._key(alias)
                    if key:
                        security_ids[key] = existing_id

            trade_ids: list[tuple[dict[str, Any], int, int | None]] = []
            for item in report.get("trades", []):
                security_id = security_ids.get(self._key(item.get("security_key")))
                trade_cursor = connection.execute(
                    """INSERT INTO portfolio_trades (
                        portfolio_id, security_id, trade_date, settlement_date, trade_time, operation_type,
                        quantity, price_percent_scaled, amount_ex_nkd_minor, nkd_minor,
                        broker_fee_minor, exchange_fee_minor, currency_code, trade_number, status, comment,
                        source_row_number, raw_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (portfolio_id, security_id, item["trade_date"], item.get("settlement_date"),
                     item.get("trade_time"), item["operation_type"], item["quantity"],
                     item.get("price_percent_scaled"), item.get("amount_ex_nkd_minor"), item.get("nkd_minor"),
                     item.get("broker_fee_minor"), item.get("exchange_fee_minor"), item.get("currency_code"),
                     item.get("trade_number"), item.get("status"), item.get("comment"),
                     item.get("source_row_number"), item.get("raw_data_json")),
                )
                trade_ids.append((item, int(trade_cursor.lastrowid), security_id))

            cash_inserted: list[tuple[dict[str, Any], int, int | None, int | None]] = []
            for item in report.get("cash_operations", []):
                linked_trade: tuple[dict[str, Any], int, int | None] | None = None
                source_trade_date = None
                match = re.search(
                    r"(?:сделка|комиссия(?:\s+брокера|\s+биржи)?)\s+от\s+(\d{2}\.\d{2}\.\d{4})",
                    item.get("description") or "", re.IGNORECASE,
                )
                if match:
                    source_trade_date = datetime.strptime(match.group(1), "%d.%m.%Y").date().isoformat()
                candidates = [trade for trade in trade_ids if source_trade_date and trade[0]["trade_date"] == source_trade_date]
                if item["operation_type"] == "BROKER_FEE":
                    amount = abs(item["amount_minor"])
                    linked_trade = next((trade for trade in candidates
                        if abs(trade[0].get("broker_fee_minor") or 0) == amount), None)
                elif item["operation_type"] == "EXCHANGE_FEE":
                    amount = abs(item["amount_minor"])
                    linked_trade = next((trade for trade in candidates
                        if abs(trade[0].get("exchange_fee_minor") or 0) == amount), None)
                elif len(candidates) == 1:
                    linked_trade = candidates[0]
                elif candidates:
                    amount = abs(item["amount_minor"])
                    linked_trade = next((trade for trade in candidates
                        if abs(trade[0].get("amount_ex_nkd_minor") or 0) + abs(trade[0].get("nkd_minor") or 0) == amount), None)
                kind = item["operation_type"]
                if linked_trade and kind == "OTHER":
                    kind = linked_trade[0]["operation_type"]
                elif kind == "OTHER" and "сделка" in (item.get("description") or "").casefold():
                    kind = "BUY" if item["amount_minor"] < 0 else "SELL"
                security_id = linked_trade[2] if linked_trade else security_ids.get(self._key(item.get("security_key")))
                trade_id = linked_trade[1] if linked_trade else None
                cash_cursor = connection.execute(
                    """INSERT INTO portfolio_cash_operations (
                        portfolio_id, security_id, trade_id, operation_date, operation_type, description,
                        amount_minor, currency_code, source_row_number, raw_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (portfolio_id, security_id, trade_id, item["operation_date"], kind, item.get("description"),
                     item["amount_minor"], item.get("currency_code"), item.get("source_row_number"),
                     item.get("raw_data_json")),
                )
                cash_inserted.append((item, int(cash_cursor.lastrowid), security_id, trade_id))

            linked_cash_ids: set[int] = set()
            for item in report.get("income_payments", []):
                related = next((cash for cash in cash_inserted
                    if cash[1] not in linked_cash_ids
                    and cash[0]["operation_date"] == item["payment_date"]
                    and cash[0].get("currency_code") == item.get("currency_code")
                    and cash[0]["operation_type"] == item.get("income_type")
                    and cash[0]["amount_minor"] == item["amount_minor"]), None)
                cash_operation_id = related[1] if related else None
                if cash_operation_id:
                    linked_cash_ids.add(cash_operation_id)
                security_id = related[2] if related else security_ids.get(self._key(item.get("security_key")))
                connection.execute(
                    """INSERT INTO portfolio_income_payments (
                        portfolio_id, security_id, cash_operation_id, payment_date, income_type,
                        amount_minor, tax_withheld_minor, net_amount_minor, currency_code,
                        description, source_row_number, raw_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (portfolio_id, security_id, cash_operation_id, item["payment_date"], item.get("income_type"),
                     item["amount_minor"], item.get("tax_withheld_minor"), item.get("net_amount_minor"),
                     item.get("currency_code"), item.get("description"), item.get("source_row_number"),
                     item.get("raw_data_json")),
                )

            for item in report.get("positions", []):
                security_id = security_ids.get(self._key(item.get("security_key")))
                if security_id is None:
                    continue
                connection.execute(
                    """INSERT INTO portfolio_positions (
                        portfolio_id, security_id, snapshot_type, quantity,
                        market_value_ex_nkd_minor
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(portfolio_id, security_id, snapshot_type) DO UPDATE SET
                        quantity = CASE WHEN excluded.quantity IS NULL THEN portfolio_positions.quantity WHEN portfolio_positions.quantity IS NULL THEN excluded.quantity ELSE portfolio_positions.quantity + excluded.quantity END,
                        market_value_ex_nkd_minor = CASE WHEN excluded.market_value_ex_nkd_minor IS NULL THEN portfolio_positions.market_value_ex_nkd_minor WHEN portfolio_positions.market_value_ex_nkd_minor IS NULL THEN excluded.market_value_ex_nkd_minor ELSE portfolio_positions.market_value_ex_nkd_minor + excluded.market_value_ex_nkd_minor END""",
                    (portfolio_id, security_id, item["snapshot_type"], item.get("quantity"),
                     item.get("market_value_ex_nkd_minor")),
                )

            for item in report.get("security_movements", []):
                connection.execute(
                    """INSERT INTO portfolio_security_movements (
                        portfolio_id, security_id, movement_date, movement_type, quantity_delta,
                        nominal_amount_minor, currency_code, description, source_row_number, raw_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (portfolio_id, security_ids.get(self._key(item.get("security_key"))), item["movement_date"],
                     item["movement_type"], item.get("quantity_delta"), item.get("nominal_amount_minor"),
                     item.get("currency_code"), item.get("description"), item.get("source_row_number"),
                     item.get("raw_data_json")),
                )

            for item in report.get("source_rows", []):
                connection.execute(
                    """INSERT INTO portfolio_source_rows (
                        import_id, section_code, source_row_number, raw_data_json, parse_status, parse_error
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (import_id, item["section_code"], item["source_row_number"], item["raw_data_json"],
                     item["parse_status"], item.get("parse_error")),
                )

            connection.execute(
                """UPDATE portfolio_imports
                   SET status = 'completed', finished_at = ?, records_summary_json = ? WHERE id = ?""",
                (datetime.now(timezone.utc).isoformat(), json.dumps(summary, ensure_ascii=False), import_id),
            )
            # Report stored relational rows (positions may be consolidated by security).
            for key, table_name in (
                ("securities", "portfolio_securities"), ("trades", "portfolio_trades"),
                ("cash_operations", "portfolio_cash_operations"),
                ("income_payments", "portfolio_income_payments"),
                ("positions", "portfolio_positions"),
                ("security_movements", "portfolio_security_movements"),
            ):
                summary[key] = connection.execute(
                    f"SELECT count(*) FROM {table_name} WHERE portfolio_id = ?", (portfolio_id,),
                ).fetchone()[0]
            summary_json = json.dumps(summary, ensure_ascii=False)
            connection.execute("UPDATE portfolio_imports SET records_summary_json = ? WHERE id = ?", (summary_json, import_id))
            return {
                "duplicate": False,
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio_name,
                "report_period_start": report.get("report_period_start"),
                "report_period_end": report.get("report_period_end"),
                "import_status": "completed",
                "records_summary": summary,
            }

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT p.id AS portfolio_id, p.name AS portfolio_name, p.base_currency,
                          p.source_file_name, p.report_period_start, p.report_period_end, p.created_at,
                          i.status AS import_status, i.records_summary_json
                   FROM portfolios p JOIN portfolio_imports i ON i.portfolio_id = p.id
                   WHERE p.user_id = ? ORDER BY p.created_at DESC""",
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["records_summary"] = json.loads(item.pop("records_summary_json") or "{}")
            except json.JSONDecodeError:
                item["records_summary"] = {}
            result.append(item)
        return result

    def get_for_user(self, user_id: str, portfolio_id: int) -> dict[str, Any] | None:
        """Return one portfolio and all its imported rows, scoped to its owner."""
        with self._connection() as connection:
            portfolio = connection.execute(
                """SELECT p.id AS portfolio_id, p.user_id, p.name AS portfolio_name, p.base_currency,
                          p.source_file_name, p.source_file_sha256, p.report_period_start,
                          p.report_period_end, p.created_at, p.updated_at,
                          i.id AS import_id, i.parser_version, i.status AS import_status,
                          i.started_at, i.finished_at, i.records_summary_json, i.error_message
                   FROM portfolios p JOIN portfolio_imports i ON i.portfolio_id = p.id
                   WHERE p.user_id = ? AND p.id = ?""",
                (user_id, portfolio_id),
            ).fetchone()
            if not portfolio:
                return None
            result: dict[str, Any] = dict(portfolio)
            try:
                result["records_summary"] = json.loads(result.pop("records_summary_json") or "{}")
            except json.JSONDecodeError:
                result["records_summary"] = {}
            for key, table in (
                ("securities", "portfolio_securities"), ("trades", "portfolio_trades"),
                ("cash_operations", "portfolio_cash_operations"),
                ("income_payments", "portfolio_income_payments"),
                ("positions", "portfolio_positions"),
                ("security_movements", "portfolio_security_movements"),
            ):
                result[key] = [dict(row) for row in connection.execute(
                    f"SELECT * FROM {table} WHERE portfolio_id = ? ORDER BY id", (portfolio_id,),
                ).fetchall()]
            result["source_rows"] = [dict(row) for row in connection.execute(
                """SELECT sr.* FROM portfolio_source_rows sr
                   JOIN portfolio_imports i ON i.id = sr.import_id
                   WHERE i.portfolio_id = ? ORDER BY sr.section_code, sr.source_row_number""",
                (portfolio_id,),
            ).fetchall()]
            return result

    def delete_for_user(self, user_id: str, portfolio_id: int) -> bool:
        """Delete one user's imported portfolio and all dependent report rows."""
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM portfolios WHERE id = ? AND user_id = ?",
                (portfolio_id, user_id),
            )
            return cursor.rowcount > 0

    def get_current_positions_for_user(
        self, user_id: str, portfolio_id: int
    ) -> dict[str, Any] | None:
        """Read the closing snapshot and security identifiers, without trades."""
        with self._connection() as connection:
            portfolio = connection.execute(
                """SELECT id AS portfolio_id, name AS portfolio_name, base_currency
                   FROM portfolios WHERE id = ? AND user_id = ?""",
                (portfolio_id, user_id),
            ).fetchone()
            if portfolio is None:
                return None
            positions = connection.execute(
                """SELECT s.id AS security_id, s.isin, s.security_code, s.asset_type,
                          p.quantity, p.market_value_ex_nkd_minor
                   FROM portfolio_positions p
                   JOIN portfolio_securities s ON s.id = p.security_id
                   WHERE p.portfolio_id = ? AND p.snapshot_type = 'CLOSING'
                     AND COALESCE(p.quantity, 0) > 0
                   ORDER BY s.id""",
                (portfolio_id,),
            ).fetchall()
            return {**dict(portfolio), "positions": [dict(row) for row in positions]}

    def get_current_position_trades_for_user(
        self, user_id: str, portfolio_id: int
    ) -> list[dict[str, Any]]:
        """Return complete trades for bonds still held in the closing snapshot."""
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT t.*,
                          s.isin, s.security_code, s.name AS security_name,
                          s.currency_code AS security_currency_code, s.asset_type,
                          s.security_category, s.issuer, s.raw_data_json AS security_raw_data_json,
                          pos.quantity AS current_quantity
                   FROM portfolio_trades t
                   JOIN portfolios p ON p.id = t.portfolio_id
                   JOIN portfolio_positions pos ON pos.portfolio_id = t.portfolio_id
                       AND pos.security_id = t.security_id
                       AND pos.snapshot_type = 'CLOSING'
                   JOIN portfolio_securities s ON s.id = pos.security_id
                   WHERE p.id = ? AND p.user_id = ? AND pos.quantity > 0
                     AND s.asset_type = 'bond'
                   ORDER BY t.security_id, t.trade_date, t.id""",
                (portfolio_id, user_id),
            ).fetchall()
            return [dict(row) for row in rows]


__all__ = ["PortfolioRepository"]
