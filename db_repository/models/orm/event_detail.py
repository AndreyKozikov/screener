from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class EventDetail(SQLModel, table=True):
    __tablename__ = "events_details"
    __table_args__ = (
        UniqueConstraint("pseudo_guid", "event_date", name="uq_events_details_guid_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    emitent_inn: Optional[str] = Field(default=None, index=True)
    pseudo_guid: str = Field(index=True)
    event_date: date = Field(index=True)
    registration_number: Optional[str] = Field(default=None)
    issue_registration_number: Optional[str] = Field(default=None)
    isin: Optional[str] = Field(default=None)
    series: Optional[str] = Field(default=None)
    security_type: Optional[str] = Field(default=None)
    message_type: Optional[str] = Field(default=None)
    event_type: Optional[str] = Field(default=None)
    publication_date: Optional[str] = Field(default=None)
    is_edit: int = Field(default=0)
