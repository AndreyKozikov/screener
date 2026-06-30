"""Роутер извлечения параметров облигаций с плавающим купоном через LLM."""

from typing import Any, Dict

from fastapi import APIRouter

from app.models.schemasDTO.float_param_analize_dto import FloatParamsAnalizeLLM
from app.models.schemasDTO.bond_docs_analisis_dto import BondBondsDocsAnalisisDTO
from app.services import get_llm_analysis_service

router = APIRouter(prefix="/api", tags=["float-bonds-llm-analize"])


@router.post("/float-bonds-llm-analize/run")
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
    return service.analysis_floaters_params(**payload.model_dump())


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
    return service.answer_question(**payload.model_dump())