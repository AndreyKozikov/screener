import logging
from typing import List, Dict, Any
from .models import Chunk, EmbeddedChunk, ScoredChunk
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService
from .retrieval_engine import RetrievalEngine
from .ranking_engine import RankingEngine
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "Формула расчета купона, порядок определения ставки купона",
    "Базовый индикатор, ключевая ставка, RUONIA, спред, премия к ставке",
    "Ограничения ставки купона, минимальная и максимальная ставка (floor, cap)",
    "Правила фиксации ставки, периоды наблюдения, даты определения индикатора",
    "Условия изменения параметров выпуска, события, влияющие на расчет купона"
]

class RetrievalPipeline:
    def __init__(self):
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()
        self.retriever = RetrievalEngine()
        self.ranker = RankingEngine()
        self.builder = ContextBuilder()

    def run(
        self, 
        markdown_docs: List[Dict[str, str]], 
        events: List[Dict[str, Any]], 
        queries: List[str] = None
    ) -> str:
        """
        Основной пайплайн векторного поиска и формирования контекста.
        """
        if queries is None:
            queries = DEFAULT_QUERIES
            
        logger.info("Starting RetrievalPipeline. Processing %d docs and %d events", 
                    len(markdown_docs), len(events))
        
        # 1. Chunking
        all_chunks: List[Chunk] = []
        for doc in markdown_docs:
            doc_chunks = self.chunker.chunk_markdown(
                doc["content"], 
                source_id=doc["filename"]
            )
            all_chunks.extend(doc_chunks)
            
        event_chunks = self.chunker.chunk_events(events)
        all_chunks.extend(event_chunks)
        
        logger.info("Created %d chunks total", len(all_chunks))
        
        # 2. Embedding
        # Pre-embed queries
        query_embeddings = [self.embedder.embed_query(q) for q in queries]
        
        # Embed chunks (sentence-level)
        embedded_chunks: List[EmbeddedChunk] = []
        total_chunks = len(all_chunks)
        for i, chunk in enumerate(all_chunks, start=1):
            print(f"  [VECTOR] Embedding chunk {i}/{total_chunks}...", flush=True)
            embedded = self.embedder.embed_chunk(chunk)
            embedded_chunks.append(embedded)
            
        logger.info("Embeddings generated for all chunks")
        
        # 3. Retrieval
        retrieved_chunks: List[ScoredChunk] = self.retriever.retrieve(
            embedded_chunks,
            query_embeddings,
            top_k=30
        )
        
        logger.info("Retrieved top %d candidates", len(retrieved_chunks))
        
        # 4. Ranking
        ranked_chunks = self.ranker.rerank(retrieved_chunks)
        
        # 5. Final Selection (top 10-15)
        final_chunks = [sc.chunk for sc in ranked_chunks[:15]]
        
        logger.info("Final selection: %d chunks", len(final_chunks))
        
        # 6. Build Context
        return self.builder.build(final_chunks)
