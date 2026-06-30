import logging
import re
from typing import List, Dict, Any, Optional
from .models import Chunk, EmbeddedChunk, ScoredChunk
from .chunking_service import ChunkingService
from .embedding_models import DEFAULT_EMBEDDING_MODEL, normalize_embedding_model
from .embedding_provider_factory import get_embedding_provider
from .retrieval_engine import RetrievalEngine
from .ranking_engine import RankingEngine
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    def __init__(self):
        self.chunker = ChunkingService()
        self.retriever = RetrievalEngine()
        self.ranker = RankingEngine()
        self.builder = ContextBuilder()

    def _is_calendar_table(self, text: str) -> bool:
        """
        Проверяет, является ли текст таблицей календаря/периодов.
        Такие чанки обычно содержат много дат и слово 'период'.
        """
        date_pattern = r'\d{2}\.\d{2}\.\d{4}'
        dates = re.findall(date_pattern, text)
        
        # Если в чанке более 4 дат и есть слово 'период' - это скорее всего таблица
        if len(dates) > 4 and ("период" in text.lower()):
            return True
        return False

    def run(
        self, 
        markdown_docs: List[Dict[str, str]], 
        events: List[Dict[str, Any]], 
        queries: Optional[List[str]] = None,
        embedding_model: Optional[str] = DEFAULT_EMBEDDING_MODEL,
    ) -> str:
        """
        Основной пайплайн векторного поиска и формирования контекста.
        """

        normalized_embedding_model = normalize_embedding_model(embedding_model)
        embedder = get_embedding_provider(normalized_embedding_model)
        retrieval_alpha = 0.8 if getattr(embedder, "supports_sparse", True) else 1.0

        logger.info(
            "Starting RetrievalPipeline. Processing %d docs and %d events. embedding_model=%s alpha=%.1f",
            len(markdown_docs),
            len(events),
            normalized_embedding_model,
            retrieval_alpha,
        )
        
        # 1. Chunking
        all_chunks: List[Chunk] = []
        for doc in markdown_docs:
            doc_chunks = self.chunker.chunk_markdown(
                doc["content"], 
                source_id=doc["filename"]
            )
            # Фильтруем чанки с календарями/таблицами периодов
            #filtered_doc_chunks = [c for c in doc_chunks if not self._is_calendar_table(c.text)]
            filtered_doc_chunks = doc_chunks
            all_chunks.extend(filtered_doc_chunks)
            
        event_chunks = self.chunker.chunk_events(events)
        filtered_event_chunks = event_chunks
        #filtered_event_chunks = [c for c in event_chunks if not self._is_calendar_table(c.text)]
        all_chunks.extend(filtered_event_chunks)
        
        logger.info("Created %d chunks total", len(all_chunks))
        
        # 2. Embedding
        # Pre-embed queries (Hybrid: Dense + Sparse)
        query_data = [embedder.embed_query(q) for q in queries]
        
        # Embed chunks (sentence-level, Hybrid)
        embedded_chunks: List[EmbeddedChunk] = []
        total_chunks = len(all_chunks)
        for i, chunk in enumerate(all_chunks, start=1):
            print(
                f"  [VECTOR] Embedding chunk {i}/{total_chunks} "
                f"({normalized_embedding_model})...",
                flush=True,
            )
            embedded = embedder.embed_chunk(chunk)
            embedded_chunks.append(embedded)

        logger.info("Embeddings generated for all chunks")

        # 3. Retrieval (раздельный поиск для документов и событий)
        # Разделяем эмбеддинги на документы и события, чтобы они не конкурировали друг с другом
        markdown_embedded = [ec for ec in embedded_chunks if ec.chunk.source_type == "markdown"]
        event_embedded = [ec for ec in embedded_chunks if ec.chunk.source_type == "event"]

        retrieved_docs = []
        if markdown_embedded:
            retrieved_docs = self.retriever.retrieve(
                markdown_embedded,
                query_data,
                top_k=30,
                alpha=retrieval_alpha # Баланс между семантикой и лексикой
            )

        retrieved_events = []
        if event_embedded:
            # Забираем все найденные события без предварительного отсечения по score документов
            retrieved_events = self.retriever.retrieve(
                event_embedded,
                query_data,
                top_k=30,
                #top_k=len(event_embedded),
                alpha=retrieval_alpha
            )

        retrieved_chunks = retrieved_docs + retrieved_events

        logger.info(
            "Retrieved %d candidates (%d docs, %d events)",
            len(retrieved_chunks), len(retrieved_docs), len(retrieved_events)
        )

        # 4. Ranking
        ranked_chunks = self.ranker.rerank(retrieved_chunks)

        # 5. Final Selection (top 15-20 для документов, все найденные события без отсечения)
        # Для документов оставляем ограничение (до 20), так как MMR эффективно дедуплицирует их.
        # Для событий исключаем отсечение и передаем все найденные векторным поиском события.
        final_markdown_chunks = [sc.chunk for sc in ranked_chunks if sc.chunk.source_type == "markdown"][:20]
        final_event_chunks = [sc.chunk for sc in ranked_chunks if sc.chunk.source_type == "event"]

        final_chunks = final_markdown_chunks + final_event_chunks

        logger.info(
            "Final selection: %d chunks (%d docs, %d events)",
            len(final_chunks), len(final_markdown_chunks), len(final_event_chunks)
        )

        # 6. Build Context
        return self.builder.build(final_chunks)
