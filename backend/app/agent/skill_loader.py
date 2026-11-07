"""Discovery and loading for repo-local Agent Skills.

Skills follow the Agent Skills folder convention: each skill is a directory
containing a ``SKILL.md`` with YAML frontmatter fields ``name`` and
``description``, followed by Markdown instructions. Optional resource folders
such as ``references/``, ``scripts/`` and ``assets/`` are allowed but are not
executed by this loader.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REFERENCE_PATH_RE = re.compile(r"(?<![\w.-])references/[\w./-]+\.md")


@dataclass(frozen=True)
class AgentSkill:
    """Validated metadata for one discovered skill."""

    name: str
    description: str
    manifest_path: Path


def discover_skills(root: Path = SKILLS_DIR) -> List[AgentSkill]:
    """Return valid skills from immediate child directories of ``root``.

    Invalid or incomplete skill folders are ignored with a warning so one bad
    manifest does not prevent the agent from using the remaining skills.
    """
    if not root.is_dir():
        return []

    skills: List[AgentSkill] = []
    for directory in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not directory.is_dir() or directory.is_symlink():
            continue
        manifest = directory / "SKILL.md"
        if manifest.is_symlink() or not manifest.is_file():
            continue
        try:
            # Discovery reads only frontmatter. The full skill body is opened
            # later by load_skill_instructions after the LLM selects this skill.
            name, description = _read_skill_metadata(manifest)
        except (OSError, UnicodeError, ValueError) as exc:
            logger.warning("[AGENT] Пропускаю скил %s: %s", directory.name, exc)
            continue
        if not _SKILL_NAME_RE.fullmatch(name):
            logger.warning(
                "[AGENT] Пропускаю скил %s: недопустимое имя %r", directory.name, name
            )
            continue
        if name != directory.name:
            logger.warning(
                "[AGENT] Пропускаю скил %s: имя в frontmatter должно совпадать с именем папки",
                directory.name,
            )
            continue
        if not description:
            logger.warning(
                "[AGENT] Пропускаю скил %s: отсутствует description", directory.name
            )
            continue
        skills.append(AgentSkill(name=name, description=description, manifest_path=manifest))
    return skills


def load_skill_instructions(skill: AgentSkill) -> str:
    """Load a selected skill and its explicitly referenced Markdown files."""
    root = SKILLS_DIR.resolve()
    manifest = skill.manifest_path.resolve()
    if not manifest.is_relative_to(root) or manifest.name != "SKILL.md":
        raise ValueError("Путь к SKILL.md выходит за пределы каталога скилов")
    name, description, instructions = _parse_manifest(manifest.read_text(encoding="utf-8"))
    if name != skill.name or description != skill.description:
        raise ValueError(f"Манифест скила {skill.name!r} изменился после обнаружения")
    if not instructions.strip():
        raise ValueError(f"Пустое тело SKILL.md для скила {skill.name!r}")

    sections = [instructions.strip()]
    skill_root = manifest.parent.resolve()
    references_root = (skill_root / "references").resolve()
    for relative_path in sorted(set(_REFERENCE_PATH_RE.findall(instructions))):
        resource_path = skill_root / relative_path
        resource = resource_path.resolve()
        if (
            resource_path.is_symlink()
            or not resource.is_relative_to(skill_root)
            or not resource.is_relative_to(references_root)
        ):
            logger.warning(
                "[AGENT] Пропускаю недопустимый ресурс скила %s: %s",
                skill.name,
                relative_path,
            )
            continue
        if not resource.is_file():
            logger.warning("[AGENT] Не найден ресурс скила %s: %s", skill.name, relative_path)
            continue
        try:
            content = resource.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            logger.warning("[AGENT] Не удалось прочитать ресурс скила %s: %s", skill.name, exc)
            continue
        if content:
            sections.append(f"\n--- Материал скила: {relative_path} ---\n{content}")
    return "\n\n".join(sections)


def validate_skill_selection(
    payload: Dict[str, object], available_names: Tuple[str, ...]
) -> Dict[str, List[str]]:
    """Validate the selector response and reject unknown or duplicate skills."""
    if set(payload) != {"skills"}:
        raise ValueError("Ответ выбора скилов должен содержать только поле skills")
    selected = payload.get("skills")
    if not isinstance(selected, list):
        raise ValueError("Поле skills должно быть массивом имён скилов")
    selected_names: List[str] = []
    for item in selected:
        if not isinstance(item, str):
            raise ValueError("Поле skills должно содержать только строковые имена")
        selected_names.append(item)
    if len(selected_names) != len(set(selected_names)):
        raise ValueError("В поле skills не должно быть повторяющихся имён")
    unknown = [name for name in selected_names if name not in available_names]
    if unknown:
        raise ValueError(f"Выбраны неизвестные скилы: {unknown}")
    return {"skills": selected_names}


def skill_metadata(skills: List[AgentSkill]) -> List[Dict[str, str]]:
    """Return the compact catalog shown to the skill selector."""
    return [{"name": skill.name, "description": skill.description} for skill in skills]


def _read_skill_metadata(manifest: Path) -> Tuple[str, str]:
    """Read YAML frontmatter without loading the skill instructions into memory."""
    frontmatter: List[str] = []
    with manifest.open("r", encoding="utf-8") as stream:
        first_line = stream.readline()
        if first_line.lstrip("\ufeff").strip() != "---":
            raise ValueError("SKILL.md должен начинаться с YAML frontmatter между ---")
        for line in stream:
            if line.strip() == "---":
                return _parse_frontmatter(frontmatter)
            frontmatter.append(line.rstrip("\r\n"))
    raise ValueError("Не найден закрывающий --- у YAML frontmatter")


def _parse_manifest(markdown: str) -> Tuple[str, str, str]:
    """Parse a full manifest after its skill has been selected."""
    lines = markdown.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md должен начинаться с YAML frontmatter между ---")
    try:
        closing_index = next(
            index for index in range(1, len(lines)) if lines[index].strip() == "---"
        )
    except StopIteration as exc:
        raise ValueError("Не найден закрывающий --- у YAML frontmatter") from exc

    name, description = _parse_frontmatter(lines[1:closing_index])
    instructions = "\n".join(lines[closing_index + 1:]).strip()
    return name, description, instructions


def _parse_frontmatter(frontmatter: List[str]) -> Tuple[str, str]:
    """Parse the small YAML frontmatter subset used by Agent Skills manifests."""
    fields: Dict[str, str] = {}
    index = 0
    while index < len(frontmatter):
        line = frontmatter[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[:1].isspace() or ":" not in line:
            raise ValueError(f"Некорректная строка frontmatter: {line!r}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if key in fields:
            raise ValueError(f"Повторяющееся поле frontmatter: {key}")
        if value in (">", ">-", "|", "|-"):
            parts: List[str] = []
            index += 1
            while index < len(frontmatter) and (
                not frontmatter[index].strip() or frontmatter[index][:1].isspace()
            ):
                parts.append(frontmatter[index].strip())
                index += 1
            value = " ".join(part for part in parts if part)
            fields[key] = value
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        fields[key] = value
        index += 1

    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    if not name:
        raise ValueError("В frontmatter обязательно поле name")
    if not description:
        raise ValueError("В frontmatter обязательно поле description")
    return name, description
