"""Tests for multithreaded coupon downloading orchestration.

Запись в БД замокана (FakeDBCoupon): тесты не вставляют данные в реальную БД.
"""

import time
import unittest
from unittest import mock

from conversion_service.app.services import coupon_service as service_module
from conversion_service.app.services.coupon_service import (
    CouponService,
    MAX_COUPON_WORKERS,
)

COUPON_KEYS = (
    "coupondate", "recorddate", "startdate",
    "initialfacevalue", "facevalue", "faceunit",
    "value", "valueprc", "value_rub",
)


def make_coupon(day: int) -> dict:
    return {k: (f"2026-01-{day:02d}" if k == "coupondate" else 1) for k in COUPON_KEYS}


class FakeMoexClient:
    def __init__(self, coupons_by_secid=None, delay=0.0, failing_secids=()):
        self.coupons_by_secid = coupons_by_secid or {}
        self.delay = delay
        self.failing_secids = set(failing_secids)

    def fetch_coupons(self, secid):
        if self.delay:
            time.sleep(self.delay)
        if secid in self.failing_secids:
            raise RuntimeError(f"boom for {secid}")
        return {
            "amortizations": [],
            "coupons": self.coupons_by_secid.get(secid, []),
            "offers": [],
        }


class FakeDBCoupon:
    def __init__(self):
        self.batches = []

    def save_moex_coupons(self, records):
        self.batches.append(list(records))


class FakeBondsRepository:
    def __init__(self, id_secid_list):
        self.id_secid_list = id_secid_list

    def get_id_secid_list(self):
        return list(self.id_secid_list)


class ExecutorProbe:
    """Обёртка ThreadPoolExecutor, запоминающая переданный max_workers."""

    def __init__(self, real_executor):
        self.real_executor = real_executor
        self.max_workers_seen = []

    def __call__(self, max_workers=1, **kwargs):
        self.max_workers_seen.append(max_workers)
        return self.real_executor(max_workers=max_workers, **kwargs)


def make_service(moex_client, bond_list):
    service = CouponService(moex_client=moex_client)
    service._bonds_repo = FakeBondsRepository(bond_list)
    service._db_coupon = FakeDBCoupon()
    return service, service._db_coupon


class RefreshAllTests(unittest.IsolatedAsyncioTestCase):
    def test_downloads_in_parallel_with_cap_and_saves_once(self):
        bonds = [(i, f"SEC{i:02d}") for i in range(1, 13)]
        coupons = [make_coupon(1), make_coupon(2)]
        client = FakeMoexClient(
            coupons_by_secid={secid: coupons for _, secid in bonds},
            delay=0.2,
        )
        service, db = make_service(client, bonds)

        probe = ExecutorProbe(service_module.ThreadPoolExecutor)
        with mock.patch.object(service_module, "ThreadPoolExecutor", probe):
            started = time.monotonic()
            result = self._run(service.refresh_all())
            elapsed = time.monotonic() - started

        self.assertEqual(probe.max_workers_seen, [MAX_COUPON_WORKERS])
        # 12 бумаг x 0.2с последовательно = 2.4с; 10 потоков укладываются в 2 волны
        self.assertLess(elapsed, 1.5, f"скачивание не распараллелилось: {elapsed:.2f}s")

        self.assertEqual(result["total_bonds"], 12)
        self.assertEqual(result["updated"], 12)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["skipped"], 0)

        self.assertEqual(len(db.batches), 1, "запись в БД должна быть одной пачкой")
        saved = db.batches[0]
        self.assertEqual(len(saved), 24)
        saved_by_bond = {}
        for record in saved:
            saved_by_bond.setdefault(record["bond_id"], []).append(record)
        self.assertEqual(set(saved_by_bond), {i for i in range(1, 13)})
        self.assertTrue(all("bond_id" in r and "coupondate" in r for r in saved))

    def test_single_bond_uses_single_worker(self):
        bonds = [(7, "ALONE")]
        client = FakeMoexClient(coupons_by_secid={"ALONE": [make_coupon(3)]})
        service, db = make_service(client, bonds)

        probe = ExecutorProbe(service_module.ThreadPoolExecutor)
        with mock.patch.object(service_module, "ThreadPoolExecutor", probe):
            result = self._run(service.refresh_all())

        self.assertEqual(probe.max_workers_seen, [1])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(len(db.batches), 1)
        self.assertEqual(len(db.batches[0]), 1)

    def test_skips_empty_secids_and_counts_errors(self):
        bonds = [(1, "GOOD"), (2, ""), (3, None), (4, "BAD")]
        client = FakeMoexClient(
            coupons_by_secid={"GOOD": [make_coupon(4)]},
            failing_secids={"BAD"},
        )
        service, db = make_service(client, bonds)
        result = self._run(service.refresh_all())

        self.assertEqual(result["total_bonds"], 4)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["skipped"], 2)

        self.assertEqual(len(db.batches), 1)
        saved = db.batches[0]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["bond_id"], 1)

    def test_no_bonds_saves_nothing_but_calls_db(self):
        service, db = make_service(FakeMoexClient(), [])
        result = self._run(service.refresh_all())

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(len(db.batches), 1)
        self.assertEqual(db.batches[0], [])

    @staticmethod
    def _run(coro):
        import asyncio
        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
