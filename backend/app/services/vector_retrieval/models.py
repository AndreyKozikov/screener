from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Chunk:
    text: str
    source_type: str  # "markdown" | "event"
    source_id: str
    section: Optional[str] = None

@dataclass
class EmbeddedChunk:
    chunk: Chunk
    sentence_embeddings: List[List[float]]

@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
