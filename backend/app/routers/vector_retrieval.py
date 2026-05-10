from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.vector_retrieval_service import get_vector_retrieval_service
from app.services.gemini_analysis_service import get_gemini_analysis_service, GEMINI_MODEL_3_FLASH
from config.llm_prompts import build_floater_analysis_prompt

router = APIRouter(
    prefix="/vector-retrieval",
    tags=["vector-retrieval"]
)

@router.get("/bond-context")
async def get_bond_context(
    secid: str = Query(..., description="SECID облигации"),
    regnumber: Optional[str] = Query(None, description="Регистрационный номер (опционально)"),
    use_local_events: bool = Query(False, description="Использовать локальный кэш событий"),
    query: Optional[str] = Query(None, description="Пользовательский запрос для поиска")
):
    """
    Эндпоинт для получения интеллектуально отобранного контекста по облигации
    и его анализа через Gemini Flash.
    """
    service = get_vector_retrieval_service()
    gemini_service = get_gemini_analysis_service()
    
    try:
        # 1. Получаем контекст через векторный поиск
        context = service.get_context_for_bond(
            secid=secid, 
            regnumber=regnumber,
            use_local_events=use_local_events,
            query=query
        )
        
        # Если передан пользовательский запрос - возвращаем результат поиска в JSON
        if query:
            return {
                "query": query,
                "result": context
            }
        
        # 2. Формируем промпт (события пустые, так как они уже в контексте)
        prompt = build_floater_analysis_prompt(
            events_json="[]",
            markdown_content=context
        )
        
        # 3. Прямой вызов LLM без дополнительной валидации и логики
        # Используем модель gemini-3-flash-preview для быстрой оценки
        raw_analysis = gemini_service._client.generate(
            prompt, 
            model=GEMINI_MODEL_3_FLASH
        )
        
        # 4. Парсим JSON из ответа модели (удаляя маркдаун-обертки) и возвращаем напрямую
        from app.services.gemini_analysis_service import _parse_json_response
        return _parse_json_response(raw_analysis)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
