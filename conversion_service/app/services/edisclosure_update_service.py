"""Update e-disclosure company mappings and emission-document metadata."""

import logging
import time
from typing import Any, Dict, List, Optional, Set

from conversion_service.app.repository.db.remote_repository import (
    EmissionDocumentRepository,
    EmitentEdisclosureRepository,
    EmitentsRepository,
)
from conversion_service.app.utils.edisclosure_utils import (
    fetch_emission_documents_page,
    search_company_by_inn,
)
from conversion_service.app.utils.emission_documents_parser import parse_emission_documents

logger = logging.getLogger(__name__)


class EdisclosureUpdateService:
    """Coordinate e-disclosure collection and database writes."""

    def __init__(
        self,
        emitents_repository: Optional[EmitentsRepository] = None,
        mapping_repository: Optional[EmitentEdisclosureRepository] = None,
        documents_repository: Optional[EmissionDocumentRepository] = None,
    ) -> None:
        self._emitents_repo = emitents_repository or EmitentsRepository()
        self._mapping_repo = mapping_repository or EmitentEdisclosureRepository()
        self._documents_repo = documents_repository or EmissionDocumentRepository()

    def populate_emitent_edisclosure(self) -> Dict[str, int]:
        delay = 2.0
        emitents = self._emitents_repo.get_emitents_with_inn()
        existing_ids: Set[int] = self._mapping_repo.get_existing_emitent_ids()
        to_process = [item for item in emitents if item["id"] not in existing_ids]
        saved = 0
        skipped = 0

        for emitent in to_process:
            emitent_id = emitent["id"]
            inn = emitent["inn"]
            try:
                companies = search_company_by_inn(inn)
                if not companies or companies[0].get("id") is None:
                    skipped += 1
                    time.sleep(delay)
                    continue
                self._mapping_repo.upsert_mapping(emitent_id, int(companies[0]["id"]))
                saved += 1
            except Exception:
                skipped += 1
            time.sleep(delay)

        return {
            "total_emitents": len(emitents),
            "already_in_table": len(existing_ids),
            "to_process": len(to_process),
            "saved": saved,
            "skipped": skipped,
        }

    def fetch_emission_documents(self, limit: Optional[int] = None) -> Dict[str, Any]:
        delay = 1.5
        emitents = self._mapping_repo.get_emitents_ordered_by_missing_docs(limit)
        processed = total_docs_added = empty_count = 0

        for emitent in emitents:
            mapping_id = emitent["id"]
            edisclosure_id = emitent["edisclosure_id"]
            try:
                html = fetch_emission_documents_page(edisclosure_id)
                docs = parse_emission_documents(html)
                if not docs:
                    empty_count += 1
                else:
                    total_docs_added += self._documents_repo.insert_batch(mapping_id, docs)
            except Exception:
                logger.exception("Failed to fetch emission documents for e-disclosure id %s", edisclosure_id)
                empty_count += 1
            processed += 1
            time.sleep(delay)

        return {
            "processed": processed,
            "total_docs_added": total_docs_added,
            "empty_count": empty_count,
        }


_service: Optional[EdisclosureUpdateService] = None


def get_edisclosure_update_service() -> EdisclosureUpdateService:
    global _service
    if _service is None:
        _service = EdisclosureUpdateService()
    return _service
