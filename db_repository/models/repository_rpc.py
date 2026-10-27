"""Validated contracts for backend-to-repository operations."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCall(BaseModel):
    """Call one explicitly allow-listed repository operation over HTTP."""

    model_config = ConfigDict(extra="forbid")

    repository: Literal[
        "blog", "bond_float_params", "bond_ratings", "bonds", "currency_rates",
        "coupons", "kbd", "descriptions", "emission_documents",
        "emitent_edisclosure", "emitents", "events", "forecasts", "keyrates",
        "ruonia", "trading_history",
    ]
    method: Literal[
        "create", "delete", "delete_event", "fetch_coupons_for_frontend",
        "fetch_coupons_raw", "get_agency_name_short_ru_by_agency_id", "get_all_dates",
        "get_all_emitent_titles", "get_all_secids", "get_bond_detail_by_secid", "get_bond_id_by_secid",
        "get_bond_ids_with_find", "get_bonds_for_ratings_pipeline", "get_by_bond_id", "get_by_date",
        "get_by_date_range", "get_by_guid_and_date", "get_by_secid_date_range", "get_by_slug",
        "get_count", "get_descriptions_formatted", "get_edisclosure_id_by_emitent_id",
        "get_emitent_data_by_secid", "get_emitent_id_by_inn", "get_emitent_inn_by_secid",
        "get_emitents_ordered_by_missing_docs", "get_emitents_with_inn", "get_event_by_id",
        "get_existing_bond_ids", "get_existing_emitent_ids", "get_existing_types", "get_first_tradedate",
        "get_first_unedited_id", "get_floater_secids", "get_forecast_by_date", "get_id_secid_list",
        "get_kbd_data", "get_last_kbd_date", "get_last_tradedate", "get_latest_on_or_before",
        "get_max_date", "get_navigation_ids", "get_processed_events_keys", "get_ratings_by_secid",
        "get_reg_number_by_secid", "get_secid_to_emitent_title_index", "get_secids_by_ids",
        "get_secids_by_regnumber", "get_stats", "has_coupons_for_secid", "insert_batch",
        "list_articles", "save", "save_event_changes", "save_forecast", "save_kbd_records",
        "save_many", "save_moex_coupons", "save_records", "update",
        "upsert", "upsert_mapping", "upsert_ratings_for_bond",
    ]
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class RepositoryResult(BaseModel):
    """JSON-safe result returned by the database service."""

    model_config = ConfigDict(extra="forbid")

    result: Any
