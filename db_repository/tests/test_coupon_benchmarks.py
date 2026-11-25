"""Проверки отбора флоатеров по официальному описанию выпуска."""
import unittest
from datetime import date
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine

from db_repository.models.bond import Bond
from db_repository.models.bond_description import BondDescription
from db_repository.models.bond_filters import BondFilters
from db_repository.models.coupon import Coupon
from db_repository.repository.bond_repository import BondRepository


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)
        self.repo = BondRepository()
        sessions = patch("db_repository.repository.bond_repository.get_session", lambda: Session(self.engine))
        sessions.start()
        self.addCleanup(sessions.stop)
        codes = ["RREFKEYR", "RUONIA", "RUONIA3M", "RUONIA6M", "RUONIA_IND", "CPI", "ZR_YLD_CRV", "OTHER"]
        self.codes = codes
        with Session(self.engine) as db:
            for i, code in enumerate([*codes, None, "FIXED_ONLY", "NO_DESCRIPTION"], 1):
                db.add(Bond(id=i, secid=f"T{i}", boardid="TQCB", bond_kind=7 if i == 10 else 6,
                            rating="AA", maturity_date="2099-11-25"))
                if i != 11:
                    db.add(BondDescription(bond_id=i, coupon_benchmark=code,
                                           coupon_benchmark_spread={1: 0, 2: -0.7, 7: 1.5}.get(i)))
            db.commit()

    def test_catalog_and_filtered_results(self):
        catalog = self.repo.list_coupon_benchmarks(BondFilters(exclude_qualified_investors=True), True, None)
        self.assertEqual(set(catalog), set(self.codes))
        for code in self.codes:
            with self.subTest(code=code):
                bonds, _, terms = self.repo.select(BondFilters(coupon_benchmark=[code], exclude_defaults=True))
                self.assertEqual(len(bonds), 1)
                self.assertEqual(terms[bonds[0].id]["coupon_benchmark"], code)
        self.assertEqual(self.repo.list_coupon_benchmarks(BondFilters(rating_min="AAA"), True, None), [])

    def test_matched_november_coupon_is_separate_from_next_coupon(self):
        with Session(self.engine) as db:
            db.add_all([Coupon(bond_id=1, coupondate=day)
                        for day in (date(2090, 1, 3), date(2090, 11, 12), date(2091, 11, 12))])
            db.commit()
        filters = BondFilters(coupon_benchmark=["RREFKEYR"], rating_min="AA",
                              matdate_from=date(2099, 11, 25), coupon_months=[11])
        bonds, coupons, terms = self.repo.select(filters)
        self.assertEqual([bond.id for bond in bonds], [1])
        self.assertEqual(coupons[0].coupondate, date(2090, 1, 3))
        self.assertEqual(terms[1]["matched_coupon_date"], date(2090, 11, 12))

    def test_spread_inclusive_and_known_benchmark(self):
        for value, code in [(0, "RREFKEYR"), (-0.7, "RUONIA"), (1.5, "ZR_YLD_CRV")]:
            with self.subTest(value=value):
                filters = BondFilters(spread_min=value, spread_max=value)
                self.assertEqual(self.repo.list_coupon_benchmarks(filters, False, None), [code])
        bonds, _, _ = self.repo.select(BondFilters(require_coupon_benchmark=True))
        self.assertEqual(len(bonds), 8)
