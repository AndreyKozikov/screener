from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import openai
import httpx
import tempfile
import json
from pathlib import Path
from app.config import settings

router = APIRouter(prefix="/api/llm", tags=["llm"])


class LLMAnalysisResponse(BaseModel):
    analysis: str  # Финальный отчет (этап 5)
    model_used: str
    stage1_forecast: str | None = None  # Этап 1: Прогноз Банка России
    stage2_zerocupon: str | None = None  # Этап 2: Кривая бескупонной доходности
    stage3_bonds: str | None = None  # Этап 3: Нормализация данных по облигациям


# Initialize OpenAI client
openai_client = None


def get_openai_client():
    global openai_client
    if openai_client is None:
        # Get API key from settings (loaded from .env)
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY environment variable is not set. Please set it in .env file."
            )
        # Configure timeout: 25 minutes (1500 seconds) for long-running LLM requests
        # This matches frontend timeout of 20 minutes with some buffer
        openai_client = openai.OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(
                connect=10.0,   # Connection timeout: 10 seconds
                read=1500.0,    # Read timeout: 25 minutes for long LLM responses
                write=10.0,     # Write timeout: 10 seconds
                pool=5.0,       # Pool timeout: 5 seconds
            ),
            max_retries=2,      # Default retry count
        )
    return openai_client


# Промпты для каждого этапа согласно ТЗ
PROMPT_STAGE_1 = """Ты — аналитик долгового рынка. Проанализируй прогноз Банка России и сформируй краткий структурированный вывод, содержащий макрофакторы, влияющие на рынок облигаций. Нужны основные показатели, диапазоны и выводы для облигаций. Текст должен быть кратким и основанным только на существенных данных."""

PROMPT_STAGE_2 = """Ты — аналитик долгового рынка. Проанализируй исторические данные по кривой бескупонной доходности. Определи последние значения, динамику, наклоны и ключевые выводы, влияющие на рынок ОФЗ."""

PROMPT_STAGE_3 = """Ты — модуль нормализации данных. Преврати предоставленные сведения об облигациях в упрощённый список с ключевыми параметрами: тикер, сроки, купон, доходность, дюрация, НКД, спреды. Игнорируй все второстепенные поля."""

PROMPT_STAGE_4 = """Ты — эксперт долгового рынка. Объедини два аналитических документа — прогноз ЦБ и состояние кривой доходности. Сформируй макроаналитическую сводку, отражающую ожидания по ставке, инфляции, кривой и их влияние на доходности."""

PROMPT_STAGE_5 = """Ты — старший аналитик долгового рынка. Используя макроаналитическую сводку и список нормализованных облигаций, подготовь профессиональный развёрнутый текстовый отчёт. Включи описание рыночной ситуации, анализ каждой облигации, выводы и рекомендации. Не используй JSON, пиши только связный аналитический текст."""


async def call_llm_with_data(client: openai.OpenAI, prompt: str, data_content: str, model: str = "gpt-5.1", stage_name: str = "Unknown") -> str:
    """
    Вызывает LLM с промптом и данными.
    Возвращает ответ модели или выбрасывает исключение.
    """
    full_prompt = f"""{prompt}

ДАННЫЕ:

{data_content}

Используй эти данные для анализа."""
    
    system_message = "Ты финансовый аналитик, специализирующийся на анализе облигаций. Весь ответ должен быть строго на русском языке. Используй только конкретные числа из предоставленных данных."
    
    print(f"\n{'='*80}")
    print(f"[LLM DEBUG] {stage_name}")
    print(f"{'='*80}")
    print(f"[LLM DEBUG] Model: {model}")
    print(f"[LLM DEBUG] Prompt length: {len(prompt)} chars")
    print(f"[LLM DEBUG] Data content length: {len(data_content)} chars")
    print(f"[LLM DEBUG] Full prompt length: {len(full_prompt)} chars")
    print(f"\n[LLM DEBUG] Full prompt:")
    print(f"{full_prompt}")
    
    try:
        # Для моделей GPT-5.1 используем reasoning_effort и verbosity
        # Для других моделей эти параметры могут не поддерживаться
        request_params = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "max_completion_tokens": 32000,
        }
        
        # Добавляем reasoning_effort и verbosity только для моделей GPT-5.x
        if model.startswith("gpt-5"):
            request_params["reasoning_effort"] = "high"
            request_params["verbosity"] = "high"
        
        print(f"\n[LLM DEBUG] Request parameters:")
        print(f"  - model: {request_params['model']}")
        print(f"  - max_completion_tokens: {request_params['max_completion_tokens']}")
        if 'reasoning_effort' in request_params:
            print(f"  - reasoning_effort: {request_params['reasoning_effort']}")
        if 'verbosity' in request_params:
            print(f"  - verbosity: {request_params['verbosity']}")
        print(f"  - messages count: {len(request_params['messages'])}")
        print(f"\n[LLM DEBUG] Sending request to OpenAI API...")
        
        response = client.chat.completions.create(**request_params)
        
        # Детальная диагностика ответа
        print(f"\n[LLM DEBUG] Response structure:")
        print(f"  - Response type: {type(response)}")
        print(f"  - Choices count: {len(response.choices) if response.choices else 0}")
        
        if not response.choices or len(response.choices) == 0:
            print(f"\n[LLM DEBUG] ERROR: No choices in response")
            print(f"  - Full response object: {response}")
            raise HTTPException(
                status_code=500,
                detail="Модель не вернула варианты ответа. Попробуйте позже."
            )
        
        choice = response.choices[0]
        print(f"  - Finish reason: {choice.finish_reason}")
        print(f"  - Message type: {type(choice.message)}")
        print(f"  - Message content type: {type(choice.message.content)}")
        print(f"  - Message content value: {repr(choice.message.content)}")
        
        result = choice.message.content
        
        # Проверка finish_reason
        if choice.finish_reason and choice.finish_reason != "stop":
            print(f"\n[LLM DEBUG] WARNING: Finish reason is '{choice.finish_reason}', not 'stop'")
            if choice.finish_reason == "length":
                if result and result.strip():
                    # Есть частичный ответ - используем его, но предупреждаем
                    print(f"\n[LLM DEBUG] WARNING: Response was truncated due to token limit, but partial content is available")
                    print(f"  - Partial content length: {len(result)} chars")
                else:
                    # Нет контента при length - это ошибка
                    print(f"\n[LLM DEBUG] ERROR: Response was truncated but no content available")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Ответ модели был обрезан из-за превышения лимита токенов (32000). Попробуйте уменьшить объем данных."
                    )
            elif choice.finish_reason == "content_filter":
                raise HTTPException(
                    status_code=500,
                    detail="Ответ модели был отфильтрован системой безопасности."
                )
        
        # Проверка на None и пустую строку
        if result is None:
            print(f"\n[LLM DEBUG] ERROR: Model returned None content")
            print(f"  - Finish reason: {choice.finish_reason}")
            print(f"  - Full response: {response}")
            raise HTTPException(
                status_code=500,
                detail="Модель вернула пустой ответ (None). Возможно, используется reasoning mode. Попробуйте позже или измените параметры модели."
            )
        
        if not result.strip():
            print(f"\n[LLM DEBUG] ERROR: Model returned empty string content")
            print(f"  - Finish reason: {choice.finish_reason}")
            print(f"  - Full response object: {response}")
            raise HTTPException(
                status_code=500,
                detail="Модель вернула пустую строку. Возможно, ответ был обрезан до начала генерации. Попробуйте уменьшить объем входных данных."
            )
        
        print(f"\n[LLM DEBUG] Response received:")
        print(f"  - Response length: {len(result)} chars")
        print(f"  - Response (first 1000 chars):")
        print(f"{result[:1000]}...")
        if len(result) > 1000:
            print(f"[LLM DEBUG] ... (truncated, total {len(result)} chars)")
        print(f"\n[LLM DEBUG] Full response:")
        print(f"{result}")
        print(f"\n{'='*80}")
        print(f"[LLM DEBUG] {stage_name} - COMPLETE")
        print(f"{'='*80}\n")
        
        return result
    
    except openai.APIError as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.json() if hasattr(e.response, 'json') else {}
                error_detail = f"{error_detail}. Details: {error_body}"
            except:
                pass
        print(f"\n[LLM DEBUG] {stage_name} - API ERROR:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error detail: {error_detail}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI API error: {error_detail}"
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n[LLM DEBUG] {stage_name} - UNEXPECTED ERROR:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        print(f"  Traceback:")
        print(f"{error_trace}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Error calling LLM: {str(e)}"
        )


@router.post("/analyze", response_model=LLMAnalysisResponse)
async def analyze_bonds(
    bonds_file: UploadFile = File(..., description="JSON file with bonds data"),
    zerocupon_file: UploadFile = File(None, description="JSON file with zero-coupon yield curve data (optional)"),
    forecast_file: UploadFile = File(None, description="JSON file with forecast data (optional)"),
    model: str = "gpt-5.1"
):
    """
    Analyze bonds using LLM with multi-stage pipeline.
    
    Implements 5-stage processing according to technical specification:
    1. Process forecast data -> forecast_summary
    2. Process zero-coupon yield curve -> yieldcurve_summary
    3. Normalize bonds data -> bonds_normalized
    4. Combine macro data (forecast_summary + yieldcurve_summary) -> macro_overview
    5. Final analysis (bonds_normalized + macro_overview) -> final report
    
    Only the final report (stage 5) is returned to the user.
    All intermediate stages are processed internally.
    """
    try:
        client = get_openai_client()
        
        print(f"[LLM Pipeline] Starting multi-stage analysis...")
        
        # Save uploaded files to temporary directory (using LLM storage as in current implementation)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save files to temporary storage
            print(f"[LLM Pipeline] Stage 0: Saving uploaded files to temporary storage...")
            
            # Bonds file is always required
            bonds_path = temp_path / "bonds_export.json"
            with open(bonds_path, "wb") as f:
                content = await bonds_file.read()
                f.write(content)
            print(f"[LLM Pipeline] Bonds file saved: {len(content)} bytes")
            
            # Check which optional files are provided
            has_forecast = forecast_file is not None and forecast_file.filename
            has_zerocupon = zerocupon_file is not None and zerocupon_file.filename
            
            forecast_path = None
            zerocupon_path = None
            
            if has_forecast:
                forecast_path = temp_path / "forecast.json"
                with open(forecast_path, "wb") as f:
                    content = await forecast_file.read()
                    f.write(content)
                print(f"[LLM Pipeline] Forecast file saved: {len(content)} bytes")
            
            if has_zerocupon:
                zerocupon_path = temp_path / "zerocupon.json"
                with open(zerocupon_path, "wb") as f:
                    content = await zerocupon_file.read()
                    f.write(content)
                print(f"[LLM Pipeline] Zerocupon file saved: {len(content)} bytes")
            
            # ========== ЭТАП 1: Обработка прогноза Банка России (опционально) ==========
            forecast_summary = ""
            if has_forecast:
                print(f"[LLM Pipeline] Stage 1: Processing forecast data...")
                with open(forecast_path, "r", encoding="utf-8") as f:
                    forecast_content = json.load(f)
                forecast_json_str = json.dumps(forecast_content, ensure_ascii=False, indent=2)
                
                forecast_summary = await call_llm_with_data(
                    client, PROMPT_STAGE_1, forecast_json_str, model, "STAGE 1: Forecast Analysis"
                )
                print(f"[LLM Pipeline] Stage 1 complete: forecast_summary length = {len(forecast_summary)} chars")
            else:
                print(f"[LLM Pipeline] Stage 1: SKIPPED (forecast file not provided)")
            
            # ========== ЭТАП 2: Анализ кривой бескупонной доходности (опционально) ==========
            yieldcurve_summary = ""
            if has_zerocupon:
                print(f"[LLM Pipeline] Stage 2: Processing zero-coupon yield curve...")
                with open(zerocupon_path, "r", encoding="utf-8") as f:
                    zerocupon_content = json.load(f)
                zerocupon_json_str = json.dumps(zerocupon_content, ensure_ascii=False, indent=2)
                
                # Проверка размера данных
                data_size_mb = len(zerocupon_json_str.encode('utf-8')) / (1024 * 1024)
                print(f"[LLM Pipeline] Stage 2: Zerocupon data size: {data_size_mb:.2f} MB ({len(zerocupon_json_str)} chars)")
                
                # Если данные слишком большие, предупреждаем
                if data_size_mb > 2.0:  # Больше 2 МБ
                    print(f"[LLM Pipeline] WARNING: Zerocupon data is very large ({data_size_mb:.2f} MB). This may cause token limit issues.")
                
                yieldcurve_summary = await call_llm_with_data(
                    client, PROMPT_STAGE_2, zerocupon_json_str, model, "STAGE 2: Zero-Coupon Yield Curve Analysis"
                )
                print(f"[LLM Pipeline] Stage 2 complete: yieldcurve_summary length = {len(yieldcurve_summary)} chars")
            else:
                print(f"[LLM Pipeline] Stage 2: SKIPPED (zerocupon file not provided)")
            
            # ========== ЭТАП 3: Нормализация данных по облигациям (всегда выполняется) ==========
            print(f"[LLM Pipeline] Stage 3: Normalizing bonds data...")
            with open(bonds_path, "r", encoding="utf-8") as f:
                bonds_content = json.load(f)
            bonds_json_str = json.dumps(bonds_content, ensure_ascii=False, indent=2)
            
            bonds_normalized = await call_llm_with_data(
                client, PROMPT_STAGE_3, bonds_json_str, model, "STAGE 3: Bonds Data Normalization"
            )
            print(f"[LLM Pipeline] Stage 3 complete: bonds_normalized length = {len(bonds_normalized)} chars")
            
            # ========== ЭТАП 4: Объединение макроданных (опционально, только если есть макроданные) ==========
            macro_overview = ""
            if has_forecast or has_zerocupon:
                print(f"[LLM Pipeline] Stage 4: Combining macro data...")
                macro_parts = []
                if has_forecast and forecast_summary:
                    macro_parts.append(f"=== ПРОГНОЗ БАНКА РОССИИ ===\n{forecast_summary}")
                if has_zerocupon and yieldcurve_summary:
                    macro_parts.append(f"=== КРИВАЯ БЕСКУПОННОЙ ДОХОДНОСТИ ===\n{yieldcurve_summary}")
                
                if macro_parts:
                    macro_data = "\n\n".join(macro_parts)
                    macro_overview = await call_llm_with_data(
                        client, PROMPT_STAGE_4, macro_data, model, "STAGE 4: Macro Data Combination"
                    )
                    print(f"[LLM Pipeline] Stage 4 complete: macro_overview length = {len(macro_overview)} chars")
                else:
                    print(f"[LLM Pipeline] Stage 4: SKIPPED (no macro data available)")
            else:
                print(f"[LLM Pipeline] Stage 4: SKIPPED (no macro data files provided)")
            
            # ========== ЭТАП 5: Итоговый аналитический отчёт ==========
            print(f"[LLM Pipeline] Stage 5: Generating final analytical report...")
            final_parts = []
            if macro_overview:
                final_parts.append(f"=== МАКРОАНАЛИТИЧЕСКАЯ СВОДКА ===\n{macro_overview}")
            final_parts.append(f"=== НОРМАЛИЗОВАННЫЕ ДАННЫЕ ПО ОБЛИГАЦИЯМ ===\n{bonds_normalized}")
            
            final_data = "\n\n".join(final_parts)
            
            final_report = await call_llm_with_data(
                client, PROMPT_STAGE_5, final_data, model, "STAGE 5: Final Analytical Report"
            )
            print(f"[LLM Pipeline] Stage 5 complete: final_report length = {len(final_report)} chars")
            print(f"[LLM Pipeline] All stages complete. Returning final report to user.")
            
            return LLMAnalysisResponse(
                analysis=final_report,
                model_used=model,
                stage1_forecast=forecast_summary if has_forecast else None,
                stage2_zerocupon=yieldcurve_summary if has_zerocupon else None,
                stage3_bonds=bonds_normalized,
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except openai.APIError as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.json() if hasattr(e.response, 'json') else {}
                error_detail = f"{error_detail}. Response: {error_body}"
            except:
                pass
        print(f"[LLM Pipeline] OpenAI API error: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI API error: {error_detail}"
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[LLM Pipeline] Unexpected error: {type(e).__name__}: {str(e)}")
        print(f"[LLM Pipeline] Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during LLM analysis: {str(e)}"
        )

