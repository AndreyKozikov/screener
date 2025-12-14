#!/usr/bin/env python3
"""
Script to send feedback suggestions to email.

This script reads feedback from feedback.json file and sends new feedback items
to the configured email address using SendGrid API. The email address is not exposed through the API.

Run this script periodically (e.g., via cron) to send feedback emails.

Requirements:
- SendGrid API key (set SENDGRID_API_KEY environment variable)
- SendGrid account (free tier: 100 emails/day)
- sendgrid Python package installed
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set

# Add parent directory to path to import app modules
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Load .env file before importing email service
try:
    from dotenv import load_dotenv
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not installed. Install it with: pip install python-dotenv")
    print("Trying to use environment variables directly...")

from app.services.email_service import send_multiple_feedback_emails

# Path to feedback JSON file
FEEDBACK_FILE = SCRIPT_DIR / "app" / "data" / "feedback.json"
SENT_FEEDBACK_FILE = SCRIPT_DIR / "app" / "data" / "sent_feedback.json"


def load_sent_feedback_ids() -> Set[int]:
    """Load IDs of feedback that have already been sent"""
    if not SENT_FEEDBACK_FILE.exists():
        return set()
    
    try:
        with open(SENT_FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get("sent_ids", []))
    except (json.JSONDecodeError, FileNotFoundError):
        return set()


def save_sent_feedback_id(feedback_id: int) -> None:
    """Mark feedback ID as sent"""
    sent_ids = load_sent_feedback_ids()
    sent_ids.add(feedback_id)
    
    data = {"sent_ids": sorted(list(sent_ids))}
    SENT_FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(SENT_FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_feedback() -> Dict[str, Any]:
    """Load feedback from JSON file"""
    if not FEEDBACK_FILE.exists():
        return {"feedback_texts": {}, "feedback_metadata": {}}
    
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"feedback_texts": {}, "feedback_metadata": {}}


def get_unsent_feedback() -> List[Dict[str, Any]]:
    """Get feedback items that haven't been sent yet"""
    feedback_data = load_feedback()
    sent_ids = load_sent_feedback_ids()
    
    feedback_texts = feedback_data.get("feedback_texts", {})
    feedback_metadata = feedback_data.get("feedback_metadata", {})
    
    unsent = []
    for feedback_id_str, text in feedback_texts.items():
        try:
            feedback_id = int(feedback_id_str)
            if feedback_id not in sent_ids:
                metadata = feedback_metadata.get(feedback_id_str, {})
                unsent.append({
                    "id": feedback_id,
                    "text": text,
                    "tab_name": metadata.get("tab_name", "Неизвестная вкладка"),
                    "timestamp": metadata.get("timestamp", "Неизвестно")
                })
        except ValueError:
            continue
    
    # Sort by ID to send in order
    unsent.sort(key=lambda x: x["id"])
    return unsent


def send_email(feedback_items: List[Dict[str, Any]]) -> bool:
    """Send feedback items via SendGrid API using email service"""
    return send_multiple_feedback_emails(feedback_items)


def main():
    """Main function"""
    print(f"Checking for new feedback at {datetime.now().isoformat()}")
    
    # Get unsent feedback
    unsent = get_unsent_feedback()
    
    if not unsent:
        print("No new feedback to send")
        return
    
    print(f"Found {len(unsent)} new feedback items")
    
    # Send email
    if send_email(unsent):
        # Mark as sent
        for item in unsent:
            save_sent_feedback_id(item["id"])
        print("All feedback items marked as sent")
    else:
        print("Failed to send email, feedback items not marked as sent")


if __name__ == "__main__":
    main()
