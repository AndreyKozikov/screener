"""Сервис отправки электронных уведомлений.

Обеспечивает доставку обратной связи от пользователей через API SendGrid.
Реализует безопасную отправку сообщений на предустановленный адрес администратора.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:
    SendGridAPIClient = None
    Mail = None

# Load .env file if dotenv is available
if load_dotenv:
    from config.paths import ENV_FILE
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    else:
        load_dotenv(override=True)

SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
"""API ключ SendGrid для отправки email (из переменной окружения SENDGRID_API_KEY)."""

EMAIL_TO: str = "nwisdom@mail.ru"
"""Адрес получателя email (жестко задан, не раскрывается через API)."""

EMAIL_FROM: str = os.getenv("SENDGRID_FROM_EMAIL", "")
"""Адрес отправителя email (из переменной окружения SENDGRID_FROM_EMAIL).

Важно: EMAIL_FROM должен быть верифицированным email адресом в SendGrid.
Для использования API требуется Domain Authentication (не Single Sender Verification).
Установите SENDGRID_FROM_EMAIL на ваш верифицированный email адрес.
"""


def send_feedback_email(feedback_id: int, text: str, tab_name: str, timestamp: str) -> bool:
    """Отправляет уведомление о новом отзыве пользователя.

    Формирует HTML-письмо с деталями предложения и отправляет его через SendGrid.

    Args:
        feedback_id (int): Уникальный ID записи обратной связи.
        text (str): Содержание предложения.
        tab_name (str): Контекст (вкладка), в котором был оставлен отзыв.
        timestamp (str): Время совершения действия.

    Returns:
        bool: True, если письмо принято сервером SendGrid к отправке.
    """
    if SendGridAPIClient is None or Mail is None:
        print("ERROR: sendgrid package is not installed. Install it with: pip install sendgrid")
        return False
    
    if not SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY environment variable must be set")
        print("Get your API key from: https://app.sendgrid.com/settings/api_keys")
        return False
    
    if not EMAIL_FROM:
        print("ERROR: SENDGRID_FROM_EMAIL environment variable must be set")
        print("This must be a verified email address in SendGrid")
        print("See instructions in backend/scripts/README.md for setting up Domain Authentication")
        return False
    
    try:
        # Create email body
        plain_text_content = f"""Получено новое предложение по улучшению приложения

Предложение #{feedback_id}
Вкладка: {tab_name}
Время: {timestamp}
Текст:
{text}
"""
        
        # Create HTML version for better readability
        html_content = f"""
<h2>Получено новое предложение по улучшению приложения</h2>
<hr>
<h3>Предложение #{feedback_id}</h3>
<p><strong>Вкладка:</strong> {tab_name}<br>
<strong>Время:</strong> {timestamp}</p>
<p><strong>Текст:</strong></p>
<pre style='background-color: #f5f5f5; padding: 10px; border-radius: 5px; white-space: pre-wrap;'>{text}</pre>
<hr>
"""
        
        # Create Mail object
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=EMAIL_TO,
            subject=f"Предложение по улучшению приложения #{feedback_id}",
            plain_text_content=plain_text_content,
            html_content=html_content
        )
        
        # Send email via SendGrid API
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print(f"Successfully sent feedback #{feedback_id} to {EMAIL_TO}")
            print(f"SendGrid response status: {response.status_code}")
            return True
        else:
            print(f"ERROR: SendGrid returned status code {response.status_code}")
            print(f"Response body: {response.body}")
            return False
        
    except Exception as e:
        print(f"ERROR: Failed to send email for feedback #{feedback_id}: {str(e)}")
        if hasattr(e, 'body'):
            print(f"Error details: {e.body}")
        return False


def send_multiple_feedback_emails(feedback_items: List[Dict[str, Any]]) -> bool:
    """Выполняет пакетную отправку уведомлений.

    Args:
        feedback_items (List[Dict[str, Any]]): Список словарей с данными отзывов.

    Returns:
        bool: Статус успешности массовой рассылки.
    """
    if SendGridAPIClient is None or Mail is None:
        print("ERROR: sendgrid package is not installed. Install it with: pip install sendgrid")
        return False
    
    if not SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY environment variable must be set")
        print("Get your API key from: https://app.sendgrid.com/settings/api_keys")
        return False
    
    if not EMAIL_FROM:
        print("ERROR: SENDGRID_FROM_EMAIL environment variable must be set")
        print("This must be a verified email address in SendGrid")
        print("See instructions in backend/scripts/README.md for setting up Domain Authentication")
        return False
    
    if not feedback_items:
        print("No feedback items to send")
        return True
    
    try:
        # Create email body
        body_parts = [
            f"Получено новых предложений: {len(feedback_items)}\n",
            "=" * 50,
            ""
        ]
        
        for item in feedback_items:
            body_parts.extend([
                f"Предложение #{item['id']}",
                f"Вкладка: {item['tab_name']}",
                f"Время: {item['timestamp']}",
                f"Текст:",
                item['text'],
                "",
                "-" * 50,
                ""
            ])
        
        plain_text_content = "\n".join(body_parts)
        
        # Create HTML version for better readability
        html_parts = [
            f"<h2>Получено новых предложений: {len(feedback_items)}</h2>",
            "<hr>"
        ]
        
        for item in feedback_items:
            html_parts.extend([
                f"<h3>Предложение #{item['id']}</h3>",
                f"<p><strong>Вкладка:</strong> {item['tab_name']}<br>",
                f"<strong>Время:</strong> {item['timestamp']}</p>",
                f"<p><strong>Текст:</strong></p>",
                f"<pre style='background-color: #f5f5f5; padding: 10px; border-radius: 5px; white-space: pre-wrap;'>{item['text']}</pre>",
                "<hr>"
            ])
        
        html_content = "\n".join(html_parts)
        
        # Create Mail object
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=EMAIL_TO,
            subject=f"Предложения по улучшению приложения ({len(feedback_items)} шт.)",
            plain_text_content=plain_text_content,
            html_content=html_content
        )
        
        # Send email via SendGrid API
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print(f"Successfully sent {len(feedback_items)} feedback items to {EMAIL_TO}")
            print(f"SendGrid response status: {response.status_code}")
            return True
        else:
            print(f"ERROR: SendGrid returned status code {response.status_code}")
            print(f"Response body: {response.body}")
            return False
        
    except Exception as e:
        print(f"ERROR: Failed to send email: {str(e)}")
        if hasattr(e, 'body'):
            print(f"Error details: {e.body}")
        return False
