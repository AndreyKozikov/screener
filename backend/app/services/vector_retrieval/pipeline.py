import logging
import re
from typing import List, Dict, Any, Optional
from .models import Chunk, EmbeddedChunk, ScoredChunk
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService
from .retrieval_engine import RetrievalEngine
from .ranking_engine import RankingEngine
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    # Legacy default queries (kept for reference):
    # "Формула расчета купона, порядок определения ставки купона",
    # "Базовый индикатор, ключевая ставка, RUONIA, спред, премия к ставке",
    # "Ограничения ставки купона, минимальная и максимальная ставка (floor, cap)",
    # "Правила фиксации ставки, периоды наблюдения, даты определения индикатора",
    # "Условия изменения параметров выпуска, события, влияющие на расчет купона",
    "Итоги размещения выпуска: ставка купона, спред, премия к базовой ставке, книга заявок",
    "Сообщение о начисленных доходах по эмиссионным ценным бумагам: размер и порядок определения купона",
    "Порядок определения процентной ставки по i-му купону: формула и переменные расчета",
    "Базовый индикатор купона: ключевая ставка, RUONIA, RUSFAR, CPI, КБД ОФЗ",
    "Дата фиксации индикатора: T-5 или T-7, рабочие или календарные дни, lookback",
    "Правило при отсутствии значения индикатора: предыдущее, следующее, последнее опубликованное",
    "Конвенция day count и база года: ACT/365, ACT/366, 30/360, ACTUAL",
    "Тип начисления купона: DAILY_ACCRUAL или FIXED_PERIOD, порядок расчета НКД",
    "Ограничения купона: минимальная ставка floor, максимальная ставка cap, пороги и условия",
    "Период наблюдения и усреднение: POINT, AVERAGE, INTERVAL, reference period",
    "Условия изменения параметров выпуска: оферта, пересмотр эмитентом, новые правила после даты",
    "Формулы с несколькими индикаторами: основной индикатор и дополнительные индексы",
]

class RetrievalPipeline:
    def __init__(self):
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()
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
        queries: Optional[List[str]] = None
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
            # Фильтруем чанки с календарями/таблицами периодов
            filtered_doc_chunks = [c for c in doc_chunks if not self._is_calendar_table(c.text)]
            all_chunks.extend(filtered_doc_chunks)
            
        event_chunks = self.chunker.chunk_events(events)
        filtered_event_chunks = [c for c in event_chunks if not self._is_calendar_table(c.text)]
        all_chunks.extend(filtered_event_chunks)
        
        logger.info("Created %d chunks total", len(all_chunks))
        
        # 2. Embedding
        # Pre-embed queries (Hybrid: Dense + Sparse)
        query_data = [self.embedder.embed_query(q) for q in queries]
        
        # Embed chunks (sentence-level, Hybrid)
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
            query_data,
            top_k=30,
            alpha=0.5 # Баланс между семантикой и лексикой
        )
        
        logger.info("Retrieved top %d candidates", len(retrieved_chunks))
        
        # 4. Ranking
        ranked_chunks = self.ranker.rerank(retrieved_chunks)
        
        # 5. Final Selection (top 10-15)
        final_chunks = [sc.chunk for sc in ranked_chunks[:15]]
        
        logger.info("Final selection: %d chunks", len(final_chunks))
        
        # 6. Build Context
        return self.builder.build(final_chunks)
