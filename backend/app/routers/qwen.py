"""Роутеры для интеграции с Qwen AI через OpenRouter.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов на анализ
облигаций с использованием модели Qwen через OpenRouter API. Реализует
многоэтапный pipeline для комплексного анализа облигаций.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI
from openai import APIError, APITimeoutError, APIConnectionError
import tempfile
import json
import asyncio
from pathlib import Path
from config.settings import settings

router = APIRouter(prefix="/api/qwen", tags=["qwen"])
"""Роутер FastAPI для обработки запросов к API Qwen AI."""


class QwenAnalysisResponse(BaseModel):
    """Модель ответа для анализа облигаций через Qwen AI.
    
    Attributes:
        analysis: Финальный аналитический отчет (этап 5).
        model_used: Название использованной модели.
        stage1_forecast: Результат этапа 1 - анализ прогноза Банка России
            (None если файл прогноза не предоставлен).
        stage2_zerocupon: Результат этапа 2 - анализ кривой бескупонной доходности
            (None если файл кривой не предоставлен).
        stage3_bonds: Результат этапа 3 - нормализация данных по облигациям.
    """
    analysis: str
    """Финальный аналитический отчет (этап 5)."""
    
    model_used: str
    """Название использованной модели."""
    
    stage1_forecast: str | None = None
    """Результат этапа 1: Прогноз Банка России."""
    
    stage2_zerocupon: str | None = None
    """Результат этапа 2: Кривая бескупонной доходности."""
    
    stage3_bonds: str | None = None
    """Результат этапа 3: Нормализация данных по облигациям."""


openai_client: OpenAI | None = None
"""Глобальный экземпляр OpenAI клиента для работы с OpenRouter API."""




def get_openai_client() -> OpenAI:
    """Инициализирует и возвращает OpenAI клиент для работы с OpenRouter API.
    
    Создает и настраивает OpenAI клиент для работы с OpenRouter API, используя
    API ключ из настроек и опциональные заголовки (HTTP-Referer, X-Title).
    Настраивает таймаут 25 минут для длительных запросов к Qwen.
    
    Returns:
        Экземпляр OpenAI клиента, настроенный для работы с OpenRouter API.
    
    Raises:
        HTTPException: Если переменная окружения OPENROUTER_API_KEY не установлена
            (статус 500).
    
    Note:
        Клиент создается один раз и переиспользуется для всех запросов (singleton pattern).
        Таймаут установлен в 25 минут для соответствия таймауту фронтенда (20 минут)
        с небольшим запасом.
    """
    global openai_client
    if openai_client is None:
        # Get API key from settings (loaded from .env)
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY environment variable is not set. Please set it in .env file."
            )
        
        # Настройка заголовков для OpenRouter (опционально)
        # Можно настроить через переменные окружения OPENROUTER_HTTP_REFERER и OPENROUTER_X_TITLE
        default_headers = {}
        if hasattr(settings, 'OPENROUTER_HTTP_REFERER') and settings.OPENROUTER_HTTP_REFERER:
            default_headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
        if hasattr(settings, 'OPENROUTER_X_TITLE') and settings.OPENROUTER_X_TITLE:
            default_headers["X-Title"] = settings.OPENROUTER_X_TITLE
        
        # Configure timeout: 25 minutes (1500 seconds) for long-running Qwen requests
        # This matches frontend timeout of 20 minutes with some buffer
        openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=1500.0,  # 25 minutes in seconds
            default_headers=default_headers if default_headers else None,
        )
    return openai_client


PROMPT_STAGE_1: str = """Ты — аналитик долгового рынка. Проанализируй прогноз Банка России и сформируй краткий структурированный вывод, содержащий макрофакторы, влияющие на рынок облигаций. Нужны основные показатели, диапазоны и выводы для облигаций. Текст должен быть кратким и основанным только на существенных данных."""
"""Промпт для этапа 1: Анализ прогноза Банка России."""

PROMPT_STAGE_2: str = """Ты — аналитик долгового рынка. Проанализируй исторические данные по кривой бескупонной доходности. Определи последние значения, динамику, наклоны и ключевые выводы, влияющие на рынок ОФЗ."""
"""Промпт для этапа 2: Анализ кривой бескупонной доходности."""

PROMPT_STAGE_3: str = """Ты — модуль нормализации данных. Преврати предоставленные сведения об облигациях в упрощённый список с ключевыми параметрами: тикер, сроки, купон, доходность, дюрация, НКД, спреды. Игнорируй все второстепенные поля."""
"""Промпт для этапа 3: Нормализация данных по облигациям."""

PROMPT_STAGE_4: str = """Ты — эксперт долгового рынка. Объедини два аналитических документа — прогноз ЦБ и состояние кривой доходности. Сформируй макроаналитическую сводку, отражающую ожидания по ставке, инфляции, кривой и их влияние на доходности."""
"""Промпт для этапа 4: Объединение макроданных."""

PROMPT_STAGE_5: str = """Ты — старший аналитик долгового рынка. Используя макроаналитическую сводку и список нормализованных облигаций, подготовь профессиональный развёрнутый текстовый отчёт. Включи описание рыночной ситуации, анализ каждой облигации, выводы и рекомендации. Не используй JSON, пиши только связный аналитический текст."""
"""Промпт для этапа 5: Итоговый аналитический отчет."""




async def call_qwen_with_data(
    client: OpenAI, 
    prompt: str, 
    data_content: str, 
    model: str = "qwen/qwen3-235b-a22b:free", 
    stage_name: str = "Unknown",
    wait_before: bool = False
) -> str:
    """Вызывает Qwen через OpenRouter с промптом и данными используя OpenAI клиент.
    
    Выполняет запрос к модели Qwen через OpenRouter API с указанным промптом и данными.
    Поддерживает паузу перед запросом для соблюдения ограничений rate limit организации.
    
    Args:
        client: Экземпляр OpenAI клиента для выполнения запросов.
        prompt: Промпт для модели с инструкциями по анализу.
        data_content: Данные для анализа в формате JSON строки.
        model: Название модели для использования (по умолчанию "qwen/qwen3-235b-a22b:free").
        stage_name: Название этапа для логирования и отладки.
        wait_before: Если True, ожидает 60 секунд перед запросом для соблюдения
            ограничений rate limit организации.
    
    Returns:
        Ответ модели (строка с результатом анализа).
    
    Raises:
        HTTPException: Если модель не вернула ответ (статус 500),
            если произошла ошибка API OpenRouter (статус 502),
            если произошел таймаут (статус 504),
            если произошла ошибка соединения (статус 503),
            или если произошла другая ошибка (статус 500).
    
    Note:
        Максимальное количество токенов установлено в 32000 для длинных ответов.
        Заголовки HTTP-Referer и X-Title настраиваются через default_headers
        при инициализации клиента.
    """
    # Пауза перед запросом, если требуется (для соблюдения ограничений организации)
    if wait_before:
        print(f"[QWEN] Waiting 60 seconds before {stage_name} (rate limit)...")
        await asyncio.sleep(60)
        print(f"[QWEN] Wait complete, proceeding with {stage_name}")
    
    full_prompt = f"""{prompt}

ДАННЫЕ:

{data_content}

Используй эти данные для анализа."""
    
    system_message = "Ты финансовый аналитик, специализирующийся на анализе облигаций. Весь ответ должен быть строго на русском языке. Используй только конкретные числа из предоставленных данных."
    
    print(f"\n{'='*80}")
    print(f"[QWEN DEBUG] {stage_name}")
    print(f"{'='*80}")
    print(f"[QWEN DEBUG] Model: {model}")
    print(f"[QWEN DEBUG] Prompt length: {len(prompt)} chars")
    print(f"[QWEN DEBUG] Data content length: {len(data_content)} chars")
    print(f"[QWEN DEBUG] Full prompt length: {len(full_prompt)} chars")
    print(f"\n[QWEN DEBUG] Full prompt:")
    print(f"{full_prompt}")
    
    try:
        print(f"\n[QWEN DEBUG] Request parameters:")
        print(f"  - model: {model}")
        print(f"  - max_tokens: 32000")
        print(f"  - messages count: 2")
        print(f"\n[QWEN DEBUG] Sending request to OpenRouter API via OpenAI client...")
        
        # Используем рекомендованный подход с OpenAI клиентом
        # extra_headers и extra_body передаются как параметры (поддерживается OpenAI SDK при использовании с кастомным base_url)
        # Заголовки HTTP-Referer и X-Title уже настроены через default_headers при инициализации клиента
        completion = client.chat.completions.create(
            extra_headers={},  # Можно добавить дополнительные заголовки здесь, если нужно
            extra_body={},     # Можно добавить дополнительные параметры в body здесь, если нужно
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            max_tokens=32000,
        )
        
        # Извлекаем ответ из completion
        if not completion.choices or len(completion.choices) == 0:
            print(f"\n[QWEN DEBUG] ERROR: Model returned no choices")
            raise HTTPException(
                status_code=500,
                detail="Модель не вернула ответ. Попробуйте позже."
            )
        
        result = completion.choices[0].message.content
        
        if not result:
            print(f"\n[QWEN DEBUG] ERROR: Model returned empty response")
            raise HTTPException(
                status_code=500,
                detail="Модель не вернула ответ. Попробуйте позже."
            )
        
        print(f"\n[QWEN DEBUG] Response received:")
        print(f"  - Response length: {len(result)} chars")
        print(f"  - Response (first 1000 chars):")
        print(f"{result[:1000]}...")
        if len(result) > 1000:
            print(f"[QWEN DEBUG] ... (truncated, total {len(result)} chars)")
        print(f"\n[QWEN DEBUG] Full response:")
        print(f"{result}")
        print(f"\n{'='*80}")
        print(f"[QWEN DEBUG] {stage_name} - COMPLETE")
        print(f"{'='*80}\n")
        
        return result
    
    except APIError as e:
        # Handle OpenAI API errors
        error_detail = str(e)
        error_code = e.status_code if hasattr(e, 'status_code') else 500
        error_message = e.message if hasattr(e, 'message') else "OpenRouter API error"
        
        print(f"\n[QWEN DEBUG] {stage_name} - API ERROR:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error code: {error_code}")
        print(f"  Error message: {error_message}")
        print(f"  Full error: {error_detail}")
        print(f"{'='*80}\n")
        
        raise HTTPException(
            status_code=error_code if isinstance(error_code, int) and 400 <= error_code < 600 else 502,
            detail=f"OpenRouter API error: {error_message}"
        )
    except (APITimeoutError, APIConnectionError) as e:
        # Handle timeout and connection errors
        error_detail = str(e)
        print(f"\n[QWEN DEBUG] {stage_name} - CONNECTION/TIMEOUT ERROR:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {error_detail}")
        print(f"{'='*80}\n")
        
        raise HTTPException(
            status_code=504 if isinstance(e, APITimeoutError) else 503,
            detail=f"Connection error: {error_detail}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n[QWEN DEBUG] {stage_name} - UNEXPECTED ERROR:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        print(f"  Traceback:")
        print(f"{error_trace}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Qwen: {str(e)}"
        )


@router.post("/analyze", response_model=QwenAnalysisResponse)
async def analyze_bonds_with_qwen(
    bonds_file: UploadFile = File(..., description="JSON file with bonds data"),
    zerocupon_file: UploadFile = File(None, description="JSON file with zero-coupon yield curve data (optional)"),
    forecast_file: UploadFile = File(None, description="JSON file with forecast data (optional)"),
    model: str = "qwen/qwen3-235b-a22b:free"
):
    """Анализирует облигации используя Qwen 3 через OpenRouter с многоэтапным pipeline.
    
    Реализует 5-этапную обработку согласно техническому заданию:
    1. Обработка прогноза Банка России -> forecast_summary (опционально)
    2. Обработка кривой бескупонной доходности -> yieldcurve_summary (опционально)
    3. Нормализация данных по облигациям -> bonds_normalized (всегда выполняется)
    4. Объединение макроданных (forecast_summary + yieldcurve_summary) -> macro_overview
       (выполняется только если предоставлены макроданные)
    5. Итоговый анализ (bonds_normalized + macro_overview) -> final report
    
    Args:
        bonds_file: JSON файл с данными об облигациях (обязательный).
        zerocupon_file: JSON файл с данными кривой бескупонной доходности (опционально).
        forecast_file: JSON файл с прогнозными данными Банка России (опционально).
        model: Название модели для использования (по умолчанию "qwen/qwen3-235b-a22b:free").
    
    Returns:
        Объект QwenAnalysisResponse с результатами анализа, содержащий:
        - analysis: Финальный аналитический отчет (этап 5)
        - model_used: Название использованной модели
        - stage1_forecast: Результат этапа 1 (None если файл прогноза не предоставлен)
        - stage2_zerocupon: Результат этапа 2 (None если файл кривой не предоставлен)
        - stage3_bonds: Результат этапа 3 (нормализация данных по облигациям)
    
    Raises:
        HTTPException: Если произошла ошибка при чтении файлов (статус 500),
            если произошла ошибка при вызове API Qwen (статус 502/503/504/500),
            или если произошла другая ошибка во время анализа (статус 500).
    
    Note:
        Между этапами добавляется пауза 60 секунд для соблюдения ограничений
        rate limit организации (если был предыдущий запрос). Все промежуточные этапы
        обрабатываются внутренне, пользователю возвращается только финальный отчет.
    """
    try:
        client = get_openai_client()
        
        print(f"[QWEN Pipeline] Starting multi-stage analysis...")
        
        # Save uploaded files to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save files to temporary storage
            print(f"[QWEN Pipeline] Stage 0: Saving uploaded files to temporary storage...")
            
            # Bonds file is always required
            bonds_path = temp_path / "bonds_export.json"
            with open(bonds_path, "wb") as f:
                content = await bonds_file.read()
                f.write(content)
            print(f"[QWEN Pipeline] Bonds file saved: {len(content)} bytes")
            
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
                print(f"[QWEN Pipeline] Forecast file saved: {len(content)} bytes")
            
            if has_zerocupon:
                zerocupon_path = temp_path / "zerocupon.json"
                with open(zerocupon_path, "wb") as f:
                    content = await zerocupon_file.read()
                    f.write(content)
                print(f"[QWEN Pipeline] Zerocupon file saved: {len(content)} bytes")
            
            # Отслеживаем, был ли выполнен предыдущий запрос (для добавления паузы)
            previous_request_made = False
            
            # ========== ЭТАП 1: Обработка прогноза Банка России (опционально) ==========
            forecast_summary = ""
            if has_forecast:
                print(f"[QWEN Pipeline] Stage 1: Processing forecast data...")
                with open(forecast_path, "r", encoding="utf-8") as f:
                    forecast_content = json.load(f)
                forecast_json_str = json.dumps(forecast_content, ensure_ascii=False, indent=2)
                
                forecast_summary = await call_qwen_with_data(
                    client, PROMPT_STAGE_1, forecast_json_str, model, "STAGE 1: Forecast Analysis",
                    wait_before=False  # Первый запрос, пауза не нужна
                )
                print(f"[QWEN Pipeline] Stage 1 complete: forecast_summary length = {len(forecast_summary)} chars")
                previous_request_made = True
            else:
                print(f"[QWEN Pipeline] Stage 1: SKIPPED (forecast file not provided)")
            
            # ========== ЭТАП 2: Анализ кривой бескупонной доходности (опционально) ==========
            yieldcurve_summary = ""
            if has_zerocupon:
                print(f"[QWEN Pipeline] Stage 2: Processing zero-coupon yield curve...")
                with open(zerocupon_path, "r", encoding="utf-8") as f:
                    zerocupon_content = json.load(f)
                zerocupon_json_str = json.dumps(zerocupon_content, ensure_ascii=False, indent=2)
                
                yieldcurve_summary = await call_qwen_with_data(
                    client, PROMPT_STAGE_2, zerocupon_json_str, model, "STAGE 2: Zero-Coupon Yield Curve Analysis",
                    wait_before=previous_request_made  # Пауза нужна, если был предыдущий запрос
                )
                print(f"[QWEN Pipeline] Stage 2 complete: yieldcurve_summary length = {len(yieldcurve_summary)} chars")
                previous_request_made = True
            else:
                print(f"[QWEN Pipeline] Stage 2: SKIPPED (zerocupon file not provided)")
            
            # ========== ЭТАП 3: Нормализация данных по облигациям (всегда выполняется) ==========
            print(f"[QWEN Pipeline] Stage 3: Normalizing bonds data...")
            with open(bonds_path, "r", encoding="utf-8") as f:
                bonds_content = json.load(f)
            bonds_json_str = json.dumps(bonds_content, ensure_ascii=False, indent=2)
            
            bonds_normalized = await call_qwen_with_data(
                client, PROMPT_STAGE_3, bonds_json_str, model, "STAGE 3: Bonds Data Normalization",
                wait_before=previous_request_made  # Пауза нужна, если был предыдущий запрос
            )
            print(f"[QWEN Pipeline] Stage 3 complete: bonds_normalized length = {len(bonds_normalized)} chars")
            previous_request_made = True
            
            # ========== ЭТАП 4: Объединение макроданных (опционально, только если есть макроданные) ==========
            macro_overview = ""
            if has_forecast or has_zerocupon:
                print(f"[QWEN Pipeline] Stage 4: Combining macro data...")
                macro_parts = []
                if has_forecast and forecast_summary:
                    macro_parts.append(f"=== ПРОГНОЗ БАНКА РОССИИ ===\n{forecast_summary}")
                if has_zerocupon and yieldcurve_summary:
                    macro_parts.append(f"=== КРИВАЯ БЕСКУПОННОЙ ДОХОДНОСТИ ===\n{yieldcurve_summary}")
                
                if macro_parts:
                    macro_data = "\n\n".join(macro_parts)
                    macro_overview = await call_qwen_with_data(
                        client, PROMPT_STAGE_4, macro_data, model, "STAGE 4: Macro Data Combination",
                        wait_before=previous_request_made  # Пауза нужна, если был предыдущий запрос
                    )
                    print(f"[QWEN Pipeline] Stage 4 complete: macro_overview length = {len(macro_overview)} chars")
                    previous_request_made = True
                else:
                    print(f"[QWEN Pipeline] Stage 4: SKIPPED (no macro data available)")
            else:
                print(f"[QWEN Pipeline] Stage 4: SKIPPED (no macro data files provided)")
            
            # ========== ЭТАП 5: Итоговый аналитический отчёт ==========
            print(f"[QWEN Pipeline] Stage 5: Generating final analytical report...")
            final_parts = []
            if macro_overview:
                final_parts.append(f"=== МАКРОАНАЛИТИЧЕСКАЯ СВОДКА ===\n{macro_overview}")
            final_parts.append(f"=== НОРМАЛИЗОВАННЫЕ ДАННЫЕ ПО ОБЛИГАЦИЯМ ===\n{bonds_normalized}")
            
            final_data = "\n\n".join(final_parts)
            
            final_report = await call_qwen_with_data(
                client, PROMPT_STAGE_5, final_data, model, "STAGE 5: Final Analytical Report",
                wait_before=previous_request_made  # Пауза нужна, если был предыдущий запрос
            )
            print(f"[QWEN Pipeline] Stage 5 complete: final_report length = {len(final_report)} chars")
            print(f"[QWEN Pipeline] All stages complete. Returning final report to user.")
            
            return QwenAnalysisResponse(
                analysis=final_report,
                model_used=model,
                stage1_forecast=forecast_summary if has_forecast else None,
                stage2_zerocupon=yieldcurve_summary if has_zerocupon else None,
                stage3_bonds=bonds_normalized,
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[QWEN Pipeline] Unexpected error: {type(e).__name__}: {str(e)}")
        print(f"[QWEN Pipeline] Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during Qwen analysis: {str(e)}"
        )

