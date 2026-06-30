from app.processors.events_processor import EventsProcessor
from app.processors.bond_llm_processor import BondLLMProcessor

from pathlib import Path
from typing import Optional

events_processor: Optional[EventsProcessor] = None
bond_llm_processor: Optional[BondLLMProcessor] = None

def init_events_processor(db_path: Path, path: Path) -> None:
    global events_processor
    events_processor = EventsProcessor(db_path, path)

def get_events_processor() -> EventsProcessor:
    if events_processor is None:
        raise RuntimeError("EventsProcessor not initialized. Call init_events_processor first.")
    return events_processor

def init_bond_llm_processor(path: Path) -> None:
    global bond_llm_processor
    bond_llm_processor = BondLLMProcessor(path)

def get_bond_llm_processor() -> BondLLMProcessor:
    if bond_llm_processor is None:
        raise RuntimeError("EventsProcessor not initialized. Call init_events_processor first.")
    return bond_llm_processor