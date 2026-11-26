from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(pattern=r"\S")]


class BondInput(BaseModel):
    secid: Text
    isin: Text
    inn: Text | None = None
    secname: str | None = None
    issuename: str | None = None
    reg_number: str | None = None
    first_tradedate: date | None = None


class EventInput(BaseModel):
    event_key: Text
    inn: Text
    pseudo_guid: Text
    source_index: int = Field(strict=True, ge=0)
    event_name: Text
    event_date: date
    full_text: str
    is_corrected_by_another_event: bool = Field(strict=True)


class IngestRequest(BaseModel):
    inn: Text
    bonds: list[BondInput]
    events: list[EventInput]


class IngestResult(BaseModel):
    indexed: int = 0
    skipped_invalid: int = 0
    skipped_no_match: int = 0
    skipped_inn_mismatch: int = 0


class BondQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secid: Text | None = None
    isin: Text | None = None
    reg_number: str | None = None
    series: str | None = None

    @model_validator(mode="after")
    def require_identifier(self):
        if not (self.secid or self.isin):
            raise ValueError("Требуется SECID или ISIN")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bond: BondQuery
    queries: list[Text] = Field(min_length=1)
    request_id: str | None = None
    start_date: date | None = None
    provider: Literal["local", "openrouter"] = "local"


class SearchHit(BaseModel):
    chunk_id: str
    event_key: str
    event_name: str
    event_date: date
    source_id: str
    text: str
    is_corrected_by_another_event: bool
    score: float


class SearchResult(BaseModel):
    request_id: str
    status: Literal["ok", "not_indexed"]
    bond_secid: str
    bond_isin: str | None
    index_fingerprint: str
    snapshot_id: str
    elapsed_ms: int
    results: list[SearchHit]
    context: str
