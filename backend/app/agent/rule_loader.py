"""Loading of always-applicable, stage-specific agent rules."""

from pathlib import Path
from typing import Dict, Tuple

RULES_DIR = Path(__file__).resolve().parent / "rules"

_RULE_FILES = frozenset(
    {
        "common.md",
        "router.md",
        "finalizer.md",
        "skill-selection.md",
        "router-json-repair.md",
        "skill-selection-json-repair.md",
    }
)
_STAGE_RULES: Dict[str, Tuple[str, ...]] = {
    "router": ("router.md",),
    "finalizer": ("finalizer.md",),
    "skill-selection": ("skill-selection.md",),
}


def load_rule(filename: str) -> str:
    """Load one known rule file; unknown names and missing rules fail loudly."""
    if filename not in _RULE_FILES:
        raise ValueError(f"Неизвестный файл правил: {filename!r}")

    path = RULES_DIR / filename
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Обязательный файл правил не найден: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Обязательный файл правил пуст: {path}")
    return content


def load_rule_set(stage: str) -> str:
    """Load common rules and the rules required by an LLM stage."""
    try:
        stage_files = _STAGE_RULES[stage]
    except KeyError as exc:
        raise ValueError(f"Неизвестный этап агента: {stage!r}") from exc

    return "\n\n".join(
        load_rule(filename) for filename in ("common.md", *stage_files)
    )
