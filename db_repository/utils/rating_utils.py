"""Canonical formatting and ordering for letter-based credit ratings."""

import re
from typing import List, Optional


RATINGS: List[str] = [
    "AAA",
    "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "CCC+", "CCC", "CCC-",
    "CC", "C",
    "D",
]

RU_INDICATORS_PATTERN = re.compile(
    r"\s*\(RU\)\s*$|\.ru\s*$|^\(RU\)\s*|^ru\s*|\|ru\|",
    flags=re.IGNORECASE,
)
SF_SUFFIX_PATTERN = re.compile(r"\.SF$", flags=re.IGNORECASE)
STANDARD_RATING_PATTERN = re.compile(r"(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)([+-]?)")


def standardize_rating(rating: Optional[str]) -> Optional[str]:
    """Normalize agency-specific wrappers while preserving ``+`` and ``-``.

    Examples: ``ruBB-`` -> ``BB-``, ``BBB(RU)`` -> ``BBB``,
    ``BB+|ru|`` -> ``BB+``, and ``aaa`` -> ``AAA``.
    """
    if not isinstance(rating, str):
        return None

    normalized = rating.strip()
    if not normalized:
        return None

    previous = None
    while normalized != previous:
        previous = normalized
        normalized = RU_INDICATORS_PATTERN.sub("", normalized).strip()

    normalized = SF_SUFFIX_PATTERN.sub("", normalized).strip()
    grade_candidate = re.sub(r"\s+", "", normalized).upper()

    # Return a canonical grade only when the whole value is a recognized grade.
    # This keeps agency modifiers such as + and - meaningful and avoids turning
    # unrelated text into a plausible rating through partial matching.
    match = STANDARD_RATING_PATTERN.fullmatch(grade_candidate)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    return normalized or None


def get_rating_index(rating: Optional[str]) -> Optional[int]:
    """Return the exact position of a normalized grade in the rating scale."""
    normalized = standardize_rating(rating)
    if normalized is None:
        return None

    try:
        return RATINGS.index(normalized)
    except ValueError:
        return None
