import uvicorn, json
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
import sys

# Добавляем корень backend в sys.path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from app.utils.events_loader import (
    get_event_by_id, get_event_text, save_event_changes, 
    get_navigation_ids, get_first_unedited_id, get_existing_types, get_stats, delete_event
)

app = FastAPI(title="BondsScreener Event Editor")

def _count_events_in_files(events_dir: Path) -> int:
    """Подсчитывает количество событий во всех JSON-файлах директории."""
    if not events_dir.is_dir():
        return 0

    total_events = 0
    for json_path in events_dir.glob("*.json"):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(payload, dict):
            for events in payload.values():
                if isinstance(events, list):
                    total_events += len(events)
        elif isinstance(payload, list):
            total_events += len(payload)

    return total_events

# Считаем единожды при старте процесса редактора.
TOTAL_EVENTS_IN_FILES = _count_events_in_files(backend_dir / "app" / "data" / "events")

def get_html_template(event, event_text, nav):
    template_path = current_dir / "event_edit.html"
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Ручная замена переменных (замена Jinja2)
    status_class = "status-edited" if event.is_edit else "status-new"
    status_text = "Изменено" if event.is_edit else "Новое"
    stats = get_stats()
    progress_text = f"{stats['edited']} / {stats['total']}"
    
    replacements = {
        "{{ event.id }}": str(event.id),
        "{{ progress_text }}": progress_text,
        "{{ total_events_in_files }}": str(TOTAL_EVENTS_IN_FILES),
        "{{ 'status-edited' if event.is_edit else 'status-new' }}": status_class,
        "{{ 'Изменено' if event.is_edit else 'Новое' }}": status_text,
        "{{ event.pseudo_guid }}": str(event.pseudo_guid),
        "{{ event.event_date }}": str(event.event_date),
        "{{ event.registration_number or '' }}": str(event.registration_number or ""),
        "{{ event.issue_registration_number or '' }}": str(event.issue_registration_number or ""),
        "{{ event.series or '' }}": str(event.series or ""),
        "{{ event.isin or '' }}": str(event.isin or ""),
        "{{ event.event_type or '' }}": str(event.event_type or ""),
        "{{ event.message_type or '' }}": str(event.message_type or ""),
        "{{ event.security_type or '' }}": str(event.security_type or ""),
        "{{ event_text or 'Текст не найден' }}": event_text or "Текст не найден",
        "{{ nav.prev }}": str(nav["prev"] or ""),
        "{{ nav.next }}": str(nav["next"] or ""),
        "{{ 'disabled' if not nav.prev }}": "disabled" if not nav["prev"] else "",
        "{{ 'disabled' if not nav.next }}": "disabled" if not nav["next"] else "",
        '{{ \'style="pointer-events:none"\' if not nav.prev }}': 'style="pointer-events:none"' if not nav["prev"] else "",
        '{{ \'style="pointer-events:none"\' if not nav.next }}': 'style="pointer-events:none"' if not nav["next"] else "",
        "// JSON_DATA_PLACEHOLDER": f"const existingTypes = {json.dumps(get_existing_types())};"
    }
    
    for key, value in replacements.items():
        html = html.replace(key, value)
    
    return html

@app.get("/check/{id}")
async def check_event(id: int):
    event = get_event_by_id(id)
    return {"exists": event is not None}

@app.get("/", response_class=HTMLResponse)
async def read_event(request: Request, id: int = None):
    # Если ID не передан, берем первый доступный неотредактированный
    if id is None:
        id = get_first_unedited_id()
        if id is None:
            return HTMLResponse("<h1>Все события обработаны!</h1>", status_code=200)
        
    event = get_event_by_id(id)
    if not event:
        return RedirectResponse(url="/?not_found=1", status_code=303)
    
    event_text = get_event_text(event.emitent_inn, event.pseudo_guid, event.event_date)
    nav = get_navigation_ids(id)
    
    content = get_html_template(event, event_text, nav)
    return HTMLResponse(content=content)

@app.post("/save")
async def save_event(
    id: int = Form(...),
    pseudo_guid: str = Form(...),
    event_date: str = Form(...),
    event_type: str = Form(...),
    message_type: str = Form(...),
    security_type: str = Form(...)
):
    success = save_event_changes(pseudo_guid, event_date, event_type, message_type, security_type)
    
    if success:
        return RedirectResponse(url=f"/?id={id}&saved=1", status_code=303)
    else:
        return HTMLResponse("Ошибка при сохранении", status_code=500)

@app.post("/delete")
async def remove_event(id: int = Form(...)):
    # Находим следующее событие ДО удаления, чтобы знать куда перейти
    nav = get_navigation_ids(id)
    next_id = nav["next"] or nav["prev"]
    
    success = delete_event(id)
    
    if success:
        if next_id:
            return RedirectResponse(url=f"/?id={next_id}&deleted=1", status_code=303)
        else:
            return RedirectResponse(url="/?deleted=1", status_code=303)
    else:
        return HTMLResponse("Ошибка при удалении", status_code=500)

if __name__ == "__main__":
    print(f"Запуск редактора событий на http://127.0.0.1:8010")
    uvicorn.run(app, host="127.0.0.1", port=8010)
