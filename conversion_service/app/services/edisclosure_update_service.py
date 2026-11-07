"""Update e-disclosure company mappings and emission-document metadata."""

import logging
import re
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
from conversion_service.app.utils.emission_documents_parser import (
    detect_edisclosure_protection,
    parse_emission_documents,
)

logger = logging.getLogger(__name__)

_COMPANY_NAME_STOP_WORDS: Set[str] = {
    "ао", "оао", "зао", "пао", "ооо", "кб", "банк", "банка",
    "общество", "акционерное", "публичное", "открытое", "закрытое",
    "непубличное", "ограниченной", "ответственностью", "коммерческий",
    "jsc", "pjsc", "llc", "ltd", "bank", "limited", "company",
}


def _company_tokens(value: str) -> Set[str]:
    """Возвращает значимые слова названия компании для сверки маппинга."""
    words = re.findall(r"[a-zA-Zа-яА-Я0-9]+", value.lower())
    return {
        word
        for word in words
        if len(word) >= 3 and word not in _COMPANY_NAME_STOP_WORDS
    }


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
            emitent_title = str(emitent.get("title") or "")
            try:
                companies = search_company_by_inn(inn)
                company = self._select_company(companies, emitent_title, inn)
                if company is None or company.get("id") is None:
                    skipped += 1
                    time.sleep(delay)
                    continue

                company_id = int(company["id"])
                conflict_emitent_id = self._mapping_repo.get_emitent_id_by_edisclosure_id(
                    company_id
                )
                if conflict_emitent_id is not None and conflict_emitent_id != emitent_id:
                    logger.warning(
                        "E-disclosure id %s already mapped to emitent_id=%s; "
                        "skip emitent_id=%s (INN %s, title %r) to avoid duplicate/wrong mapping.",
                        company_id,
                        conflict_emitent_id,
                        emitent_id,
                        inn,
                        emitent_title,
                    )
                    skipped += 1
                    time.sleep(delay)
                    continue

                self._mapping_repo.upsert_mapping(emitent_id, company_id)
                saved += 1
                logger.info(
                    "Mapped emitent_id=%s (INN %s, title %r) -> e-disclosure id %s (%r)",
                    emitent_id,
                    inn,
                    emitent_title,
                    company_id,
                    company.get("name"),
                )
            except Exception:
                skipped += 1
                logger.exception(
                    "Failed to map emitent_id=%s (INN %s, title %r) to e-disclosure",
                    emitent_id,
                    inn,
                    emitent_title,
                )
            time.sleep(delay)

        return {
            "total_emitents": len(emitents),
            "already_in_table": len(existing_ids),
            "to_process": len(to_process),
            "saved": saved,
            "skipped": skipped,
        }

    @staticmethod
    def _select_company(
        companies: List[Dict[str, Any]],
        emitent_title: str,
        inn: str,
    ) -> Optional[Dict[str, Any]]:
        """Выбирает компанию e-disclosure, чьё название похоже на название эмитента.

        Это защита от неверного первого результата поиска: раньше код брал
        companies[0] без проверки, из-за чего можно было привязать эмитента
        к чужой странице e-disclosure и скачивать чужие документы.
        """
        if not companies:
            return None
        if not emitent_title:
            return companies[0]

        title_tokens = _company_tokens(emitent_title)
        best_company: Optional[Dict[str, Any]] = None
        best_score = 0
        for company in companies:
            if company.get("id") is None:
                continue
            name_tokens = _company_tokens(str(company.get("name") or ""))
            score = len(title_tokens & name_tokens)
            if score > best_score:
                best_company = company
                best_score = score

        if best_company is not None and best_score > 0:
            return best_company

        logger.warning(
            "E-disclosure search by INN %s returned no company matching emitent title %r: %r. "
            "Mapping skipped to avoid assigning a foreign e-disclosure page.",
            inn,
            emitent_title,
            [company.get("name") for company in companies],
        )
        return None

    def fetch_emission_documents(self, limit: Optional[int] = None) -> Dict[str, Any]:
        delay = 1.5
        emitents = self._mapping_repo.get_emitents_ordered_by_missing_docs(limit)
        processed = total_docs_added = empty_count = blocked_count = failed_count = 0

        for emitent in emitents:
            mapping_id = emitent["id"]
            edisclosure_id = emitent["edisclosure_id"]
            try:
                html = fetch_emission_documents_page(edisclosure_id)
                protection = detect_edisclosure_protection(html)
                docs = parse_emission_documents(html)
                logger.info(
                    "Emission documents response: edisclosure_id=%s, html_len=%d, parsed=%d, protection=%s",
                    edisclosure_id,
                    len(html),
                    len(docs),
                    protection or "-",
                )
                if not docs:
                    if protection:
                        blocked_count += 1
                        logger.warning(
                            "Emission documents blocked by e-disclosure anti-bot protection: "
                            "edisclosure_id=%s, marker=%r, html_len=%d. Existing DB rows kept.",
                            edisclosure_id,
                            protection,
                            len(html),
                        )
                    else:
                        empty_count += 1
                        logger.warning(
                            "No emission documents parsed: edisclosure_id=%s, html_len=%d. "
                            "Either the issuer has no documents on the page, or the table was not recognized.",
                            edisclosure_id,
                            len(html),
                        )
                else:
                    inserted = self._documents_repo.insert_batch(mapping_id, docs)
                    total_docs_added += inserted
                    logger.info(
                        "Emission documents updated: edisclosure_id=%s, inserted=%d",
                        edisclosure_id,
                        inserted,
                    )
            except Exception:
                failed_count += 1
                logger.exception("Failed to fetch emission documents for e-disclosure id %s", edisclosure_id)
            processed += 1
            time.sleep(delay)

        return {
            "processed": processed,
            "total_docs_added": total_docs_added,
            "empty_count": empty_count,
            "blocked_count": blocked_count,
            "failed_count": failed_count,
        }


_service: Optional[EdisclosureUpdateService] = None


def get_edisclosure_update_service() -> EdisclosureUpdateService:
    global _service
    if _service is None:
        _service = EdisclosureUpdateService()
    return _service
