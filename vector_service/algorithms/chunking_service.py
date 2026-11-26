from typing import List
from .models import Chunk


class ChunkingService:
    def chunk_events(self, events: List[dict]) -> List[Chunk]:
        """
        Преобразует events в текстовые чанки. 1 event = 1 chunk.
        """
        chunks = []
        for ev in events:
            # Формируем текст события
            event_text = f"Тип события: {ev.get('event_name', 'н/д')}\n"
            event_text += f"Дата: {ev.get('event_date', 'н/д')}\n"
            event_text += f"Описание: {ev.get('text', '')}"
            
            chunks.append(Chunk(
                text=event_text,
                source_type="event",
                source_id=f"event_{ev.get('event_date', '0')}",
                section=ev.get('event_name')
            ))
        return chunks
