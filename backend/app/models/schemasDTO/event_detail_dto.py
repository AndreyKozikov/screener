"""Pydantic write contract for event details sent to the repository service."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventDetailRecordDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emitent_inn: Optional[str] = None
    pseudo_guid: str
    event_date: date
    registration_number: Optional[str] = None
    issue_registration_number: Optional[str] = None
    isin: Optional[str] = None
    series: Optional[str] = None
    security_type: Optional[str] = None
    message_type: Optional[str] = None
    event_type: Optional[str] = None
    publication_date: Optional[str] = None
