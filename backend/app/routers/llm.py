from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
import tempfile
from pathlib import Path
from app.config import settings

router = APIRouter(prefix="/api/llm", tags=["llm"])


class LLMAnalysisRequest(BaseModel):
    model: str = "gpt-5-mini"  # Using GPT-5-mini model


class LLMAnalysisResponse(BaseModel):
    analysis: str
    model_used: str


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
        openai_client = openai.OpenAI(api_key=api_key)
    return openai_client


PROMPT_TEMPLATE = """**Используй данные из следующих файлов:

bonds_data.json — характеристики и рыночные параметры облигаций;

forecast_data.json — прогнозы ставок, инфляции, макроэкономики;

zerocupon_data.json — кривая бескупонной доходности.**

На основе этих файлов проведи детальный, числовой анализ одной или нескольких указанных мной облигаций.

Запрещено ограничиваться описанием методологии — необходимо выполнить фактический анализ с конкретными числами из файлов.

Выполни строго все пункты:

1. Текущие параметры каждой облигации

Для каждой указанной мной облигации обязательно:

рыночная цена;

доходность к погашению;

купон и график выплат;

НКД;

дюрация;

Z-спрэд (если есть в данных);

объём торгов и ликвидность.

Используй только данные из bonds_data.json.

2. Сопоставление с бескупонной кривой

На основании даты последней котировки:

найди срок до погашения;

найди соответствующий срок на кривой zerocupon_data.json;

сравни доходность облигации с доходностью БКД;

сделай вывод: торгуется с премией или дисконтом.

3. Анализ чувствительности цены (interest rate risk)

Выполни реальные расчёты:

оцени изменение цены при +1 п.п., +2 п.п., –1 п.п.

используй дюрацию и приближение через DV01.

выведи фактические проценты изменения цены.

4. Влияние прогнозов ставок и инфляции

На основе forecast_data.json:

оцени вероятность роста или снижения ставок для горизонтов 1, 3, 5 лет;

сделай конкретные выводы о влиянии на цену облигации;

оцени ожидаемую доходность с учётом сценариев.

5. Анализ рисков

Конкретно, на основании данных:

процентный риск;

инфляционный;

риск реинвестирования купонов;

риск ликвидности;

рыночная волатильность бумаги.

Запрещено использовать общие шаблонные объяснения.

6. Вывод и решение

Обязательные элементы:

держать / докупить / продать — с количественным обоснованием;

перспектива на 1, 3, 5 лет;

аргументы, основанные только на числах;

если заменить — только тип альтернатив без конкретных бумаг.

Формат ответа — строго структура:

Облигация X — текущие параметры

Сравнение с кривой доходности

Чувствительность цены

Влияние макропрогнозов

Риски

Итоговая рекомендация

Весь ответ строго на русском языке. Используй только конкретные числа из файлов.
"""


@router.post("/analyze", response_model=LLMAnalysisResponse)
async def analyze_bonds(
    bonds_file: UploadFile = File(..., description="JSON file with bonds data"),
    zerocupon_file: UploadFile = File(..., description="JSON file with zero-coupon yield curve data"),
    forecast_file: UploadFile = File(..., description="JSON file with forecast data"),
    model: str = "gpt-5-mini"
):
    """
    Analyze bonds using LLM with file uploads.
    
    Takes three JSON data files as uploads:
    - bonds_file: Selected bonds with details and coupons
    - zerocupon_file: Zero-coupon yield curve data
    - forecast_file: Bank of Russia forecast data
    
    Files are read and their contents are embedded in the prompt for Chat Completions API.
    This approach is used because GPT-5.1 is not supported in Assistants API.
    
    Returns analysis in markdown format.
    
    Note: Uses GPT-5-mini via Chat Completions API for analysis capabilities.
    """
    try:
        client = get_openai_client()
        
        print(f"[LLM] Step 1: Saving uploaded files to temporary storage...")
        
        # Save uploaded files to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save bonds file
            bonds_path = temp_path / "bonds_data.json"
            with open(bonds_path, "wb") as f:
                content = await bonds_file.read()
                f.write(content)
            print(f"[LLM] Bonds file saved: {len(content)} bytes")
            
            # Save zerocupon file
            zerocupon_path = temp_path / "zerocupon_data.json"
            with open(zerocupon_path, "wb") as f:
                content = await zerocupon_file.read()
                f.write(content)
            print(f"[LLM] Zerocupon file saved: {len(content)} bytes")
            
            # Save forecast file
            forecast_path = temp_path / "forecast_data.json"
            with open(forecast_path, "wb") as f:
                content = await forecast_file.read()
                f.write(content)
            print(f"[LLM] Forecast file saved: {len(content)} bytes")
            
            print(f"[LLM] Step 2: Reading file contents...")
            
            # Read file contents to include in prompt
            import json
            with open(bonds_path, "r", encoding="utf-8") as f:
                bonds_content = json.load(f)
            bonds_json_str = json.dumps(bonds_content, ensure_ascii=False, indent=2)
            print(f"[LLM] Bonds file read: {len(bonds_json_str)} chars")
            
            with open(zerocupon_path, "r", encoding="utf-8") as f:
                zerocupon_content = json.load(f)
            zerocupon_json_str = json.dumps(zerocupon_content, ensure_ascii=False, indent=2)
            print(f"[LLM] Zerocupon file read: {len(zerocupon_json_str)} chars")
            
            with open(forecast_path, "r", encoding="utf-8") as f:
                forecast_content = json.load(f)
            forecast_json_str = json.dumps(forecast_content, ensure_ascii=False, indent=2)
            print(f"[LLM] Forecast file read: {len(forecast_json_str)} chars")
            
            print(f"[LLM] Step 3: Using Chat Completions API (gpt-5.1 requires Chat Completions, not Assistants API)...")
            
            # Build prompt with file contents
            full_prompt = f"""{PROMPT_TEMPLATE}

ДАННЫЕ ИЗ ФАЙЛОВ:

=== ФАЙЛ bonds_data.json ===
{bonds_json_str}

=== ФАЙЛ forecast_data.json ===
{forecast_json_str}

=== ФАЙЛ zerocupon_data.json ===
{zerocupon_json_str}

Используй эти данные для анализа. Все числа должны быть из этих файлов."""
            
            print(f"[LLM] Total prompt size: {len(full_prompt)} chars")
            print(f"[LLM] Calling Chat Completions API with model: {model}")
            
            # Use Chat Completions API for gpt-5-mini
            # Note: GPT-5 family models use reasoning_effort and verbosity as strings, not objects
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты финансовый аналитик, специализирующийся на анализе облигаций. Весь ответ должен быть строго на русском языке. Используй только конкретные числа из предоставленных данных."
                    },
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                reasoning_effort="high",  # High reasoning for detailed analysis
                verbosity="high",  # High verbosity for detailed explanations
                max_completion_tokens=8000,  # Maximum tokens for completion
            )
            
            analysis_text = response.choices[0].message.content
            print(f"[LLM] Analysis received: {len(analysis_text) if analysis_text else 0} chars")
            
            return LLMAnalysisResponse(
                analysis=analysis_text or "Не удалось получить анализ",
                model_used=model
            )
    
    except openai.APIError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during LLM analysis: {str(e)}"
        )

