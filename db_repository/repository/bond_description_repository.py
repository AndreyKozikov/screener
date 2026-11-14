"""Persistence for MOEX bond-description data."""

import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import select

from db_repository.core.database_init import get_session
from db_repository.models.bond import Bond
from db_repository.models.bond_description import BondDescription
from db_repository.models.emitent import Emitent


_SECID_QUERY_BATCH_SIZE = 500
_EMITENT_INSERT_BATCH_SIZE = 500
_DESCRIPTION_UPSERT_BATCH_SIZE = 20


class BondDescriptionRepository:
    """Upserts validated descriptions, resolving MOEX SECID to bonds.id."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def upsert_by_secid(self, descriptions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        normalized = {
            str(secid).strip(): values
            for secid, values in descriptions.items()
            if secid and str(secid).strip() and isinstance(values, dict)
        }
        if not normalized:
            return {"updated": 0, "unmatched_secids": [], "invalid_secids": []}

        with get_session() as session:
            bond_rows = []
            secids = list(normalized)
            for offset in range(0, len(secids), _SECID_QUERY_BATCH_SIZE):
                bond_rows.extend(
                    session.exec(
                        select(Bond.secid, Bond.id).where(
                            Bond.secid.in_(secids[offset:offset + _SECID_QUERY_BATCH_SIZE])
                        )
                    ).all()
                )
            bond_ids_by_secid: dict[str, list[int]] = {}
            for secid, bond_id in bond_rows:
                if secid and bond_id is not None:
                    bond_ids_by_secid.setdefault(str(secid).strip(), []).append(int(bond_id))

            records: list[dict[str, Any]] = []
            unmatched_secids: list[str] = []
            invalid_secids: list[str] = []
            for secid, values in normalized.items():
                bond_ids = bond_ids_by_secid.get(secid, [])
                if not bond_ids:
                    unmatched_secids.append(secid)
                    continue
                try:
                    validated = [
                        BondDescription.model_validate({**values, "bond_id": bond_id})
                        for bond_id in bond_ids
                    ]
                except ValidationError as exc:
                    self.logger.warning(
                        "Некорректные данные MOEX description для %s: %s", secid, exc
                    )
                    invalid_secids.append(secid)
                    continue
                records.extend(model.model_dump() for model in validated)

            if records:
                emitter_ids = sorted({
                    row["emitter_id"]
                    for row in records
                    if row.get("emitter_id") is not None
                })
                if emitter_ids:
                    for offset in range(0, len(emitter_ids), _EMITENT_INSERT_BATCH_SIZE):
                        emitent_stmt = insert(Emitent).values(
                            [
                                {"moex_id": emitter_id}
                                for emitter_id in emitter_ids[
                                    offset:offset + _EMITENT_INSERT_BATCH_SIZE
                                ]
                            ]
                        )
                        session.exec(
                            emitent_stmt.on_conflict_do_nothing(
                                index_elements=[Emitent.moex_id]
                            )
                        )

                for offset in range(0, len(records), _DESCRIPTION_UPSERT_BATCH_SIZE):
                    stmt = insert(BondDescription).values(
                        records[offset:offset + _DESCRIPTION_UPSERT_BATCH_SIZE]
                    )
                    update_columns = {
                        column.name: getattr(stmt.excluded, column.name)
                        for column in BondDescription.__table__.columns
                        if column.name != "bond_id"
                    }
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[BondDescription.bond_id],
                        set_=update_columns,
                    )
                    session.exec(stmt)
                session.commit()

        return {
            "updated": len(records),
            "unmatched_secids": unmatched_secids,
            "invalid_secids": invalid_secids,
        }
