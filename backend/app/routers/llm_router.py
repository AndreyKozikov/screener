"""Роутер извлечения параметров облигаций с плавающим купоном через LLM."""

import traceback
from typing import Any, Dict

import asyncio

from fastapi import APIRouter, Depends

from app.routers.auth import require_admin
from app.models.schemasDTO.float_param_analize_dto import FloatParamsAnalizeLLM
from app.models.schemasDTO.bond_docs_analisis_dto import BondBondsDocsAnalisisDTO
from app.services import get_llm_analysis_service
from app.services.data_update_journal import (
    STATUS_ERROR,
    begin_manual_run,
    classify_payload,
    finish_manual_run,
)

router = APIRouter(prefix="/api", tags=["float-bonds-llm-analize"])

_FLOATERS_TASK_ID = "floaters"
_FLOATERS_REQUEST_PATH = "/api/float-bonds-llm-analize/run"


@router.post("/float-bonds-llm-analize/run", dependencies=[Depends(require_admin)])
async def run_float_bonds_analize(payload: FloatParamsAnalizeLLM) -> Dict[str, Any]:
    """Запускает пайплайн анализа LLM для флоатеров с загруженными документами.

    Читает существующие Markdown-файлы из data/{secid}/, загружает
    события (локально или с сервера e-disclosure), применяет фильтры (серия,
    регистрационный номер, secid) и отправляет промпт в LLM.

    Args:
        payload: DTO с параметрами конфигурации и фильтрации для пайплайна.

    Returns:
        Словарь с результатами выполнения пайплайна.
    """
    service = get_llm_analysis_service()
    run_id, started_at = await begin_manual_run(
        _FLOATERS_TASK_ID,
        _FLOATERS_REQUEST_PATH,
        None,
    )
    try:
        result = await asyncio.to_thread(
            service.analysis_floaters_params, **payload.model_dump()
        )
    except Exception as exc:
        await finish_manual_run(
            run_id=run_id,
            task_id=_FLOATERS_TASK_ID,
            request_path=_FLOATERS_REQUEST_PATH,
            request_query=None,
            started_at=started_at,
            status=STATUS_ERROR,
            error_message=str(exc),
            exception_text=traceback.format_exc(),
        )
        raise

    status, error_message, warning_message = classify_payload(_FLOATERS_TASK_ID, result)
    await finish_manual_run(
        run_id=run_id,
        task_id=_FLOATERS_TASK_ID,
        request_path=_FLOATERS_REQUEST_PATH,
        request_query=None,
        started_at=started_at,
        status=status,
        http_status=200,
        error_message=error_message,
        warning_message=warning_message,
        payload=result,
    )
    return result


@router.post("/llm/bond-context")
async def run_answer_question(payload: BondBondsDocsAnalisisDTO) -> Dict[str, Any]:
    """Запускает пайплайн анализа LLM для флоатеров с загруженными документами.

    Читает существующие Markdown-файлы из data/{secid}/, загружает
    события (локально или с сервера e-disclosure), применяет фильтры (серия,
    регистрационный номер, secid) и отправляет промпт в LLM.

    Args:
        payload: DTO с параметрами конфигурации и фильтрации для пайплайна.

    Returns:
        Словарь с результатами выполнения пайплайна.
    """
    service = get_llm_analysis_service()
    return await asyncio.to_thread(
        service.answer_question, **payload.model_dump()
    )
