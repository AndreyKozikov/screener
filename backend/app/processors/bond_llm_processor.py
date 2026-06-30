from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
from app.repository.db import get_bonds_repository, get_history_repository
from app.repository.files import get_markdownfile_repository, get_file_storage
from app.parsers.emission_documents_parser import extract_series_from_markdown


from app.services.vector_retrieval import get_retrieval_pipeline


_DEFAULT_DATE: str = "2000-04-24"


class BondLLMProcessor:

    def __init__(self,
                 data_dir: Path
                 ) -> None:
        from app.processors import get_events_processor

        self._data_dir: Path = data_dir
        self._bonds_repo = get_bonds_repository()
        self._history_repo = get_history_repository()
        self._markdown_repository = get_markdownfile_repository()
        self._events_processor = get_events_processor()
        self._file_storage = get_file_storage()
        self._retrieval_pipeline = get_retrieval_pipeline()

    def process_single_bond(
            self,
            secid: str,
            pl_logger: logging.Logger,
            use_local_events: bool = False,
            is_forced: bool = False,
            embedding_model: Optional[str] = None,
            queries: Optional[List[str]] = None,
            filename_exclude_phrases: Optional[List[str]] = None,
            header_conditions: Optional[List[str]] = None,
            start_date: Optional[str] = None,
    ) -> Dict[str, Any]:

        print(f"  [{secid}] LLM pipeline start", flush=True)

        # Проверяем, что существует каталог облигации
        bond_data_dir: Path = self._data_dir / secid
        # if not bond_data_dir.is_dir():
        #     pl_logger.warning(f"[SKIP] secid={secid}: директория с файлами не найдена")
        #     return {}

        bond_id: Optional[int] = self._bonds_repo.get_bond_id_by_secid(secid)
        regnumber: Optional[str] = self._bonds_repo.get_reg_number_by_secid(secid)

        # Получаем ИНН компании, выпустившей облигацию
        inn: Optional[str] = self._bonds_repo.get_emitent_inn_by_secid(secid)
        if not inn:
            pl_logger.warning(f"[SKIP] secid={secid}: ИНН эмитента не найден в базе")
            # Сохраняем в базу пустые значения
            # self._save_not_found(bond_id, is_forced)
            return {}

        # Получаем дату начала торгов по облигации
        if start_date is None:
            first_tradedate = self._history_repo.get_first_tradedate(secid)

            date_str: str = (
                first_tradedate.isoformat() if first_tradedate is not None else _DEFAULT_DATE
            )
        else:
            date_str = start_date

        # --- Step 2: Filter existing Markdown files ---

        markdown_docs = self._markdown_repository.read_emission_docs(
            secid,
            filename_exclude_phrases,
            header_conditions
        )

        # --- Step 3: Extract series from Markdown ---
        series: Optional[str] = None
        for md_record in markdown_docs:
            try:
                md_content: str = md_record["content"]
                series = extract_series_from_markdown(md_content)
                if series is not None:
                    print(f"  [{secid}] Series extracted: {series!r}", flush=True)
                    if series.isdigit():
                        print(f"  [{secid}] Series {series!r} is digits only, ignoring filter", flush=True)
                        series = None
                    break
            except OSError as exc:
                pl_logger.warning(
                    "[DOCS] secid=%s: failed to read %s: %s", secid, md_record["filename"], exc)

        # --- Step 4: Load events and filter ---
        print(f"  [{secid}] Loading and preparing events via processor", flush=True)
        try:
            events = self._events_processor.get_prepared_events(
                secid=secid,
                inn=inn,
                regnumber=regnumber,
                series=series,
                date_str=date_str,
                use_local_events=use_local_events,
                filter_event_by_type=True
            )
            print(f"  [{secid}] Filtered and cleaned events: {len(events)}", flush=True)
        except Exception as exc:
            pl_logger.warning(
                "[EVENTS] secid=%s: event processing error: %s", secid, exc,
            )
            events = []

        # Save events.json
        events_file: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file,
            json.dumps(
                [
                    {
                        "event_name": e.get("event_name"),
                        "event_date": e.get("event_date"),
                        "pseudo_guid": e.get("pseudo_guid"),
                        "full_text": e.get("full_text", ""),
                        "processed_text": e.get("text", ""),
                    }
                    for e in events
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        events_for_llm: List[Dict[str, Any]] = [
            {
                "event_name": e.get("event_name"),
                "event_date": e.get("event_date"),
                "text": e.get("text", ""),
            }
            for e in events
        ]
        if not events and not markdown_docs:
            pl_logger.warning(
                "[NOT FOUND] secid=%s: no events and no documents", secid,
            )
            return {}

        # Vector retrieval must be applied before sending data to LLM.
        try:
            vector_context: str = self._retrieval_pipeline.run(
                markdown_docs=markdown_docs,
                events=events_for_llm,
                queries=queries,
                embedding_model=embedding_model,
            )
            self._file_storage.save_text_file(
                bond_data_dir / "vector_context.md", vector_context
            )
        except Exception as exc:
            pl_logger.error(
                "[VECTOR] secid=%s: vector retrieval failed: %s", secid, exc,
                exc_info=True,
            )
            return {}

        converted: Dict[str, Any] = {
            "bond_id": bond_id,
            "secid": secid,
            "inn": inn,
            "regnumber": regnumber,
            "search_date": date_str,
            "queries": queries,
            "vector_context": vector_context,
        }

        return converted
