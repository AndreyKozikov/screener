from typing import List
from .models import Chunk

class ContextBuilder:
    def build(self, chunks: List[Chunk]) -> str:
        """
        Формирует финальный prompt для LLM.
        Группирует события и документы.
        """
        events = [c for c in chunks if c.source_type == "event"]
        documents = [c for c in chunks if c.source_type == "markdown"]
        
        lines = []
        
        if events:
            lines.append("=== EVENTS ===")
            for ev in events:
                lines.append(ev.text)
                lines.append("-" * 20)
            lines.append("")
            
        if documents:
            lines.append("=== DOCUMENTS ===")
            for doc in documents:
                source_info = f"[source: {doc.source_id}"
                if doc.section:
                    source_info += f" | section: {doc.section}"
                source_info += "]"
                
                lines.append(source_info)
                lines.append(doc.text)
                lines.append("-" * 20)
                
        return "\n".join(lines)
