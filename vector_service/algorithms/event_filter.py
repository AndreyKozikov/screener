import re
from typing import Dict, List, Optional, Tuple

_CHAR_MAP: Dict[str, str] = {
    "А": "A", "В": "B", "С": "C", "Е": "E", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
    "а": "a", "с": "c", "е": "e", "к": "k",
    "м": "m", "о": "o", "р": "p", "х": "x",
}



def clean_event_text(text: str) -> str:
    """Удаляет из текста события лишние блоки и маркеры для упрощения анализа LLM."""
    text = re.sub(
        r"1\. Общие сведения.*?2\. Содержание сообщения",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"3\. Подпись.*", "", text, flags=re.DOTALL)
    text = re.sub(r"^\d+\.\d+\.\s*", "", text, flags=re.MULTILINE)
    text = text.replace("2. Содержание сообщения", "")
    return text.strip()


def normalize_reg_number(reg_number: str) -> Tuple[str, str]:
    """Создаёт две нормализованные копии регистрационного номера.

    На основе карты ``_CHAR_MAP`` формирует:

    - ``reg_num_ru``: все символы из карты заменены на кириллические эквиваленты.
    - ``reg_num_lat``: все символы из карты заменены на латинские эквиваленты.

    Args:
        reg_number: Регистрационный номер облигации.

    Returns:
        Кортеж ``(reg_num_ru, reg_num_lat)``.
    """
    reverse_map: Dict[str, str] = {lat: ru for ru, lat in _CHAR_MAP.items()}
    reg_num_ru = "".join(reverse_map.get(ch, ch) for ch in reg_number)
    reg_num_lat = "".join(_CHAR_MAP.get(ch, ch) for ch in reg_number)
    return reg_num_ru, reg_num_lat


def event_text_matches_reg_number(
    text: str,
    reg_num_lat: str,
) -> bool:
    """Проверяет, содержит ли текст события полный регистрационный номер.

    Нормализует текст события (заменяет кириллицу на латиницу для визуально схожих символов)
    и ищет в нём латинскую версию регистрационного номера.

    Args:
        text: Текст события.
        reg_num_lat: Регистрационный номер в латинской нормализации.

    Returns:
        ``True``, если в тексте найден номер; иначе ``False``.
    """
    if not text or not reg_num_lat:
        return False

    # Нормализуем текст события: переводим в нижний регистр и заменяем кириллицу на латиницу
    text_norm = text.lower()
    for ru_char, lat_char in _CHAR_MAP.items():
        text_norm = text_norm.replace(ru_char.lower(), lat_char.lower())

    return reg_num_lat.lower() in text_norm


def event_matches_secid(subsection_text: str, secid: str) -> bool:
    """Проверяет наличие SECID облигации в тексте события.

    Ищет secid как целое слово (с учётом границ ``\\b``), без учёта регистра.

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        secid: Идентификатор ценной бумаги (например «RU000A107UQ9»).

    Returns:
        ``True``, если secid найден; иначе ``False``.
    """
    if not subsection_text or not secid or not secid.strip():
        return False

    secid_clean: str = secid.strip()
    pattern: str = r"\b" + re.escape(secid_clean) + r"\b"

    try:
        found: bool = bool(re.search(pattern, subsection_text, re.IGNORECASE))
    except re.error as exc:
        print(f"  [MATCH SECID] ошибка regex — {exc}", flush=True)
        return False

    if found:
        print(f"  [MATCH SECID] secid={secid_clean!r} -> найден", flush=True)
    return found


def event_matches_reg_number(subsection_text: str, reg_number: str) -> bool:
    """Проверяет наличие регистрационного номера в тексте события.

    Делегирует проверку в ``event_text_matches_reg_number`` из
    ``app.utils.edisclosure_utils`` (только полное совпадение номера, без паттернов по частям).

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        reg_number: Регистрационный номер облигации (например «4B02-01-36245-A-001P»).

    Returns:
        ``True``, если рег. номер найден; иначе ``False``.
    """
    if not subsection_text or not reg_number or not reg_number.strip():
        return False

    reg_number_clean: str = reg_number.strip()

    _, reg_num_lat = normalize_reg_number(reg_number_clean)
    found = event_text_matches_reg_number(subsection_text, reg_num_lat)

    if found:
        print(f"  [MATCH REG_NUMBER] reg_number={reg_number_clean!r} -> найден", flush=True)
    return found


def event_matches_issuename(text: str, issuename: Optional[str]) -> bool:
    """Ищет полное наименование выпуска как фразу, допуская переносы строк."""
    words = issuename.split() if issuename else []
    if not words:
        return False
    phrase = r"\s+".join(re.escape(word) for word in words)
    return re.search(r"(?<!\w)" + phrase + r"(?!\w)", text, re.IGNORECASE) is not None


def event_matches_series(
    subsection_text: str,
    series: Optional[str],
) -> bool:
    """Проверяет наличие серии облигации в тексте события.

    Ищет значение серии как подстроку, допуская произвольные пробелы/переносы
    между символами дефиса, без учёта регистра.

    Args:
        subsection_text: Полный текст события (или фрагмент для поиска).
        series: Серия облигации (например «ПБО-002Р-31») или ``None``.

    Returns:
        ``True``, если серия найдена; ``False``, если серия пуста/None или не найдена.
    """
    if not series or not series.strip():
        return False
    if not subsection_text:
        return False

    series_clean: str = series.strip()

    parts: List[str] = series_clean.split("-")
    flexible_pattern: str = r"\s*[\-–—]\s*".join(re.escape(p) for p in parts)

    try:
        found: bool = bool(
            re.search(flexible_pattern, subsection_text, re.IGNORECASE)
        )
    except re.error as exc:
        print(f"  [MATCH SERIES] ошибка regex — {exc}", flush=True)
        return False

    if found:
        print(f"  [MATCH SERIES] series={series_clean!r} -> найден", flush=True)
    return found

