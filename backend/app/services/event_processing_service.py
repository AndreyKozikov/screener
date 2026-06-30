
from app.models.entities.event_detail import EventDetail
from app.repository.db.event_detail_repository import EventDetailRepository
from app.repository.db.bonds_repository import BondsRepository
from typing import Dict, Any, Optional
import httpx
import logging
import os
from pathlib import Path
from config.paths import EMITENT_EVENTS_JSON_DIR
import config.settings as settings
import json
import re
from datetime import datetime

SYSTEM_PROMPT_TEMPLATE = """Ты — система извлечения структурированных данных из текста. Твоя единственная задача — извлечь параметры ценных бумаг из предоставленного сообщения о существенном факте и вернуть результат в виде строго валидного JSON.

---

**ЖЁСТКИЕ ПРАВИЛА**

- Ответ содержит ТОЛЬКО один валидный JSON-объект — никакого текста до или после.
- Никаких пояснений, комментариев, markdown-блоков, префиксов вроде `json` или ` ``` `.
- Не додумывай и не интерполируй значения. Если данные явно не указаны в тексте — возвращай `null`.
- Если найдено несколько значений для одного поля — выбери наиболее релевантное.
- Каждый ключ содержит ровно одно значение (не массив, не объект).
- Очищай значения: убирай символы `«»""№`, слово `от`, лишние пробелы — оставляй только чистое значение.

**ДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ДЛЯ QWEN:**
- Пиши значения с большой буквы, как в списке ниже.
- Если видишь синоним (например, "Сбор акционеров"), ТРАНСФОРМИРУЙ его в "Собрание".
- Не используй кавычки ВНУТРИ значений JSON.

---

**КЛАССИФИКАТОР (СТРОГИЙ СПИСОК)**

Для полей message_type и event_type ЗАПРЕЩЕНО использовать любые слова, кроме указанных ниже. Если текст подходит под описание, сопоставь его с ЕДИНСТВЕННЫМ разрешенным термином из списка.

**Разрешенные значения (в порядке приоритета):**
1. "Утверждение отчета" — если: утвердить годовой отчет, отчетность, баланс.
2. "Сделка" — если: одобрить договор, кредит, залог, поручительство, заинтересованность.
3. "Погашение" — если: погашение номинала, амортизация.
4. "Выкуп" — если: приобретение эмитентом, отчет о выкупе.
5. "Оферта" — если: предложение о приобретении, приглашение делать оферты.
6. "Фиксация реестра" — если: дата определения лиц, закрытие реестра.
7. "Выплата купона" — если: выплата дохода, купонный период.
8. "Выплата дивидендов" — если: дивиденды, распределение прибыли.
9. "Собрание" — если: ОСА, ВОСА, созыв, решение акционера/участника.
10. "Размещение" — если: начало размещения, итоги выпуска, цена размещения.
11. "Ставка купона" — если: размер процента, величина купона.
12. "Регистрация" — если: присвоение номера, регистрация программы/выпуска.
13. "Допуск к торгам" — если: листинг, биржа, котировальный список.
14. "Рейтинг" — если: присвоение, изменение или подтверждение кредитного рейтинга.
15. "Раскрытие информации" — техническая категория для всего остального.

**ПРАВИЛА КЛАССИФИКАЦИИ (ПРИОРИТЕТ):**
1. Тебе ЗАПРЕЩЕНО создавать новые типы событий. 
2. Выбирай наиболее подходящее из списка: [Собрание, Выкуп, Выплата дивидендов, Допуск к торгам, Оферта, Регистрация, Ставка купона, Утверждение отчета, Фиксация реестра, Выплата купона, Размещение, Сделка, Погашение, Рейтинг].
3. Если событие не подходит ни под одно — пиши "Раскрытие информации", но не выдумывай своё.
4. Очищай текст: никаких "событие с акциями", только "Собрание" или "Выплата дивидендов".

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

`security_type`:
Смотри на организационно-правовую форму в пункте 1.1 и контекст:
- Если Эмитент — ООО: НИКОГДА не ставь «Акция». Если текст об утверждении отчетов или сделках без упоминания конкретных облигаций — ставь null. Если указан ISIN или номер выпуска облигаций — ставь Облигация.
- Если Эмитент — ПАО/АО/ОАО/ЗАО: Если речь о дивидендах или собрании акционеров — Акция. Если речь о купонах, сериях БО или 001Р — Облигация.

`message_type`
Категория сообщения из строгого списка выше.

`event_type`
Тип события из строгого списка выше.

`publication_date`
Приоритет источника:
1. Дата публикации
2. Дата сообщения
3. Дата подписи

Формат вывода: `YYYY-MM-DD`. Если ни одна из дат не найдена — `null`.

---

**СТРУКТУРА ОТВЕТА**

{
  "registration_number": null,
  "issue_registration_number": null,
  "isin": null,
  "series": null,
  "security_type": null,
  "message_type": null,
  "event_type": null,
  "publication_date": null
}


---

**ПРИМЕР**

Входной текст:
```
«Идентификационные признаки ценных бумаг: биржевые облигации процентные неконвертируемые бездокументарные серии 001Р-01, размещаемые в рамках программы биржевых облигаций, имеющей регистрационный номер 4-00206-L-001P-02E от 10.12.2024 г., регистрационный номер выпуска 4B02-01-00206-L-001P от 27.12.2024, международный код (номер) идентификации ценных бумаг (ISIN): RU000A10D665»
```

Ожидаемый ответ:

{
  "registration_number": "4B02-01-00206-L-001P",
  "issue_registration_number": "4-00206-L-001P-02E",
  "isin": "RU000A10D665",
  "series": "001Р-01",
  "security_type": "Облигация",
  "message_type": "Выплата купона",
  "event_type": "Выплата купона",
  "publication_date": null
}

"""
logger = logging.getLogger(__name__)

class EventProcessingService:
    """Сервис интеллектуальной обработки событий раскрытия информации.

    Класс обеспечивает конвейерную обработку сырых текстовых данных событий,
    используя локальные или облачные языковые модели для извлечения структурированных
    параметров облигаций.
    """

    def __init__(self, repository: EventDetailRepository):
        self.repository = repository
        self.bonds_repository = BondsRepository()
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
        
        self.current_prompt = SYSTEM_PROMPT_TEMPLATE
        self.logger.info("Промпт для LLM сформирован со строгим списком типов событий")

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

        # 1. Предварительный подсчет общего количества событий для прогресс-бара
        total_events_count = 0
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
                except Exception:
                    continue

                if isinstance(data, dict):
                    for year, events_list in data.items():
                        if isinstance(events_list, list):
                            total_events_count += len(events_list)
                elif isinstance(data, list):
                    total_events_count += len(data)

        self.logger.info("Всего найдено событий для обработки: %d", total_events_count)

        url = f"{settings.LOCAL_LLM_BASE_URL.rstrip('/')}{settings.LOCAL_LLM_GENERATE_PATH}"

        from tqdm import tqdm
        import sys
        from tqdm.contrib.logging import logging_redirect_tqdm

        with logging_redirect_tqdm(), tqdm(
            total=total_events_count,
            desc="Обработка событий",
            file=sys.stdout,
            dynamic_ncols=True,
            leave=True
        ) as pbar:
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
                                    self._process_event_list(events_list, processed_keys, client, url, stats, emitent_inn=current_inn, pbar=pbar)
                        elif isinstance(data, list):
                            self.logger.info("Обработка плоского списка событий (всего в списке: %d)", len(data))
                            self._process_event_list(data, processed_keys, client, url, stats, emitent_inn=current_inn, pbar=pbar)

        return stats

    def _process_event_list(
        self,
        events: list[Dict[str, Any]],
        processed_keys: set,
        client: httpx.Client,
        url: str,
        stats: Dict[str, int],
        emitent_inn: str,
        pbar: Optional[Any] = None
    ) -> None:
        """Обрабатывает список событий, фильтрует и отправляет в LLM."""
        total_in_list = len(events)
        skipped_count = 0
        
        if pbar is not None:
            pbar.set_description(f"ИНН {emitent_inn}")

        for i, event in enumerate(events, 1):
            pseudo_guid = event.get("pseudoGUID") or event.get("pseudo_guid")
            event_date_raw = event.get("eventDate") or event.get("event_date")
            full_text = event.get("full_text") or event.get("text") or event.get("MessageText")

            if not pseudo_guid or not event_date_raw or not full_text:
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(processed=stats["processed"], skipped=stats["skipped"], errors=stats["errors"])
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
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(processed=stats["processed"], skipped=stats["skipped"], errors=stats["errors"])
                continue

            date_str = str(date_obj)

            if (pseudo_guid, date_str) in processed_keys:
                stats["skipped"] += 1
                skipped_count += 1
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(processed=stats["processed"], skipped=stats["skipped"], errors=stats["errors"])
                continue

            # Если были пропущенные события перед текущим новым - сообщим об этом
            if skipped_count > 0:
                self.logger.info("[%s] Пропущено уже обработанных событий: %d", emitent_inn, skipped_count)
                skipped_count = 0

            text_len = len(full_text)
            if text_len > 30000:
                # self.logger.warning(
                #     "[%s] Событие пропущено: текст слишком длинный (%d симв. > 30000)",
                #     emitent_inn, text_len
                # )
                stats["skipped"] += 1
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(processed=stats["processed"], skipped=stats["skipped"], errors=stats["errors"])
                continue

            # self.logger.info("[%s] Обработка события %d/%d (GUID: %s). Размер текста: %d симв.",
            #                  emitent_inn, i, total_in_list, pseudo_guid, text_len)

            # Отправляем в LLM
            prompt = f"{self.current_prompt}\n\nТекст события:\n{full_text}"
            payload = {
                "message": prompt,
                "max_new_tokens": settings.LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS,
                "temperature": settings.LOCAL_LLM_ANALYSIS_TEMPERATURE,
                "top_p": settings.LOCAL_LLM_ANALYSIS_TOP_P
            }

            try:
                #self.logger.info("[%s] Отправка запроса в LLM (ожидание ответа может занять несколько минут)...", emitent_inn)
                response = client.post(url, json=payload, timeout=600.0)
                response.raise_for_status()
                #self.logger.info("[%s] Ответ от LLM получен", emitent_inn)
                response_data = response.json()
                llm_text = response_data.get("response", "")
                
                # Надежное извлечение JSON (находим первый { и последний })
                llm_text = llm_text.strip()
                start_idx = llm_text.find('{')
                end_idx = llm_text.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    json_candidate = llm_text[start_idx:end_idx+1]
                    # Если LLM все-таки вернула {{ ... }}
                    if json_candidate.startswith("{{") and json_candidate.endswith("}}"):
                        json_candidate = json_candidate[1:-1]
                    try:
                        extracted_data = json.loads(json_candidate)
                    except json.JSONDecodeError:
                        # Попробуем починить одинарные кавычки (бывает у Qwen)
                        try:
                            fixed_json = json_candidate.replace("'", '"')
                            extracted_data = json.loads(fixed_json)
                        except:
                            self.logger.error("[%s] Не удалось распарсить JSON. Сырой текст: %s", emitent_inn, llm_text)
                            raise
                else:
                    self.logger.error("[%s] JSON не найден в ответе LLM. Сырой текст: %s", emitent_inn, llm_text)
                    raise ValueError("JSON not found in LLM response")

                # Логика доопределения isin по registration_number
                security_type = extracted_data.get("security_type")
                isin = extracted_data.get("isin")
                reg_number = extracted_data.get("registration_number")

                if security_type == "Облигация" and not isin and reg_number:
                    secids = self.bonds_repository.get_secids_by_regnumber(reg_number)
                    if secids:
                        extracted_data["isin"] = secids[0]
                        self.logger.info("[%s] ISIN доопределен по registration_number (%s): %s", emitent_inn, reg_number, secids[0])

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
                # self.logger.info("[%s] Событие успешно сохранено: %s (ISIN: %s)",
                #                  emitent_inn, new_event.message_type, new_event.isin)

            except Exception as e:
                self.logger.error("Ошибка обработки события GUID %s: %s", pseudo_guid, e)
                stats["errors"] += 1
            finally:
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(processed=stats["processed"], skipped=stats["skipped"], errors=stats["errors"])
        
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
