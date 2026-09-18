import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests


DEALOS_BASE_URL = os.environ.get(
    "DEALOS_BASE_URL", "https://kush-sba-deal-os.kgali01.chatgpt.site"
).rstrip("/")
EASTERN = ZoneInfo("America/New_York")


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment value {name} is missing.")
    return value


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-github-repository": os.environ.get(
            "GITHUB_REPOSITORY", "darkmobster/deal-screener"
        ),
    }


def format_due(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(EASTERN).strftime("%A, %B %-d at %-I:%M %p ET")


def build_message(sender, recipient, tasks):
    message = EmailMessage()
    message["Subject"] = (
        f"DealOS: {len(tasks)} task{'s' if len(tasks) != 1 else ''} due within 24 hours"
    )
    message["From"] = sender
    message["To"] = recipient
    lines = ["DealOS task reminder", "", "These tasks are due within the next 24 hours:", ""]
    for task in tasks:
        deal = task.get("dealTitle") or "Workspace"
        lines.append(
            f"- {task['title']} — {deal} — {format_due(task['dueDate'])} "
            f"— {task['priority']} priority — Owner: {task['owner']}"
        )
    lines.extend(["", f"Open DealOS: {DEALOS_BASE_URL}"])
    message.set_content("\n".join(lines))
    return message


def run():
    token = required_env("GITHUB_TOKEN")
    gmail_user = required_env("GMAIL_USER")
    gmail_password = required_env("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("TASK_REMINDER_TO", gmail_user).strip()
    headers = github_headers(token)
    response = requests.get(
        f"{DEALOS_BASE_URL}/api/task-reminders", headers=headers, timeout=60
    )
    response.raise_for_status()
    tasks = response.json().get("tasks", [])
    if not tasks:
        print("No task reminders are due within the next 24 hours.")
        return

    message = build_message(gmail_user, recipient, tasks)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(message)

    acknowledgement = requests.post(
        f"{DEALOS_BASE_URL}/api/task-reminders",
        headers=headers,
        json={"taskIds": [task["id"] for task in tasks]},
        timeout=60,
    )
    acknowledgement.raise_for_status()
    print(f"Sent and recorded {len(tasks)} task reminder(s).")


if __name__ == "__main__":
    run()
