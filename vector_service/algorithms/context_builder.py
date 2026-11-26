from typing import List
from .models import Chunk


class ContextBuilder:
    def build(self, chunks: List[Chunk]) -> str:
        """
        Формирует контекст для LLM в Markdown-формате.
        Оптимизировано для GPT и Gemini.
        """

        events = [c for c in chunks if c.source_type == "event"]
        documents = [c for c in chunks if c.source_type == "markdown"]

        lines = []

        if events:
            lines.extend([
                "# EVENTS",
                ""
            ])

            for ev in events:
                lines.extend([
                    "## EVENT",
                    "",
                    f"- ID: {ev.source_id}",
                ])

                if ev.section:
                    lines.append(f"- TITLE: {ev.section}")

                lines.extend([
                    "",
                    ev.text.strip(),
                    ""
                ])

        if documents:
            lines.extend([
                "# DOCUMENTS",
                ""
            ])

            for doc in documents:
                lines.extend([
                    "## DOCUMENT",
                    "",
                    f"- ID: {doc.source_id}",
                ])

                if doc.section:
                    lines.append(f"- SECTION: {doc.section}")

                lines.extend([
                    "",
                    doc.text.strip(),
                    ""
                ])

        return "\n".join(lines).strip()