# План перевода загрузки купонов на новый алгоритм (MOEX ISS bondization)

Статус: план согласовывается, изменения в код НЕ внесены.

## 1. Как работает загрузка купонов сейчас

| Слой | Файл | Что делает |
|---|---|---|
| Конфиг | `conversion_service/config/paths.py:27` | `MOEX_COUPONS_QUERY = "?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"` |
| Клиент | `conversion_service/app/utils/moex_client.py:41` `MoexClient.fetch_coupons` | Один GET на `bondization.json`, берёт `payload[1]["coupons"]`, чистит UTF-8, извлекает 9 полей, из первого купона строит `amortizations` |
| Подготовка | `conversion_service/app/utils/coupon_utils.py:52` `extract_coupon_for_storage` | Поля `coupondate, recorddate, startdate, initialfacevalue, facevalue, faceunit, value, valueprc, value_rub` |
| Сервис | `conversion_service/app/services/coupon_service.py:48` `refresh_all` | **Последовательно** обходит все облигации (`for` + `asyncio.to_thread`), копит записи, один раз вызывает `save_moex_coupons` |
| БД | `db_repository/.../db_coupon.py` | Принимает список записей, INSERT OR REPLACE |

## 2. Результаты реальных запросов (проверено ~500 ответами, 400+ облигаций)

- Формат `iss.json=extended&iss.meta=off` подтверждён: ответ — массив `[{charsetinfo...}, {coupons:[...], amortizations:[...], offers:[...]}]`, где `coupons` — массив объектов. Структура элементов купона: `isin, name, issuevalue, coupondate, recorddate, startdate, initialfacevalue, facevalue, faceunit, value, valueprc, value_rub, secid, primary_boardid`.
- **Поля совпадают с `COUPON_STORAGE_FIELDS` один в один → алгоритм подготовки данных для БД менять не нужно**, структура БД не затрагивается.
- Параметры `start` и `limit` API честно поддерживает (проверено: `start=0/20/40` на 40 купонах SU26238RMFS4; `limit=100` на 364 купонах RU000A1018T2).
- **Критичное расхождение с ТЗ:** блока `coupons.cursor` (INDEX/TOTAL/PAGESIZE) в ответах `bondization.json` **не существует**. Проверено: режимы atomic/compact/extended, `iss.meta` вкл/выкл, `iss.only=coupons`, комбинации `start`/`limit`, облигации с 40/60/140/364 купонами, заголовки ответа — курсор не появляется ни разу. Данные обрезаются сервером молча (по умолчанию ~20 строк).

**Вывод:** буквальная автопагинация «через coupons.cursor» нереализуема — API не отдаёт этот блок. Эквивалент формулы `start = INDEX + PAGESIZE` → страничный цикл с фиксированным `PAGESIZE` и остановкой, когда страница вернула меньше `PAGESIZE` строк (это и есть `nextStart >= TOTAL`).

## 3. План изменений (по файлам)

### 3.1. `conversion_service/config/paths.py`
- `MOEX_COUPONS_QUERY` заменить на шаблон с пагинацией: `?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&start={start}&limit={pagesize}`.
- Добавить `MOEX_COUPONS_PAGESIZE = 100` (стандартный PAGESIZE ISS).

### 3.2. `conversion_service/app/utils/moex_client.py` — `fetch_coupons`
- Внутри метода — цикл пагинации: `start = 0`; GET очередной страницы; при ошибке сети/JSON — `RuntimeError` как сейчас; страница пустая → выход; строки добавляются в общий список; `len(page) < PAGESIZE` → выход; иначе `start += PAGESIZE`. Лимит безопасности на число страниц (например, 1000).
- Парсинг `payload[1]`, очистка `clean_string_value`, `extract_coupon_for_storage`, построение `amortizations` из **первого купона первой страницы** — без изменений (первый купон первой страницы = первый купон всего выпуска).
- Сигнатура и возвращаемая структура `{amortizations, coupons, offers}` не меняются.

### 3.3. `conversion_service/app/services/coupon_service.py` — `refresh_all`
- Заменить последовательный цикл на `ThreadPoolExecutor(max_workers=10)` (константа `MAX_COUPON_WORKERS = 10`, жёсткий потолок по ТЗ).
- В каждом потоке: `fetch_coupons(secid)` + сборка записей `{"bond_id": ..., **coupon}`.
- Результаты собираются из `as_completed`; счётчики `updated/errors/skipped` и логирование прогресса сохраняются.
- Финальный единый вызов `self._db_coupon.save_moex_coupons(records)` — **не меняется** (алгоритм записи в БД и схема БД прежние).

### 3.4. `get_coupons` (одиночная облигация)
- Изменений не требует: пагинация спрятана внутри `fetch_coupons`.

### 3.5. Тесты (`conversion_service/tests/`)
- Юнит `MoexClient.fetch_coupons`: мок двух страниц (полная + короткая) → проверка склеивания и остановки; пустая первая страница; ошибка сети на второй странице.
- Юнит `refresh_all`: мок `MoexClient`, проверка что `ThreadPoolExecutor` создаётся с `max_workers=10` и `save_moex_coupons` вызывается один раз.

## 4. Риски и решения
- «Слепая» остановка по короткой странице: если `TOTAL` кратен `PAGESIZE`, будет один лишний пустой запрос — обрабатывается выходом по пустой странице.
- Порядок записей при многопотоке не гарантирован — для `INSERT OR REPLACE` и PK `(bond_id, coupondate)` некритично (БД не меняется).
- Нагрузка на ISS: 10 потоков — в рамках требований; при необходимости легко снизить константой.

## 5. Проверенные эмпирические факты (для сверки при реализации)
- SU26238RMFS4: 40 купонов; страница по умолчанию 20 строк; `start` сдвигает окно; `limit=unlimited` отдаёт все.
- RU000A1018T2: 364 купона; `limit=100` отдаёт ровно 100 строк; cursor отсутствует.
- `coupons.cursor`, `INDEX`, `TOTAL`, `PAGESIZE` не встречаются в сырых ответах `bondization.json` ни в одном сочетании параметров.
