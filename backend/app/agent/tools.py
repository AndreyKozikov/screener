"""Реестр инструментов ИИ-агента.

Каждый инструмент — это функция-обёртка над существующими сервисами
(bonds_service, keyrate_service, coupon_service, llm_analysis_service).
Сами сервисы не изменяются. Результаты усекаются до компактных данных
перед отправкой в LLM — весь датасет в промпт не уходит.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from app.agent.dto import AgentSource
from app.agent.contracts import tool_args_schema, validate_tool_args
from app.models import BondFilters, BondsListResponse
from app.services.bonds_service import get_bond_detail, get_bonds_list, list_coupon_benchmarks
from app.services.coupon_service import get_coupon_service
from app.services.keyrate_service import get_keyrate_service

MAX_COUPONS_TO_LLM: int = 12


@dataclass
class ToolOutput:
    """Результат выполнения инструмента."""

    data: Dict[str, Any] = field(default_factory=dict)
    sources: List[AgentSource] = field(default_factory=list)
    summary: str = ""
    final_answer: Optional[str] = None
    error: Optional[str] = None
    question: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


_FILTER_DESCRIPTION_OVERRIDES: Dict[str, str] = {
    "bondtype": (
        "Список ID типов облигаций: 1=exchange_bond (биржевые), "
        "2=ofz_bond (ОФЗ), 3=corporate_bond (корпоративные), "
        "4=municipal_bond (муниципальные), 5=subfederal_bond (субфедеральные)"
    ),
    "bondtype43": (
        "Список ID видов облигаций: 1=Амортизируемая, 2=Валютная, "
        "3=Дисконтная, 4=Конвертируемая, 5=Линкер/с индексируемым номиналом, "
        "6=С плавающим купоном (флоатер), 7=С фиксированным (известным) купоном, "
        "8=С фиксированным (неизвестным) купоном, 9=Структурная. "
        "«Известный постоянный купон» — это 7."
    ),
    "exclude_amortized": (
        "true — исключить амортизируемые облигации (с амортизацией долга). "
        "«Без амортизации» = true"
    ),
    "exclude_options": (
        "true — исключить облигации со встроенными опционами (оферты call/put, "
        "досрочный выкуп/продажа). «Без встроенных опционов» = true"
    ),
}


def _filters_args_text() -> str:
    """Полная схема сохраняет Optional, типы элементов, форматы и ограничения."""
    schema = tool_args_schema("search_bonds")
    for name, desc in _FILTER_DESCRIPTION_OVERRIDES.items():
        schema["properties"][name]["description"] = desc
    return json.dumps(schema, ensure_ascii=False, indent=2)


async def _run_search_bonds(args: Dict[str, Any]) -> ToolOutput:
    """Поиск облигаций по фильтрам (аргументы = поля BondsListFiltersDTO)."""
    allowed = validate_tool_args("search_bonds", args)
    allowed.setdefault("skip", 0)
    allowed.setdefault("limit", 1000)
    allowed.setdefault("exclude_spob", True)
    filters = BondFilters(**allowed)
    # Ссылка воспроизводит условия поиска независимо от текущего состояния таблицы.
    filter_args = filters.model_dump(
        exclude_unset=True, exclude={"skip", "limit"}, mode="json"
    )

    try:
        response: BondsListResponse = await get_bonds_list(
            filters=filters,
            emitent_title=allowed.get("emitent_title"),
            exclude_spob=filters.exclude_spob,
        )
    except Exception as exc:
        return ToolOutput(
            error=str(exc),
            question="Не удалось получить список облигаций. Попробуйте уточнить условия поиска.",
        )

    total = len(response.bonds or [])
    return ToolOutput(
        data={"total_found": total, "applied_filters": filter_args},
        filters=filter_args,
        summary=f"Найдено выпусков: {total}",
    )


BENCHMARK_NAMES = {
    "RREFKEYR": "Ключевая ставка Банка России",
    "RUONIA": "Ставка RUONIA",
    "RUONIA_IND": "Индекс RUONIA",
    "RUONIA3M": "Срочная ставка RUONIA на 3 месяца",
    "RUONIA6M": "Срочная ставка RUONIA на 6 месяцев",
    "ZR_YLD_CRV": "Кривая бескупонной доходности (КБД)",
    "CPI": "Индекс потребительских цен (ИПЦ)",
    "OTHER": "Прочий индикатор",
}


async def _run_list_coupon_benchmarks(args: Dict[str, Any]) -> ToolOutput:
    """Запрашивает доступные индикаторы в пределах выбранных условий."""
    codes = await asyncio.to_thread(list_coupon_benchmarks, BondFilters(**args.get("filters", {})))
    answer = "По заданным условиям флоатеров с известной базой купона нет."
    if codes:
        entries = [f"- {BENCHMARK_NAMES.get(code, 'Название пока не расшифровано')} (`{code}`)" for code in codes]
        answer = "Базовые индикаторы купона в выбранной группе флоатеров:\n\n" + "\n".join(entries)
    selection = args.get("selection")
    if selection is not None:
        result = await _run_search_bonds({**selection, "require_coupon_benchmark": True})
        if result.is_error:
            return result
        if not result.data["total_found"]:
            answer += "\n\nПо условиям отдельной подборки облигаций не найдено."
        selection = result.filters
    return ToolOutput(data={"benchmarks": codes}, final_answer=answer, filters=selection)


async def _run_get_bond_detail(args: Dict[str, Any]) -> ToolOutput:
    """Детальная информация об одной облигации по SECID."""
    secid = str(args.get("secid") or "").strip()
    if not secid:
        return ToolOutput(
            error="missing_secid",
            question="Укажите, пожалуйста, код ценной бумаги (SECID).",
        )

    dto = await asyncio.to_thread(get_bond_detail, secid)
    if dto is None:
        return ToolOutput(
            error="not_found",
            question=f"Облигация с кодом {secid} не найдена. Проверьте SECID.",
        )

    securities = dto.securities or {}
    marketdata = dto.marketdata or {}
    compact: Dict[str, Any] = {
        "SECID": securities.get("SECID"),
        "SHORTNAME": securities.get("SHORTNAME"),
        "SECNAME": securities.get("SECNAME"),
        "ISIN": securities.get("ISIN"),
        "FACEVALUE": securities.get("FACEVALUE"),
        "FACEUNIT": securities.get("FACEUNIT"),
        "PREVPRICE": securities.get("PREVPRICE"),
        "YIELDATPREVWAPRICE": (
            securities.get("YIELDATPREVWAPRICE")
            if securities.get("YIELDATPREVWAPRICE") is not None
            else marketdata.get("YIELD")
        ),
        "COUPONPERCENT": securities.get("COUPONPERCENT"),
        "COUPONVALUE": securities.get("COUPONVALUE"),
        "NEXTCOUPON": securities.get("NEXTCOUPON"),
        "MATDATE": securities.get("MATDATE"),
        "CURRENCYID": securities.get("CURRENCYID"),
        "RATING_LEVEL": securities.get("RATING_LEVEL"),
        "RATING_AGENCY": securities.get("RATING_AGENCY"),
        "LISTLEVEL": securities.get("LISTLEVEL"),
        "DURATION": marketdata.get("DURATION"),
        "LOTSIZE": securities.get("LOTSIZE"),
        "REGNUMBER": securities.get("REGNUMBER"),
        "BONDTYPE": securities.get("BONDTYPE"),
        "BONDTYPE43": securities.get("BONDTYPE43"),
        "OFFERDATE": securities.get("OFFERDATE"),
        "CALLOPTIONDATE": securities.get("CALLOPTIONDATE"),
        "PUTOPTIONDATE": securities.get("PUTOPTIONDATE"),
    }
    shortname = str(compact.get("SHORTNAME") or "")
    resolved_secid = str(compact.get("SECID") or secid)
    return ToolOutput(
        data={"bond": compact},
        sources=[AgentSource(secid=resolved_secid, shortname=shortname)],
        summary=f"Детальная информация по бумаге {secid}",
    )


async def _run_get_key_rate(args: Dict[str, Any]) -> ToolOutput:
    """Текущая ключевая ставка ЦБ РФ (последнее значение из БД)."""
    service = get_keyrate_service()
    data = await asyncio.to_thread(service.get_keyrate_data)
    if not data:
        return ToolOutput(
            error="no_data",
            question="Данные по ключевой ставке недоступны.",
        )
    latest_date = max(data.keys())
    latest_rate = float(data[latest_date])
    history_tail = [
        {"date": d, "rate": float(data[d])}
        for d in sorted(data.keys())[-5:]
    ]
    return ToolOutput(
        data={
            "key_rate": latest_rate,
            "date": latest_date,
            "history_tail": history_tail,
            "source": "BondsScreener: последнее сохранённое значение ключевой ставки Банка России",
            "retrieved_on": date.today().isoformat(),
        },
        sources=[],
        summary=f"Ключевая ставка ЦБ РФ на {latest_date}: {latest_rate}% годовых",
    )


async def _run_get_coupons(args: Dict[str, Any]) -> ToolOutput:
    """График купонных выплат по облигации (ближайшие купоны)."""
    secid = str(args.get("secid") or "").strip()
    if not secid:
        return ToolOutput(
            error="missing_secid",
            question="Укажите, пожалуйста, код ценной бумаги (SECID).",
        )
    try:
        service = get_coupon_service()
        data = await asyncio.to_thread(service.get_coupons, secid)
    except Exception as exc:
        return ToolOutput(
            error=str(exc),
            question="Не удалось получить данные по купонам. Попробуйте другой SECID.",
        )

    coupons = data.get("coupons", [])
    today = date.today()
    upcoming = []
    for coupon in coupons:
        cd = str(coupon.get("coupondate") or "")
        if cd and cd[:10] >= today.isoformat():
            upcoming.append(
                {
                    "coupondate": cd[:10],
                    "value": coupon.get("value"),
                    "valueprc": coupon.get("valueprc"),
                    "faceunit": coupon.get("faceunit"),
                }
            )
    upcoming.sort(key=lambda c: str(c.get("coupondate") or ""))
    truncated = len(upcoming) > MAX_COUPONS_TO_LLM
    upcoming = upcoming[:MAX_COUPONS_TO_LLM]
    shortname = str(coupons[0].get("shortname") or "") if coupons else ""
    return ToolOutput(
        data={"secid": secid, "coupons": upcoming, "truncated": truncated},
        sources=[AgentSource(secid=secid, shortname=shortname)],
        summary=f"Ближайшие купоны {secid}: {len(upcoming)} выплат",
    )


TOOL_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "search_bonds": _run_search_bonds,
    "list_coupon_benchmarks": _run_list_coupon_benchmarks,
    "get_bond_detail": _run_get_bond_detail,
    "get_key_rate": _run_get_key_rate,
    "get_coupons": _run_get_coupons,
}

TOOL_SCHEMAS: Dict[str, Dict[str, str]] = {
    "list_coupon_benchmarks": {
        "description": "Доступные базы купона по данным таблицы описаний флоатеров.",
        "args_text": "filters — условия справки; selection — необязательная дополнительная подборка.",
    },
    "search_bonds": {
        "description": (
            "Поиск облигаций на Мосбирже по финансовым фильтрам. "
            "Используйте, когда нужно подобрать бумаги по доходности, купону, "
            "дате погашения, рейтингу, типу или эмитенту."
        ),
        "args_text": _filters_args_text(),
    },
    "get_bond_detail": {
        "description": (
            "Детальная информация об одной облигации (купон, цена, доходность, "
            "рейтинг, параметры выпуска). Используй для вопросов «расскажи про "
            "бумагу», «что за облигация». Принимает SECID или ISIN указанного "
            "выпуска. Если по коду ничего не найдено — НЕ отвечай по памяти, "
            "сообщи об этом и попроси пользователя уточнить SECID."
        ),
        "args_text": (
            "- `secid` (string): код ценной бумаги на Мосбирже (SECID) или ISIN выпуска"
        ),
    },
    "get_key_rate": {
        "description": (
            "Последнее сохранённое в BondsScreener значение ключевой ставки Банка России "
            "вместе с датой записи. Актуальность на сегодня не гарантируется."
        ),
        "args_text": "Аргументы не требуются (пустой объект {}).",
    },
    "get_coupons": {
        "description": (
            "График ближайших купонных выплат по облигации. Требует точный SECID."
        ),
        "args_text": "- `secid` (string): код ценной бумаги на Мосбирже",
    },
}


def build_tools_catalog_text() -> str:
    """Формирует текстовый каталог инструментов для системного промпта."""
    lines: List[str] = []
    for name, schema in TOOL_SCHEMAS.items():
        lines.append(f"### {name}")
        lines.append(schema["description"])
        lines.append("Аргументы JSON:")
        lines.append(schema["args_text"])
        if name != "search_bonds":
            lines.append(json.dumps(tool_args_schema(name), ensure_ascii=False, indent=2))
        lines.append("")
    return "\n".join(lines)
