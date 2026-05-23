"""Сервис векторного поиска и формирования контекста для анализа облигаций.

Обеспечивает сбор текстовой информации из различных источников (Markdown документы,
лента раскрытия информации E-disclosure), фильтрацию по релевантности и запуск
конвейера векторного поиска для подготовки контекста LLM-запросов.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.services.bonds_service import (
    get_emitent_inn_by_secid,
    get_reg_number_by_secid,
    get_bond_id_by_secid
)
from app.services.edisclosure_service import EdisclosureService
from app.services.llm_prompt_pipeline_service import LlmPromptPipelineService, _markdown_has_any_required_header, _filename_excluded_from_pipeline
from app.repository.files.file_storage import FileStorage
from app.parsers.emission_series_parser import (
    extract_series_from_markdown,
    filter_events_by_secid_regnumber_series,
    markdown_has_decision_header,
)
from app.utils.edisclosure_utils import (
    clean_event_text,
    get_events_with_full_text_for_year,
)
from app.services.trading_history_service import get_trading_history_service

from .vector_retrieval.pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

class VectorRetrievalService:
    """Сервис векторного поиска контекста.

    Агрегирует данные по конкретной облигации, фильтрует нерелевантные документы
    и события, после чего использует RetrievalPipeline для отбора наиболее
    значимых фрагментов текста (чанков) на основе семантического сходства.

    Attributes:
        edisclosure_service (EdisclosureService): Сервис для работы с лентой новостей эмитентов.
        file_storage (FileStorage): Компонент для чтения локальных Markdown файлов.
        pipeline (RetrievalPipeline): Конвейер векторного поиска и ранжирования.
    """

    def __init__(self):
        """Инициализирует сервис векторного поиска."""
        self.edisclosure_service = EdisclosureService()
        self.file_storage = FileStorage()
        self.pipeline = RetrievalPipeline()

    def get_context_for_bond(
        self,
        secid: str, 
        regnumber: Optional[str] = None,
        use_local_events: bool = False,
        query: Optional[str] = None
    ) -> str:
        """Собирает данные по облигации и формирует векторный контекст.

        Процесс включает:
        1. Получение метаданных (ИНН, рег. номер) и ID компании в E-disclosure.
        2. Загрузку и фильтрацию локальных Markdown-документов (решения, проспекты).
        3. Загрузку и фильтрацию событий существенных фактов.
        4. Запуск векторного поиска (RAG) для отбора наиболее релевантных чанков.

        Args:
            secid: Идентификатор облигации (SECID).
            regnumber: Государственный регистрационный номер выпуска.
            use_local_events: Если True, загружает события из локальных файлов,
                иначе — через API E-disclosure.
            query: Текстовый запрос для семантического поиска. Если не указан,
                используется стандартный алгоритм ранжирования.

        Returns:
            Строка, содержащая отобранный текстовый контекст в формате Markdown.

        Raises:
            ValueError: Если не найден ИНН для указанного SECID.
        """
        secid = secid.strip()
        inn = get_emitent_inn_by_secid(secid)
        if not inn:
            raise ValueError(f"ИНН для {secid} не найден")
            
        if not regnumber:
            regnumber = get_reg_number_by_secid(secid)
            
        # 1. Resolve company_id
        company_id, _ = self.edisclosure_service._resolve_company_id_by_inn(inn)
        
        # 2. Find first trade date for events
        trading_service = get_trading_history_service()
        first_tradedate = trading_service.get_first_tradedate(secid)
        date_str = first_tradedate.isoformat() if first_tradedate else "2025-04-24"
        
        # 3. Collect and filter Markdown files
        bond_data_dir = _DATA_DIR / secid
        markdown_docs = []
        series = None
        
        if bond_data_dir.is_dir():
            all_md_files = list(bond_data_dir.glob("*.md"))
            for md_path in all_md_files:
                # Фильтры исключения (регистронезависимые)
                filename_lower = md_path.name.lower()
                if "отчетность мсфо" in filename_lower or "отчетность рсбу" in filename_lower or filename_lower == "vector_context.md":
                    logger.info(f"Исключен файл по имени: {md_path.name}")
                    continue
                    
                try:
                    md_content = self.file_storage.read_text_file(md_path)
                    
                    # Проверка начала файла на наличие исключаемых фраз
                    content_prefix = md_content[:1000].lower()
                    if "учетная политика" in content_prefix or \
                       "бухгалтерская отчетность" in content_prefix or \
                       "консолидированная отчетность" in content_prefix:
                        logger.info(f"Исключен файл по содержимому: {md_path.name}")
                        continue

                    markdown_docs.append({
                        "filename": md_path.name,
                        "content": md_content
                    })
                    
                    # Попытка извлечь серию для фильтрации событий все еще полезна, если файл - Решение
                    if series is None and markdown_has_decision_header(md_content):
                        series = extract_series_from_markdown(md_content)
                except Exception as e:
                    logger.error(f"Error reading {md_path}: {e}")
        else:
            logger.warning(f"Data directory for {secid} not found. Proceeding with events only.")

        # 4. Load and filter events
        event_years = self.edisclosure_service._compute_event_years(date_str)
        events = []
        try:
            if use_local_events:
                all_events = self.edisclosure_service._load_events_from_local_file(inn, event_years)
            else:
                all_events = []
                for year in event_years:
                    year_events = get_events_with_full_text_for_year(company_id, year)
                    all_events.extend(year_events)
            
            filtered_events = filter_events_by_secid_regnumber_series(
                all_events, secid, regnumber or "", series
            )
            
            # Clean event text
            for ev in filtered_events:
                full_text = ev.get("full_text", "")
                ev["text"] = clean_event_text(full_text)
                events.append(ev)
        except Exception as e:
            logger.error(f"Error loading events for {secid}: {e}")

        # 5. Run vector retrieval pipeline
        queries = [query] if query else None
        context = self.pipeline.run(markdown_docs, events, queries=queries)
        
        # Сохранение отобранных чанков для анализа качества
        try:
            debug_file = bond_data_dir / "vector_context.md"
            self.file_storage.save_text_file(debug_file, context)
            logger.info(f"Saved vector context for debugging: {debug_file}")
        except Exception as e:
            logger.error(f"Error saving debug vector context: {e}")
            
        return context

_vector_retrieval_service = None

def get_vector_retrieval_service() -> VectorRetrievalService:
    """Получает singleton экземпляр сервиса векторного поиска.

    Returns:
        Экземпляр VectorRetrievalService.
    """
    global _vector_retrieval_service
    if _vector_retrieval_service is None:
        _vector_retrieval_service = VectorRetrievalService()
    return _vector_retrieval_service
