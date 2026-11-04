"""Validated router decisions and tool arguments shared with the prompt catalog."""

import json
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator

from app.models import BondFilters

# Единая национальная шкала рейтингов (АКРА/Эксперт РА и аналоги), от высшего
# к низшему. Должна совпадать с db_repository/config/constants.py RATINGS_ORDER.
# Держим локальную копию: backend запускается как отдельный сервис (main:app из
# каталога backend/) и не должен импортировать db_repository в момент старта.
RATINGS_ORDER: List[str] = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
]


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchBondsArgs(BondFilters):
    model_config = ConfigDict(extra="forbid")

    coupon_months: Optional[List[Annotated[int, Field(ge=1, le=12)]]] = Field(
        default=None,
        description="Будущая выплата хотя бы в одном месяце (1-12), любого года; не все месяцы и не конкретный год",
        min_length=1,
    )
    bondtype: Optional[List[Annotated[int, Field(ge=1, le=5)]]] = Field(default=None, min_length=1)
    bondtype43: Optional[List[Annotated[int, Field(ge=1, le=9)]]] = Field(default=None, min_length=1)
    listlevel: Optional[List[Annotated[int, Field(ge=1, le=3)]]] = Field(default=None, min_length=1)
    faceunit: Optional[List[NonEmptyText]] = Field(
        default=None, min_length=1, description="Валюты номинала: SUR (рубли), USD, EUR и т.д."
    )
    emitent_title: Optional[NonEmptyText] = Field(
        default=None, description="Точное название эмитента в данных сервиса для фильтрации облигаций"
    )
    rating_min: Optional[Literal[tuple(RATINGS_ORDER)]] = Field(
        default=None, description="Указанный рейтинг и все более высокие (не ниже)"
    )
    rating_max: Optional[Literal[tuple(RATINGS_ORDER)]] = Field(
        default=None, description="Указанный рейтинг и все более низкие (не выше)"
    )

    @model_validator(mode="after")
    def check_ranges(self) -> "SearchBondsArgs":
        for low, high in (
            (self.coupon_min, self.coupon_max),
            (self.yield_min, self.yield_max),
            (self.coupon_yield_min, self.coupon_yield_max),
            (self.matdate_from, self.matdate_to),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError("Lower range bound must not exceed upper bound")
        if self.rating_min and self.rating_max:
            if RATINGS_ORDER.index(self.rating_min) < RATINGS_ORDER.index(self.rating_max):
                raise ValueError("Rating bounds describe an empty range")
        if self.exclude_amortized and self.bondtype43 and 1 in self.bondtype43:
            raise ValueError("Amortized bonds cannot be requested and excluded together")
        return self


class SecidArgs(ToolArgs):
    secid: NonEmptyText


class RagArgs(SecidArgs):
    query: NonEmptyText


TOOL_ARG_MODELS = {
    "search_bonds": SearchBondsArgs,
    "get_bond_detail": SecidArgs,
    "get_key_rate": ToolArgs,
    "get_coupons": SecidArgs,
    "bond_rag_query": RagArgs,
}


def tool_args_schema(tool: str) -> Dict[str, Any]:
    schema = TOOL_ARG_MODELS[tool].model_json_schema()
    if tool == "search_bonds":
        for name in ("skip", "limit"):
            schema["properties"].pop(name, None)
        # Optional filters are omitted, not passed as null/no-op conditions.
        for prop in schema["properties"].values():
            choices = [item for item in prop.get("anyOf", []) if item.get("type") != "null"]
            if len(choices) == 1:
                prop.pop("anyOf")
                prop.update(choices[0])
            if prop.get("default", False) is None:
                prop.pop("default")
    return schema


def validate_tool_args(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool not in TOOL_ARG_MODELS:
        raise ValueError(f"Unknown tool: {tool}")
    if not isinstance(args, dict):
        raise ValueError("Tool args must be a JSON object")
    if tool == "search_bonds" and {"skip", "limit"}.intersection(args):
        raise ValueError("Pagination arguments skip/limit are not available to the agent")
    if tool == "search_bonds" and any(value is None for value in args.values()):
        raise ValueError("Omit unspecified filters instead of passing null")
    # JSON-mode strict validation permits ISO dates, but rejects scalar/list and
    # string/number coercions that could silently change a filter's meaning.
    validated = TOOL_ARG_MODELS[tool].model_validate_json(
        json.dumps(args, ensure_ascii=False, allow_nan=False), strict=True
    )
    return validated.model_dump(mode="json", exclude_unset=True)


class AskDecision(ToolArgs):
    intent: Literal["ask"]
    question: NonEmptyText
    missing_filters: List[str]


class ToolDecision(ToolArgs):
    intent: Literal["tool"]
    tool: Literal["search_bonds", "get_bond_detail", "get_key_rate", "get_coupons", "bond_rag_query"]
    args: Dict[str, Any]


class AnswerDecision(ToolArgs):
    intent: Literal["answer"]
    answer_markdown: NonEmptyText
    sources: List[Any] = Field(max_length=0)


ROUTER_DECISION = TypeAdapter(
    Annotated[Union[AskDecision, ToolDecision, AnswerDecision], Field(discriminator="intent")]
)


def validate_router_decision(value: Dict[str, Any]) -> Dict[str, Any]:
    decision = ROUTER_DECISION.validate_python(value, strict=True)
    result = decision.model_dump()
    if isinstance(decision, ToolDecision):
        result["args"] = validate_tool_args(decision.tool, decision.args)
    elif isinstance(decision, AskDecision):
        allowed = (set(SearchBondsArgs.model_fields) - {"skip", "limit"}) | {"secid", "query"}
        unknown = set(decision.missing_filters) - allowed
        if unknown:
            raise ValueError(f"Unknown missing_filters: {sorted(unknown)}")
    return result
