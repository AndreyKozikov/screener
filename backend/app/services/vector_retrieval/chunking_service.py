import re
from typing import List, Optional
from .models import Chunk

class ChunkingService:
    def __init__(self, chunk_size: int = 3000, overlap: int = 500):
        # Using character counts as approximation for tokens (1 token ~ 4 chars)
        # 700 tokens ~ 2800 chars. 500-900 tokens -> 2000-3600 chars.
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_markdown(self, markdown: str, source_id: str) -> List[Chunk]:
        """
        Разбивает markdown по структуре документа (заголовкам).
        Сохраняет целостность таблиц и формул.
        """
        if not markdown:
            return []

        # Split by headers: #, ##, ###, ####
        # We use a regex that keeps the header in the split part
        parts = re.split(r'(^#+\s+.*$)', markdown, flags=re.MULTILINE)
        
        chunks = []
        current_chunk_text = ""
        current_section = "Root"
        
        # parts will look like ["text before first header", "# Header 1", "text after header 1", ...]
        i = 0
        while i < len(parts):
            part = parts[i]
            if not part.strip():
                i += 1
                continue
                
            if part.startswith("#"):
                # If we have a header, update current section and add to text
                # But first, if current_chunk_text is large enough, save it
                if len(current_chunk_text) > self.chunk_size:
                    chunks.append(Chunk(
                        text=current_chunk_text,
                        source_type="markdown",
                        source_id=source_id,
                        section=current_section
                    ))
                    # Keep some overlap if possible, but headers usually start new blocks
                    # For simplicity, we just start fresh with the new header
                    current_chunk_text = ""
                
                new_section = part.strip()
                # If we have a previous chunk that isn't empty, and we are starting a new section,
                # we might want to close the old one.
                # However, the user wants 500-900 tokens. 
                # If the section is small, we can combine it with the next one.
                
                # Update section for the next block
                current_section = new_section
                current_chunk_text += part + "\n"
            else:
                # Regular text
                # Check if adding this part exceeds chunk_size
                if len(current_chunk_text) + len(part) > self.chunk_size:
                    # If current chunk is already meaningful, save it
                    if current_chunk_text.strip():
                        chunks.append(Chunk(
                            text=current_chunk_text,
                            source_type="markdown",
                            source_id=source_id,
                            section=current_section
                        ))
                        # Start new chunk with overlap from the end of current_chunk_text
                        overlap_text = current_chunk_text[-self.overlap:] if len(current_chunk_text) > self.overlap else ""
                        current_chunk_text = overlap_text + part
                    else:
                        # Part itself is too large, split it? 
                        # User says "не допускается дробить формулы, таблицы".
                        # Tables in markdown usually start with | and end with \n\n
                        # We should try to split by double newline first.
                        sub_parts = part.split("\n\n")
                        for sp in sub_parts:
                            if len(current_chunk_text) + len(sp) > self.chunk_size:
                                if current_chunk_text.strip():
                                    chunks.append(Chunk(
                                        text=current_chunk_text,
                                        source_type="markdown",
                                        source_id=source_id,
                                        section=current_section
                                    ))
                                    overlap_text = current_chunk_text[-self.overlap:] if len(current_chunk_text) > self.overlap else ""
                                    current_chunk_text = overlap_text + sp + "\n\n"
                                else:
                                    # Still too large? Just add it and it will be a large chunk.
                                    # Better than breaking a table.
                                    current_chunk_text = sp + "\n\n"
                            else:
                                current_chunk_text += sp + "\n\n"
                else:
                    current_chunk_text += part
            i += 1
            
        if current_chunk_text.strip():
            chunks.append(Chunk(
                text=current_chunk_text,
                source_type="markdown",
                source_id=source_id,
                section=current_section
            ))
            
        return chunks

    def chunk_events(self, events: List[dict]) -> List[Chunk]:
        """
        Преобразует events в текстовые чанки. 1 event = 1 chunk.
        """
        chunks = []
        for ev in events:
            # Format event as text
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
