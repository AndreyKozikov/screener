from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.services.vector_retrieval_service import get_vector_retrieval_service
from app.services.gemini_analysis_service import get_gemini_analysis_service, GEMINI_MODEL_3_FLASH
from config.llm_prompts import build_floater_analysis_prompt
from config.settings import settings
from openai import OpenAI

router = APIRouter(
    prefix="/api/vector-retrieval",
    tags=["vector-retrieval"]
)

class BondContextRequest(BaseModel):
    secid: str = Field(..., description="SECID облигации")
    regnumber: Optional[str] = Field(None, description="Регистрационный номер (опционально)")
    use_local_events: bool = Field(False, description="Использовать локальный кэш событий")
    query: Optional[str] = Field(None, description="Пользовательский запрос для поиска")
    model: Optional[str] = Field(None, description="Идентификатор модели LLM (например, gemini-2.5-flash)")

@router.post("/bond-context")
async def get_bond_context(
    request: BondContextRequest
) -> Dict[str, Any]:
    """
    Эндпоинт для получения интеллектуально отобранного контекста по облигации
    и его анализа через Gemini Flash.
    """
    service = get_vector_retrieval_service()
    gemini_service = get_gemini_analysis_service()
    
    try:
        # Если передан пользовательский запрос - возвращаем ответ от ЛЛМ с обогащением запроса
        if request.query:
            model_id = request.model
            is_openrouter = model_id and model_id.startswith("openrouter/")
            
            if is_openrouter and model_id:
                actual_model = model_id.replace("openrouter/", "")
                
                # 1. Обогащаем запрос (Query Expansion) через OpenRouter
                from config.llm_prompts import QUERY_EXPANSION_SYSTEM_PROMPT
                expansion_prompt = (
                    f"{QUERY_EXPANSION_SYSTEM_PROMPT}\n\n"
                    f"Пользовательский запрос: {request.query}\n\n"
                    f"Обогащенный запрос:"
                )
                
                api_key = settings.OPENROUTER_API_KEY
                if not api_key:
                    raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY не задан в настройках бэкенда")
                
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                )
                
                try:
                    expansion_completion = client.chat.completions.create(
                        model=actual_model,
                        messages=[{"role": "user", "content": expansion_prompt}],
                        temperature=0.1,
                    )
                    expanded_query = expansion_completion.choices[0].message.content or request.query
                    expanded_query = expanded_query.strip().strip('"').strip("'").strip()
                    print(f"[OPENROUTER] Expanded query: '{expanded_query}'", flush=True)
                except Exception as e:
                    print(f"[OPENROUTER] Ошибка при обогащении запроса: {str(e)}", flush=True)
                    expanded_query = request.query
                
                # 2. Получаем контекст через векторный поиск
                context = service.get_context_for_bond(
                    secid=request.secid,
                    regnumber=request.regnumber,
                    use_local_events=request.use_local_events,
                    query=expanded_query
                )
                
                # 3. Отвечаем на исходный вопрос пользователя на основе контекста через OpenRouter
                from config.llm_prompts import build_qa_prompt
                qa_prompt = build_qa_prompt(context=context, query=request.query)
                
                try:
                    qa_completion = client.chat.completions.create(
                        model=actual_model,
                        messages=[{"role": "user", "content": qa_prompt}],
                        temperature=0.1,
                    )
                    answer = qa_completion.choices[0].message.content or "Не удалось получить ответ от OpenRouter."
                except Exception as e:
                    answer = f"Ошибка при вызове OpenRouter: {str(e)}"
                
                return {
                    "query": request.query,
                    "answer": answer
                }
            else:
                # 1. Обогащаем запрос (Query Expansion) через LLM
                expanded_query = gemini_service.expand_query(request.query, model=request.model)
                
                # 2. Получаем контекст через векторный поиск с использованием обогащенного запроса
                context = service.get_context_for_bond(
                    secid=request.secid,
                    regnumber=request.regnumber,
                    use_local_events=request.use_local_events,
                    query=expanded_query
                )
                
                # 3. Отвечаем на исходный вопрос пользователя на основе контекста
                answer = gemini_service.answer_question(
                    context=context,
                    query=request.query,
                    model=request.model
                )
                return {
                    "query": request.query,
                    "answer": answer
                }
        
        # 1. Получаем контекст через векторный поиск (когда query не передан, используются дефолтные запросы)
        context = service.get_context_for_bond(
            secid=request.secid, 
            regnumber=request.regnumber,
            use_local_events=request.use_local_events,
            query=None
        )
        
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
