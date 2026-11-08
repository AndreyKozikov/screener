"""Update e-disclosure company mappings and emission-document metadata."""

import logging
import time
from typing import Any, Dict, Optional, Set

from conversion_service.app.repository.db.remote_repository import (
    EmissionDocumentRepository,
    EmitentEdisclosureRepository,
    EmitentsRepository,
)
from conversion_service.app.utils.edisclosure.browser_event_fetcher import (
    LazyEdisclosureBrowser,
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

    def populate_emitent_edisclosure(self, force: bool = False) -> Dict[str, Any]:
        delay = 2.0
        emitents = self._emitents_repo.get_emitents_with_inn()
        existing_ids: Set[int] = self._mapping_repo.get_existing_emitent_ids()
        if force:
            to_process = list(emitents)
        else:
            to_process = [item for item in emitents if item["id"] not in existing_ids]
        saved = 0
        created = 0
        updated = 0
        skipped = 0

        with LazyEdisclosureBrowser() as browser:
            for emitent in to_process:
                emitent_id = emitent["id"]
                inn = emitent["inn"]
                emitent_title = str(emitent.get("title") or "")
                try:
                    if browser.started:
                        companies = browser.get().search_companies_by_inn(inn)
                    else:
                        try:
                            companies = search_company_by_inn(inn)
                        except Exception as exc:
                            logger.warning(
                                "HTTP-поиск компании по ИНН %s не удался (%s); "
                                "переключаюсь на браузер.",
                                inn,
                                exc,
                            )
                            companies = browser.get().search_companies_by_inn(inn)

                    company = next(
                        (item for item in companies if item.get("id") is not None),
                        None,
                    )
                    if company is None:
                        logger.warning(
                            "E-disclosure search by INN %s returned no usable company: %r. "
                            "Mapping skipped.",
                            inn,
                            [item.get("name") for item in companies],
                        )
                        skipped += 1
                        time.sleep(delay)
                        continue
                    if len(companies) > 1:
                        logger.warning(
                            "E-disclosure search by INN %s returned %d companies; "
                            "using first: id=%s, name=%r.",
                            inn,
                            len(companies),
                            company.get("id"),
                            company.get("name"),
                        )

                    company_id = int(company["id"])
                    conflict_emitent_id = self._mapping_repo.get_emitent_id_by_edisclosure_id(
                        company_id
                    )
                    if conflict_emitent_id is not None and conflict_emitent_id != emitent_id:
                        if force:
                            logger.warning(
                                "Force remap: e-disclosure id %s was mapped to emitent_id=%s; "
                                "remapping emitent_id=%s (INN %s, title %r).",
                                company_id,
                                conflict_emitent_id,
                                emitent_id,
                                inn,
                                emitent_title,
                            )
                        else:
                            logger.warning(
                                "E-disclosure id %s already mapped to emitent_id=%s; "
                                "skip emitent_id=%s (INN %s, title %r) to avoid duplicate/wrong mapping. "
                                "Use force=true to overwrite.",
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
                    if emitent_id in existing_ids:
                        updated += 1
                    else:
                        created += 1
                    logger.info(
                        "%s emitent_id=%s (INN %s, title %r) -> e-disclosure id %s (%r)",
                        "Force-mapped" if force else "Mapped",
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
            "created": created,
            "updated": updated,
            "saved": saved,
            "skipped": skipped,
            "force": force,
        }

    def fetch_emission_documents(self, limit: Optional[int] = None) -> Dict[str, Any]:
        delay = 1.5
        emitents = self._mapping_repo.get_emitents_ordered_by_missing_docs(limit)
        processed = total_docs_added = empty_count = blocked_count = failed_count = 0

        with LazyEdisclosureBrowser() as browser:
            for emitent in emitents:
                mapping_id = emitent["id"]
                edisclosure_id = emitent["edisclosure_id"]
                try:
                    if browser.started:
                        html = browser.get().fetch_emission_documents_html(edisclosure_id)
                    else:
                        try:
                            html = fetch_emission_documents_page(edisclosure_id)
                        except Exception as exc:
                            logger.warning(
                                "HTTP-загрузка страницы документов edisclosure_id=%s "
                                "не удалась (%s); переключаюсь на браузер.",
                                edisclosure_id,
                                exc,
                            )
                            html = browser.get().fetch_emission_documents_html(
                                edisclosure_id
                            )
                        else:
                            http_protection = detect_edisclosure_protection(html)
                            if http_protection:
                                logger.warning(
                                    "HTTP вернул антибот-страницу (маркер=%r) для "
                                    "edisclosure_id=%s; переключаюсь на браузер.",
                                    http_protection,
                                    edisclosure_id,
                                )
                                html = browser.get().fetch_emission_documents_html(
                                    edisclosure_id
                                )

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
