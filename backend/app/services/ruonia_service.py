"""Read-only access to RUONIA records in the shared database."""

from datetime import date, datetime
from typing import Optional

from app.models.schemasDTO.ruonia_dto import RuoniaDataResponse, RuoniaDTO
from app.repository.db.ruonia_repository import RuoniaRepository


class RuoniaService:
    """Expose RUONIA queries to backend features without performing updates."""

    def __init__(self, repository: Optional[RuoniaRepository] = None) -> None:
        self._repository = repository or RuoniaRepository()

    def get_ruonia_data(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> RuoniaDataResponse:
        from_date = _parse_date(date_from)
        to_date = _parse_date(date_to)
        rows = self._repository.get_by_date_range(date_from=from_date, date_to=to_date)
        data = [
            RuoniaDTO(
                date_stavki=_date_key(row.dt),
                stavka_ruonia=row.ruo,
                volume_ruonia=row.vol,
                count_deals=row.T,
                min_rate=row.MinRate,
                percentile_25=row.Percentile25,
                percentile_75=row.Percentile75,
                max_rate=row.MaxRate,
            )
            for row in rows
        ]
        return RuoniaDataResponse(
            data=data,
            count=len(data),
            date_from=date_from,
            date_to=date_to,
        )

    def export_markdown(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        response = self.get_ruonia_data(date_from=date_from, date_to=date_to)
        columns = [
            "Дата ставки",
            "Ставка RUONIA, % годовых",
            "Объем сделок RUONIA, млрд руб.",
            "Количество сделок, ед.",
            "Минимальная процентная ставка, % годовых",
            "25-й процентиль по процентным ставкам, % годовых",
            "75-й процентиль по процентным ставкам, % годовых",
            "Максимальная процентная ставка, % годовых",
        ]
        lines = ["# Ставка RUONIA", "", "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for record in response.data:
            row = record.model_dump(by_alias=True)
            values = []
            for column in columns:
                value = row.get(column)
                if value is None:
                    values.append("")
                elif isinstance(value, (int, float)):
                    values.append(f"{value:.4f}")
                else:
                    values.append(str(value))
            lines.append("| " + " | ".join(values) + " |")
        lines.append("")
        return "\n".join(lines)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _date_key(value: date) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


_ruonia_service: Optional[RuoniaService] = None


def get_ruonia_service() -> RuoniaService:
    global _ruonia_service
    if _ruonia_service is None:
        _ruonia_service = RuoniaService()
    return _ruonia_service
