import re

_SERIES_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\-]*")


def _normalize_series(value: str | None) -> str | None:
    """Отбрасывает кавычки и знаки препинания вокруг значения серии."""
    match = _SERIES_PATTERN.search(value or "")
    return match.group(0) if match else None


def extract_series(name: str | None) -> str | None:
    """Извлекает серию из названия бумаги или наименования выпуска."""
    tokens = (name or "").split()
    if not tokens:
        return None

    dated = bool(re.fullmatch(r"\d{2}/\d{2}/\d{2}", tokens[-1]))
    suffix = tokens[-1].casefold() in {"обл", "обл.", "об.", "сер."}
    end = len(tokens) - int(dated or suffix)
    markers = []
    index = 0
    while index < end:
        token = tokens[index].casefold()
        if token == "обл." and index + 1 < end and tokens[index + 1].casefold() == "сер.":
            markers.append((1, index, index + 2))
            index += 2
            continue
        ranks = {"серия": 0, "серии": 0, "об.сер.": 1, "кл.": 2, "бо": 4, "об.": 5, "обл.": 5, "сер.": 6}
        rank = 3 if token.startswith("бо-") else ranks.get(token)
        if rank is not None:
            markers.append((rank, index, index + 1))
        index += 1

    if not markers:
        if suffix and end:
            return _normalize_series(tokens[end - 1].rsplit("-", 1)[-1])
        return None
    _, start, following = min(markers)
    if tokens[start].casefold().startswith("бо-"):
        return _normalize_series(tokens[start])
    for rank, start, stop in markers:
        if start == following:
            if rank == 3:
                return _normalize_series(tokens[start])
            following = stop
    return _normalize_series(tokens[following]) if following < end else None
