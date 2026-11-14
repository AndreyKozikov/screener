"""Admin-only read access to persisted agent session logs."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.agent.session_logger import get_session_logger
from app.routers.auth import require_admin
from config.paths import BACKEND_DIR

router = APIRouter(
    prefix="/api/admin/agent-sessions",
    tags=["admin-agent-sessions"],
    dependencies=[Depends(require_admin)],
)

_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_ISSUE_TYPES = {
    "error",
    "finalizer_empty",
    "finalizer_error",
    "finalizer_fallback",
    "llm_generation_error",
    "router_invalid",
    "router_none",
    "skill_load_error",
    "skill_selection_error",
    "tool_args_invalid",
    "tool_error",
    "tool_error_result",
    "tool_unknown",
}


class AgentSessionSummary(BaseModel):
    session_id: str
    first_query: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    query_count: int = 0
    event_count: int = 0
    issue_count: int = 0
    with_portfolio: bool = False
    outcome: Optional[str] = None
    log_source: str = "current"


class AgentSessionListResponse(BaseModel):
    items: List[AgentSessionSummary]
    total: int
    offset: int
    limit: int
    logging_enabled: bool


class AgentSessionDetailResponse(AgentSessionSummary):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]]
    parse_errors: int = 0


def _log_roots() -> tuple[List[tuple[Path, str]], bool]:
    configured_path, logging_enabled = get_session_logger().config
    configured_root = configured_path.resolve()
    roots: List[tuple[Path, str]] = [(configured_root, "current")]

    # Older builds resolved the default relative path from the repository root.
    # Include those existing logs so upgrades do not hide already collected chats.
    legacy_root = (BACKEND_DIR.parent / "logs" / "agent_sessions").resolve()
    if legacy_root != configured_root and legacy_root.is_dir():
        roots.append((legacy_root, "legacy"))
    return roots, logging_enabled


def _safe_session_dir(root: Path, session_id: str) -> Optional[Path]:
    if not _SAFE_SESSION_ID.fullmatch(session_id):
        return None
    try:
        resolved_root = root.resolve()
        resolved_dir = (resolved_root / session_id).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if resolved_dir.parent != resolved_root or not resolved_dir.is_dir():
        return None
    return resolved_dir


def _read_metadata(session_dir: Path) -> Dict[str, Any]:
    path = session_dir / "session.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_events(session_dir: Path) -> tuple[List[Dict[str, Any]], int]:
    path = session_dir / "events.jsonl"
    events: List[Dict[str, Any]] = []
    parse_errors = 0
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue
                if isinstance(event, dict):
                    events.append(_json_safe(event))
                else:
                    parse_errors += 1
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        parse_errors += 1
    return events, parse_errors


def _is_issue_event(event: Dict[str, Any]) -> bool:
    event_type = event.get("type")
    return event_type in _ISSUE_TYPES or (
        event_type == "llm_provider_attempt"
        and event.get("status") in {"failed", "empty"}
    )


def _event_stats(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_queries = [event for event in events if event.get("type") == "user_query"]
    timestamps = [str(event["ts"]) for event in events if event.get("ts")]
    outcome_types = {
        "error",
        "final_answer",
        "finalizer_fallback",
        "needs_info",
        "tool_error_result",
    }
    outcome = next(
        (str(event.get("type")) for event in reversed(events) if event.get("type") in outcome_types),
        None,
    )
    return {
        "event_count": len(events),
        "query_count": len(user_queries),
        "first_query": next((event.get("query") for event in user_queries if event.get("query")), ""),
        "first_event_at": timestamps[0] if timestamps else None,
        "last_event_at": timestamps[-1] if timestamps else None,
        "issue_count": sum(1 for event in events if _is_issue_event(event)),
        "outcome": outcome,
    }


def _read_event_stats(session_dir: Path) -> Dict[str, Any]:
    """Summarize an event stream without loading tool results and prompts into memory."""
    path = session_dir / "events.jsonl"
    stats: Dict[str, Any] = {
        "event_count": 0,
        "query_count": 0,
        "first_query": "",
        "first_event_at": None,
        "last_event_at": None,
        "issue_count": 0,
        "outcome": None,
    }
    outcome_types = {
        "error",
        "final_answer",
        "finalizer_fallback",
        "needs_info",
        "tool_error_result",
    }
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                stats["event_count"] += 1
                event_type = event.get("type")
                if event_type == "user_query":
                    stats["query_count"] += 1
                    if not stats["first_query"] and event.get("query"):
                        stats["first_query"] = str(event["query"])
                if _is_issue_event(event):
                    stats["issue_count"] += 1
                if event_type in outcome_types:
                    stats["outcome"] = str(event_type)
                event_ts = event.get("ts")
                if event_ts:
                    event_ts = str(event_ts)
                    if stats["first_event_at"] is None:
                        stats["first_event_at"] = event_ts
                    stats["last_event_at"] = event_ts
    except (OSError, UnicodeError):
        pass
    return stats


def _iso_from_mtime(session_dir: Path) -> Optional[str]:
    try:
        timestamp = (session_dir / "events.jsonl").stat().st_mtime
    except OSError:
        try:
            timestamp = session_dir.stat().st_mtime
        except OSError:
            return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def _summary(
    session_id: str,
    session_dir: Path,
    log_source: str,
    *,
    include_events: bool = False,
) -> tuple[AgentSessionSummary, Optional[List[Dict[str, Any]]], int]:
    metadata = _read_metadata(session_dir)
    events: Optional[List[Dict[str, Any]]] = None
    if include_events:
        events, parse_errors = _read_events(session_dir)
        stats = _event_stats(events)
    else:
        parse_errors = 0
        stats = _read_event_stats(session_dir)
    first_query = str(
        metadata.get("first_query")
        or stats["first_query"]
    )
    created_at = str(metadata.get("ts") or stats["first_event_at"] or "") or None
    updated_at = stats["last_event_at"] or _iso_from_mtime(session_dir)
    summary = AgentSessionSummary(
        session_id=session_id,
        first_query=first_query[:500],
        created_at=created_at,
        updated_at=updated_at,
        query_count=stats["query_count"],
        event_count=stats["event_count"],
        issue_count=stats["issue_count"],
        with_portfolio=bool(metadata.get("with_portfolio")),
        outcome=stats["outcome"],
        log_source=log_source,
    )
    return summary, events, parse_errors


def _all_summaries() -> tuple[List[AgentSessionSummary], bool]:
    roots, logging_enabled = _log_roots()
    summaries_by_id: Dict[str, AgentSessionSummary] = {}
    for root, source in roots:
        if not root.is_dir():
            continue
        try:
            directories = list(root.iterdir())
        except OSError:
            continue
        for directory in directories:
            if not directory.is_dir() or not _SAFE_SESSION_ID.fullmatch(directory.name):
                continue
            safe_dir = _safe_session_dir(root, directory.name)
            if safe_dir is None:
                continue
            summary, _, _ = _summary(directory.name, safe_dir, source)
            current = summaries_by_id.get(directory.name)
            if current is None or (summary.updated_at or "") > (current.updated_at or ""):
                summaries_by_id[directory.name] = summary

    summaries = list(summaries_by_id.values())
    summaries.sort(key=lambda item: (item.updated_at or "", item.session_id), reverse=True)
    return summaries, logging_enabled


@router.get("", response_model=AgentSessionListResponse)
def list_agent_sessions(
    q: str = Query(default="", max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    problem_only: bool = Query(default=False),
) -> AgentSessionListResponse:
    """List logged chats, optionally searching by session ID or first query."""
    summaries, logging_enabled = _all_summaries()
    if problem_only:
        summaries = [item for item in summaries if item.issue_count > 0]
    needle = q.strip().casefold()
    if needle:
        summaries = [
            item
            for item in summaries
            if needle in item.session_id.casefold() or needle in item.first_query.casefold()
        ]
    return AgentSessionListResponse(
        items=summaries[offset : offset + limit],
        total=len(summaries),
        offset=offset,
        limit=limit,
        logging_enabled=logging_enabled,
    )


@router.get("/{session_id}", response_model=AgentSessionDetailResponse)
def get_agent_session(session_id: str) -> AgentSessionDetailResponse:
    """Return full metadata and event stream for one logged chat."""
    if not _SAFE_SESSION_ID.fullmatch(session_id):
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    roots, _ = _log_roots()
    candidates: List[tuple[Path, str]] = []
    for root, source in roots:
        session_dir = _safe_session_dir(root, session_id)
        if session_dir is not None:
            candidates.append((session_dir, source))
    if not candidates:
        raise HTTPException(status_code=404, detail="Лог чата не найден")

    session_dir, source = max(
        candidates,
        key=lambda item: _summary(session_id, item[0], item[1])[0].updated_at or "",
    )
    summary, events, parse_errors = _summary(
        session_id, session_dir, source, include_events=True
    )
    metadata = _json_safe(_read_metadata(session_dir))
    return AgentSessionDetailResponse(
        **summary.model_dump(),
        metadata=metadata,
        events=events or [],
        parse_errors=parse_errors,
    )
