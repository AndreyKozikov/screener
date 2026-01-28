"""Роутеры для обработки обратной связи от пользователей.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов с предложениями
по улучшению приложения от пользователей. Сохраняет обратную связь в JSON файл
для последующего анализа.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
import json
import os
# Email sending is disabled
# from app.services.email_service import send_feedback_email

router = APIRouter(prefix="/api", tags=["feedback"])
"""Роутер FastAPI для обработки запросов обратной связи."""


class FeedbackRequest(BaseModel):
    """Модель запроса для отправки обратной связи.
    
    Attributes:
        text: Текст предложения по улучшению приложения (1-3000 символов).
        tab_name: Название вкладки, где было отправлено предложение.
    """
    text: str = Field(..., min_length=1, max_length=3000, description="Feedback text")
    tab_name: str = Field(..., description="Name of the tab where feedback was submitted")


class FeedbackResponse(BaseModel):
    """Модель ответа для отправки обратной связи.
    
    Attributes:
        success: Флаг успешной отправки обратной связи.
        feedback_id: Идентификатор сохраненного предложения.
        message: Сообщение о результате операции.
    """
    success: bool
    feedback_id: int
    message: str = "Feedback submitted successfully"


FEEDBACK_FILE: Path = Path(__file__).parent.parent / "data" / "feedback.json"
"""Путь к файлу для хранения обратной связи от пользователей."""




def ensure_feedback_file() -> None:
    """Обеспечивает существование файла feedback.json с правильной структурой.
    
    Создает файл feedback.json с начальной структурой, если он не существует.
    Создает директорию для файла при необходимости.
    """
    if not FEEDBACK_FILE.exists():
        # Create directory if it doesn't exist
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Initialize with empty structure
        initial_data = {
            "feedback_texts": {},
            "feedback_metadata": {}
        }
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)


def get_next_feedback_id() -> int:
    """Получает следующий ID для обратной связи.
    
    Читает существующий файл feedback.json и определяет максимальный ID из всех
    существующих записей. Возвращает следующий доступный ID.
    
    Returns:
        Следующий доступный ID для обратной связи. Если файл не существует или
        пуст, возвращает 1.
    """
    ensure_feedback_file()
    
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get all existing IDs from both sections
        text_ids = [int(k) for k in data.get("feedback_texts", {}).keys() if k.isdigit()]
        metadata_ids = [int(k) for k in data.get("feedback_metadata", {}).keys() if k.isdigit()]
        all_ids = set(text_ids + metadata_ids)
        
        if not all_ids:
            return 1
        
        return max(all_ids) + 1
    except (json.JSONDecodeError, FileNotFoundError, ValueError):
        return 1


def save_feedback(feedback_id: int, text: str, tab_name: str) -> None:
    """Сохраняет обратную связь в JSON файл.
    
    Сохраняет текст обратной связи и метаданные (название вкладки, временная метка)
    отдельно в файл feedback.json. Текст сохраняется в секции feedback_texts,
    метаданные - в секции feedback_metadata.
    
    Args:
        feedback_id: Идентификатор обратной связи для сохранения.
        text: Текст предложения по улучшению приложения.
        tab_name: Название вкладки, где было отправлено предложение.
    """
    ensure_feedback_file()
    
    # Read existing data
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data = {
            "feedback_texts": {},
            "feedback_metadata": {}
        }
    
    # Ensure structure exists
    if "feedback_texts" not in data:
        data["feedback_texts"] = {}
    if "feedback_metadata" not in data:
        data["feedback_metadata"] = {}
    
    # Add feedback
    feedback_id_str = str(feedback_id)
    timestamp = datetime.now().isoformat()
    
    # Store text and metadata separately
    data["feedback_texts"][feedback_id_str] = text
    data["feedback_metadata"][feedback_id_str] = {
        "tab_name": tab_name,
        "timestamp": timestamp
    }
    
    # Write back to file
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """Отправляет предложение по улучшению приложения.
    
    Сохраняет текст предложения и метаданные (название вкладки, временная метка)
    отдельно в JSON файл. Присваивает уникальный ID предложению и возвращает его
    в ответе. Уведомления по email отключены.
    
    Args:
        feedback: Объект FeedbackRequest с текстом предложения и названием вкладки.
    
    Returns:
        Объект FeedbackResponse с результатом отправки, содержащий:
        - success: Флаг успешной отправки (True)
        - feedback_id: Идентификатор сохраненного предложения
        - message: Сообщение об успешной отправке
    
    Raises:
        HTTPException: Если произошла ошибка при сохранении обратной связи
            (статус 500).
    """
    try:
        # Get next feedback ID
        feedback_id = get_next_feedback_id()
        
        # Get timestamp for email
        timestamp = datetime.now().isoformat()
        
        # Save feedback to file
        save_feedback(feedback_id, feedback.text, feedback.tab_name)
        
        # Email sending is disabled
        # Send email immediately after saving (non-blocking, errors are logged but don't fail the request)
        # try:
        #     send_feedback_email(feedback_id, feedback.text, feedback.tab_name, timestamp)
        # except Exception as email_error:
        #     # Log email error but don't fail the request
        #     print(f"Warning: Failed to send email for feedback #{feedback_id}: {str(email_error)}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message="Feedback submitted successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save feedback: {str(e)}"
        )
