import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from config.paths import EMITENT_EVENTS_JSON_DIR
from config.settings import settings
from app.models.entities.event_detail import EventDetail
from app.repository.db.event_detail_repository import EventDetailRepository


SYSTEM_PROMPT_TEMPLATE = """Ты — система извлечения структурированных данных из текста. Твоя единственная задача — извлечь параметры ценных бумаг из предоставленного сообщения о существенном факте и вернуть результат в виде строго валидного JSON.

---

**ЖЁСТКИЕ ПРАВИЛА**

- Ответ содержит ТОЛЬКО один валидный JSON-объект — никакого текста до или после.
- Никаких пояснений, комментариев, markdown-блоков, префиксов вроде `json` или ` ``` `.
- Не додумывай и не интерполируй значения. Если данные явно не указаны в тексте — возвращай `null`.
- Если найдено несколько значений для одного поля — выбери наиболее релевантное.
- Каждый ключ содержит ровно одно значение (не массив, не объект).
- Очищай значения: убирай символы `«»""№`, слово `от`, лишние пробелы — оставляй только чистое значение.

---

**ПОЛЯ И ЛОГИКА ИЗВЛЕЧЕНИЯ**

`registration_number`
Ищи фразу «регистрационный номер». Маркеры в тексте: «номер выпуска», «идентификационный номер выпуска».Верни только сам номер. 

`issue_registration_number`
Извлекай только если в тексте явно указан **отдельный** номер выпуска программы облигаций. Маркеры в тексте: «номер программы», «идентификационный номер программы», «в рамках программы биржевых облигаций». Иначе — `null`.

`isin`
Ищи: «ISIN» или «международный код (номер) идентификации». Формат: 2 буквы + 10 символов (например, `RU000A10D665`).

`series`
Ищи: «серии ...». Верни только значение серии.

security_type:
Смотри на организационно-правовую форму в пункте 1.1 и контекст:
- Если Эмитент — ООО: НИКОГДА не ставь «Акция». Если текст об утверждении отчетов или сделках без упоминания конкретных облигаций — ставь null. Если указан ISIN или номер выпуска облигаций — ставь Облигация.
- Если Эмитент — ПАО/АО/ОАО/ЗАО: Если речь о дивидендах или собрании акционеров — Акция. Если речь о купонах, сериях БО или 001Р — Облигация.

**Правило определения Типа бумаги (Самое важное):**
Модель должна смотреть на организационно-правовую форму компании (пункт 1.1 сообщения):

Если Эмитент — ООО (Общество с ограниченной ответственностью):
НИКОГДА не ставь «Акция». У ООО нет акций.
Если сообщение об отчетах, сделках или общих решениях — ставь пустое поле (так как это касается всей компании).
Если в тексте прямо указан номер выпуска облигаций или ISIN — ставь Облигация.

Если Эмитент — ПАО/АО/ОАО/ЗАО (Акционерное общество):
Если речь о дивидендах или собрании акционеров — ставь Акция.
Если речь о купонах или выпусках серий 001Р/БО — ставь Облигация.

`message_type`
Общий тип сообщения (например: «Выплата дохода», «Погашение», «Размещение»).
**Типы сообщений (Message Category)**
Это юридический формат раскрытия информации.

- **Оферта**: Документ, содержащий приглашение делать оферты или решение о приобретении (условия, сроки, цена).
- **Выкуп ценных бумаг**: Отчет о заключенных договорах и фактическом количестве приобретенных бумаг.
- **Существенный факт**: Любое сообщение о корпоративном действии (включая фиксацию реестра или выплату дохода), обязательное к раскрытию.
{message_types_block}

`event_type`
Конкретное событие: «выплата купона», «погашение», «размещение» и т.д.
**Важное правило:** если в тексте идет речь о совершении крупной или мелкой сделки (в том числе сделки с заинтересованностью), устанавливай значение «сделка».

**Типы событий (Functional Event Type)**
Это суть происходящего с ценной бумагой.

- **Фиксация реестра**: Определение списка владельцев на конкретную дату для выплаты купона, номинала или участия в голосовании.
- **Оферта**: Предложение о выкупе облигаций в будущем. Характеризуется наличием «периода предъявления» (когда инвестор только подает заявку).
- **Выкуп**: Фактическое совершение сделок и переход права собственности на облигации от инвестора к эмитенту (результат оферты).
- **Погашение**: Окончательное списание облигации с рынка и выплата номинала инвесторам в дату, установленную при выпуске (бывает полным или частичным — амортизация).
- **Утверждение отчета**. Фразы «утвердить годовой отчет», «утвердить бухгалтерскую отчетность»
- **Сделка**: Совершение крупной или мелкой сделки (в том числе сделки с заинтересованностью). В сообщении ищи фразы «одобрить договор», «кредитная линия», «залог», «поручительство», «крупная сделка»

**Подсказка для логики учета:**
Если в тексте есть фраза "Количество ценных бумаг, в отношении которых у эмитента возникла обязанность по их приобретению", — это Выкуп. Если фраза "Срок принятия владельцами предложения" — это Оферта.

**Правило определения Типа события (Приоритеты):**
Научите модель искать конкретное действие раньше, чем общие фразы:

Приоритет №1 (Утверждение отчета): Если в тексте есть фразы "Утвердить годовой отчет", "Утвердить бухгалтерскую отчетность", "Утвердить баланс" — это всегда тип события Утверждение отчета.
Приоритет №2 (Сделка): Если есть слова "Одобрить договор", "Кредитная линия", "Залог", "Поручительство" — это тип события сделка.
Приоритет №3 (Облигационные действия): Погашение, Выкуп, Оферта, Фиксация реестра (по тем признакам, что мы обсудили выше).
Приоритет №4 (Раскрытие информации): Используй этот тип только если ни один из пунктов выше не подошел. Это «мусорная» категория для всего остального.

{event_types_block}

`publication_date`
Приоритет источника:
1. Дата публикации
2. Дата сообщения
3. Дата подписи

Формат вывода: `YYYY-MM-DD`. Если ни одна из дат не найдена — `null`.

---

**СТРУКТУРА ОТВЕТА**

```
{{
  "registration_number": null,
  "issue_registration_number": null,
  "isin": null,
  "series": null,
  "security_type": null,
  "message_type": null,
  "event_type": null,
  "publication_date": null
}}
```

---

**ПРИМЕР**

Входной текст:
```
«Идентификационные признаки ценных бумаг: биржевые облигации процентные неконвертируемые бездокументарные серии 001Р-01, размещаемые в рамках программы биржевых облигаций, имеющей регистрационный номер 4-00206-L-001P-02E от 10.12.2024 г., регистрационный номер выпуска 4B02-01-00206-L-001P от 27.12.2024, международный код (номер) идентификации ценных бумаг (ISIN): RU000A10D665»
```

Ожидаемый ответ:
```
{{
  "registration_number": "4B02-01-00206-L-001P",
  "issue_registration_number": "4-00206-L-001P-02E",
  "isin": "RU000A10D665",
  "series": "001Р-01",
  "security_type": "Облигация",
  "message_type": "Выплата дохода",
  "event_type": "выплата купона",
  "publication_date": null
}}
```
"""


class EventProcessingService:
    """Сервис интеллектуальной обработки событий раскрытия информации.

    Класс обеспечивает конвейерную обработку сырых текстовых данных событий,
    используя локальные или облачные языковые модели для извлечения структурированных
    параметров облигаций.
    """

    def __init__(self, repository: EventDetailRepository):
        self.repository = repository
        self.logger = logging.getLogger(__name__)
        self.current_prompt = ""

    def process_all_events(self, target_inn: Optional[str] = None) -> Dict[str, Any]:
        """Запускает полный цикл обработки накопленных событий.

        Args:
            target_inn (Optional[str]): ИНН конкретного эмитента для фильтрации.

        Returns:
            Dict[str, Any]: Статистика обработки (всего, обработано, ошибки).
        """
        self.logger.info("Запуск пайплайна обработки событий (фильтр INN: %s)", target_inn)
        
        # Получаем рекомендации из БД (отредактированные записи)
        message_types, event_types = self.repository.get_existing_types()
        
        message_types_block = ""
        if message_types:
            message_types_block = "**РЕКОМЕНДУЕМЫЕ ЗНАЧЕНИЯ (в приоритете):**\n- " + "\n- ".join(sorted(list(message_types))) + "\nЕсли ни одно из этих значений не подходит, определи тип самостоятельно."

        event_types_block = ""
        if event_types:
            event_types_block = "**РЕКОМЕНДУЕМЫЕ ЗНАЧЕНИЯ (в приоритете):**\n- " + "\n- ".join(sorted(list(event_types))) + "\nЕсли ни одно из этих значений не подходит, определи тип самостоятельно."

        self.current_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            message_types_block=message_types_block,
            event_types_block=event_types_block
        )
        self.logger.info("Промпт для LLM сформирован с учетом %d типов сообщений и %d типов событий", 
                         len(message_types), len(event_types))

        processed_keys = self.repository.get_processed_events_keys()
        
        stats = {
            "total_found": 0,
            "processed": 0,
            "skipped": 0,
            "errors": 0
        }

        if not EMITENT_EVENTS_JSON_DIR.exists():
            self.logger.warning("Директория с событиями не найдена: %s", EMITENT_EVENTS_JSON_DIR)
            return stats

        url = f"{settings.LOCAL_LLM_BASE_URL.rstrip('/')}{settings.LOCAL_LLM_GENERATE_PATH}"

        with httpx.Client(timeout=300.0) as client:
            for root, _, files in os.walk(EMITENT_EVENTS_JSON_DIR):
                for file in files:
                    if not file.endswith(".json"):
                        continue
                    
                    current_inn = file.replace(".json", "")
                    if target_inn and current_inn != target_inn:
                        continue
                    
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception as e:
                        self.logger.error("Ошибка чтения JSON файла %s: %s", file_path, e)
                        continue

                    # Если JSON содержит список событий (по годам или плоский список)
                    # Структура: {"2024": [{"pseudoGUID": "...", "event_date": "...", "full_text": "..."}, ...]}
                    self.logger.info("Начата обработка событий для ИНН: %s", current_inn)
                    
                    if isinstance(data, dict):
                        for year, events_list in data.items():
                            if isinstance(events_list, list):
                                self.logger.info("Обработка событий за %s год (всего в списке: %d)", year, len(events_list))
                                self._process_event_list(events_list, processed_keys, client, url, stats, emitent_inn=current_inn)
                    elif isinstance(data, list):
                        self.logger.info("Обработка плоского списка событий (всего в списке: %d)", len(data))
                        self._process_event_list(data, processed_keys, client, url, stats, emitent_inn=current_inn)

        return stats

    def _process_event_list(
        self, 
        events: List[Dict[str, Any]], 
        processed_keys: set, 
        client: httpx.Client, 
        url: str, 
        stats: Dict[str, int],
        emitent_inn: str
    ) -> None:
        """Обрабатывает список событий, фильтрует и отправляет в LLM."""
        total_in_list = len(events)
        skipped_count = 0
        
        for i, event in enumerate(events, 1):
            pseudo_guid = event.get("pseudoGUID") or event.get("pseudo_guid")
            event_date_raw = event.get("eventDate") or event.get("event_date")
            full_text = event.get("full_text") or event.get("text") or event.get("MessageText")

            if not pseudo_guid or not event_date_raw or not full_text:
                continue

            # Очистка текста от мусорных символов
            full_text = self._clean_text(full_text)

            stats["total_found"] += 1

            # Попытка нормализовать дату
            try:
                if "T" in event_date_raw:
                    date_obj = datetime.strptime(event_date_raw[:10], "%Y-%m-%d").date()
                else:
                    date_obj = datetime.strptime(event_date_raw, "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning("Некорректный формат даты события %s для GUID %s", event_date_raw, pseudo_guid)
                stats["errors"] += 1
                continue

            date_str = str(date_obj)

            if (pseudo_guid, date_str) in processed_keys:
                stats["skipped"] += 1
                skipped_count += 1
                continue

            # Если были пропущенные события перед текущим новым - сообщим об этом
            if skipped_count > 0:
                self.logger.info("[%s] Пропущено уже обработанных событий: %d", emitent_inn, skipped_count)
                skipped_count = 0

            text_len = len(full_text)
            if text_len > 30000:
                self.logger.warning(
                    "[%s] Событие пропущено: текст слишком длинный (%d симв. > 30000)", 
                    emitent_inn, text_len
                )
                stats["skipped"] += 1
                continue

            self.logger.info("[%s] Обработка события %d/%d (GUID: %s). Размер текста: %d симв.", 
                             emitent_inn, i, total_in_list, pseudo_guid, text_len)

            # Отправляем в LLM
            prompt = f"{self.current_prompt}\n\nТекст события:\n{full_text}"
            payload = {
                "message": prompt,
                "max_new_tokens": settings.LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS,
                "temperature": settings.LOCAL_LLM_ANALYSIS_TEMPERATURE,
                "top_p": settings.LOCAL_LLM_ANALYSIS_TOP_P
            }

            try:
                self.logger.info("[%s] Отправка запроса в LLM (ожидание ответа может занять несколько минут)...", emitent_inn)
                response = client.post(url, json=payload, timeout=600.0)
                response.raise_for_status()
                self.logger.info("[%s] Ответ от LLM получен", emitent_inn)
                response_data = response.json()
                llm_text = response_data.get("response", "")
                
                # Очистка markdown блоков (если LLM их все-таки вернула)
                llm_text = llm_text.strip()
                if llm_text.startswith("```json"):
                    llm_text = llm_text[7:]
                if llm_text.startswith("```"):
                    llm_text = llm_text[3:]
                if llm_text.endswith("```"):
                    llm_text = llm_text[:-3]
                
                extracted_data = json.loads(llm_text.strip())

                new_event = EventDetail(
                    emitent_inn=emitent_inn,
                    pseudo_guid=pseudo_guid,
                    event_date=date_obj,
                    registration_number=extracted_data.get("registration_number"),
                    issue_registration_number=extracted_data.get("issue_registration_number"),
                    isin=extracted_data.get("isin"),
                    series=extracted_data.get("series"),
                    security_type=extracted_data.get("security_type"),
                    message_type=extracted_data.get("message_type"),
                    event_type=extracted_data.get("event_type"),
                    publication_date=extracted_data.get("publication_date")
                )

                self.repository.save(new_event)
                processed_keys.add((pseudo_guid, date_str))
                stats["processed"] += 1
                self.logger.info("[%s] Событие успешно сохранено: %s (ISIN: %s)", 
                                 emitent_inn, new_event.message_type, new_event.isin)

            except Exception as e:
                self.logger.error("Ошибка обработки события GUID %s: %s", pseudo_guid, e)
                stats["errors"] += 1
        
        if skipped_count > 0:
            self.logger.info("[%s] В конце списка пропущено уже обработанных событий: %d", emitent_inn, skipped_count)

    def _clean_text(self, text: str) -> str:
        """Очищает текст события от мусорных символов, лишних пробелов и нормализует форматирование."""
        if not text:
            return ""

        # 1. Нормализация переносов строк
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Удаление непечатаемых и странных пробельных символов (типа \xa0)
        # Оставляем только те символы, которые имеют смысл для LLM
        # Заменяем все странные пробельные символы на обычный пробел
        text = re.sub(r'[\u00A0\u1680\u180E\u2000-\u200B\u202F\u205F\u3000\uFEFF]', ' ', text)
        
        # Удаляем управляющие символы (кроме новой строки и табуляции)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # 3. Удаление длинных "украшательств" (линейки из точек, подчеркиваний и т.д.)
        text = re.sub(r'\.{5,}', '...', text)
        text = re.sub(r'_{5,}', '___', text)
        text = re.sub(r'-{5,}', '---', text)
        text = re.sub(r'={5,}', '===', text)
        text = re.sub(r'\*{5,}', '***', text)

        # 4. Схлопывание множественных пробелов (внутри строк)
        text = re.sub(r'[ \t]+', ' ', text)

        # 5. Очистка каждой строки и удаление лишних пустых строк
        lines = [line.strip() for line in text.split('\n')]
        
        # 6. Сборка обратно с ограничением пустых строк (максимум одна пустая строка подряд)
        result_lines = []
        for line in lines:
            if line:
                result_lines.append(line)
            elif result_lines and result_lines[-1] != "":
                result_lines.append("")
        
        return "\n".join(result_lines).strip()
