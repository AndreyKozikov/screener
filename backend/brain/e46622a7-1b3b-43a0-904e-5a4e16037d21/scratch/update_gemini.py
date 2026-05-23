
import sys
import re

path = r'd:\Andrew\GeekBrains\Python\BondsScreener\backend\app\services\gemini_analysis_service.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
content = content.replace(
    'from config.llm_prompts import build_floater_analysis_prompt',
    'from config.llm_prompts import build_floater_analysis_prompt, build_qa_prompt'
)

# Add method
method_code = """
    def answer_question(
        self,
        context: str,
        query: str,
        model: Optional[str] = None,
    ) -> str:
        \"\"\"Отвечает на вопрос пользователя на основе предоставленного контекста.

        Args:
            context: Текстовый контекст (результат векторного поиска).
            query: Вопрос пользователя.
            model: Идентификатор модели Gemini.

        Returns:
            Текст ответа.
        \"\"\"
        prompt: str = build_qa_prompt(context=context, query=query)
        model_id: str = model or GEMINI_MODEL_3_FLASH

        logger.info(
            "[GEMINI] QA Запрос: длина контекста=%d, длина вопроса=%d → %s",
            len(context), len(query), model_id
        )

        try:
            return self._client.generate(prompt, model=model_id)
        except Exception as exc:
            logger.error("[GEMINI] Ошибка в QA-запросе: %s", exc)
            return f"Извините, не удалось получить ответ от модели: {str(exc)}"
"""

# Insert before _parse_json_response
if 'def _parse_json_response' in content:
    content = content.replace('def _parse_json_response', method_code + '\n\ndef _parse_json_response')
else:
    print("Error: _parse_json_response not found")
    sys.exit(1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated gemini_analysis_service.py")
