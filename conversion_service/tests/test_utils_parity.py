"""Parity tests for conversion_service local copies of shared utilities."""

import unittest
from decimal import Decimal

from conversion_service.app.utils.coupon_utils import (
    COUPON_STORAGE_FIELDS,
    clean_string_value,
    extract_coupon_for_storage,
    to_frontend_coupon,
)
from conversion_service.app.utils.rating_utils import (
    RATINGS,
    get_rating_index,
    standardize_rating,
)


class RatingUtilityTests(unittest.TestCase):
    def test_standardize_rating_cases(self) -> None:
        cases = {
            "ruBB-": "BB-",
            "BBB(RU)": "BBB",
            "BB+|ru|": "BB+",
            "aaa": "AAA",
            "AA+.SF": "AA+",
            "  A-  ": "A-",
            "not-a-rating": "not-a-rating",
            None: None,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(standardize_rating(source), expected)

    def test_rating_index(self) -> None:
        self.assertEqual(get_rating_index("AAA"), 0)
        self.assertEqual(get_rating_index("D"), len(RATINGS) - 1)
        self.assertIsNone(get_rating_index("unknown"))


class CouponUtilityTests(unittest.TestCase):
    def test_clean_string_value_handles_surrogates(self) -> None:
        cleaned = clean_string_value({"text": "bad\ud800value"})
        self.assertIn("bad", cleaned["text"])
        cleaned["text"].encode("utf-8")

    def test_extract_coupon_for_storage_keeps_only_storage_fields(self) -> None:
        coupon = {field: field for field in COUPON_STORAGE_FIELDS}
        coupon["ignored"] = "yes"
        self.assertEqual(extract_coupon_for_storage(coupon), coupon_storage_only(coupon))
        self.assertNotIn("ignored", extract_coupon_for_storage(coupon))

    def test_to_frontend_coupon_removes_bond_id(self) -> None:
        row = {"bond_id": 1, "secid": "RU1", "value": Decimal("10")}
        self.assertEqual(to_frontend_coupon(row), {"secid": "RU1", "value": Decimal("10")})


def coupon_storage_only(coupon: dict) -> dict:
    return {field: coupon.get(field) for field in COUPON_STORAGE_FIELDS}


if __name__ == "__main__":
    unittest.main()
