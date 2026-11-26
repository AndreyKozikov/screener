from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventVersion(Record):
    event_key: str
    chunk_id: str
    write_id: str


class DatedEvent(EventVersion):
    event_date: date
    event_year: int
    is_corrected_by_another_event: bool


class BondEventMap(DatedEvent):
    bond_secid: str
    bond_isin: str
    bond_reg_number: str | None
    bond_series: str | None
    bond_first_tradedate: date | None
    issuename: str | None = None
    bond_event_write_key: str
    bond_event_key: str
    chunk_write_key: str
    match_reason: Literal["secid", "reg_number", "series", "issuename"]
    source_index: int = Field(ge=0)


class EventChunk(DatedEvent):
    event_write_key: str
    pseudo_guid: str
    text: str
    source_type: Literal["event"]
    source_id: str
    event_name: str
    text_pipeline_version: str
    created_at: datetime


class EventVector(EventVersion):
    sentence_id: str
    chunk_write_key: str
    sentence_index: int = Field(ge=0)
    sentence_text: str
    vector: list[FiniteFloat] = Field(min_length=1)
    terms: list[str]
    weights: list[FiniteFloat]
    created_at: datetime

    @model_validator(mode="after")
    def check_weights(self):
        if len(self.terms) != len(self.weights):
            raise ValueError("Количество терминов и лексических весов различается")
        return self


class EventState(Record):
    event_key: str
    active_write_id: str | None
    status: Literal["active", "orphan", "deleted", "recovering"]
    committed_at: datetime
    commit_seq: int = Field(ge=0)


class BondIndexState(Record):
    bond_secid: str
    indexed_at: datetime


class IndexMeta(Record):
    model_id: str
    embedding_dim: int = Field(gt=0)
    alpha: float = Field(ge=0, le=1)
    supports_sparse: bool
    sparse_source: str
    sentence_splitter_version: str
    text_pipeline_version: str
    series_source: str
    series_extractor_version: str
    commit_protocol_version: str
    schema_version: str
    built_at: datetime
    fingerprint: str
    catalog_epoch: int = Field(ge=0)


TABLE_MODELS = {
    "bond_event_map": BondEventMap,
    "event_chunks": EventChunk,
    "event_vectors": EventVector,
    "event_state": EventState,
    "bond_index_state": BondIndexState,
    "index_meta": IndexMeta,
}
