from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

from db.mongodb import db


HEARING_REMINDER_DAYS = {
    7: ("hearing_7_days", "Hearing in 7 days"),
    1: ("hearing_1_day", "Hearing tomorrow"),
    0: ("hearing_morning", "Hearing today"),
}


def _date_only(value: datetime) -> datetime.date:
    return value.date()


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
    return doc


def user_can_access_case(case: Dict[str, Any], user_id: str, role: str) -> bool:
    normalized_role = (role or "").lower()
    if normalized_role == "admin":
        return True
    if normalized_role == "advocate":
        return case.get("advocateId") == user_id
    if normalized_role == "client":
        return case.get("clientId") == user_id
    return False


async def ensure_reminder_indexes() -> None:
    await db.notifications.create_index("dedupeKey", unique=True)
    await db.notifications.create_index([("recipientId", 1), ("createdAt", -1)])
    await db.tasks.create_index([("caseId", 1), ("dueDate", 1)])
    await db.tasks.create_index([("advocateId", 1), ("dueDate", 1)])
    await db.tasks.create_index([("clientId", 1), ("dueDate", 1)])


async def create_notification(
    *,
    recipient_id: str,
    recipient_role: str,
    title: str,
    message: str,
    notification_type: str,
    dedupe_key: str,
    related_case_id: Optional[str] = None,
    related_task_id: Optional[str] = None,
    hearing_date: Optional[datetime] = None,
    due_date: Optional[datetime] = None,
    created_by: Optional[str] = "system",
) -> Optional[str]:
    now = datetime.utcnow()
    notification = {
        "recipientId": recipient_id,
        "recipientRole": recipient_role,
        "title": title,
        "message": message,
        "type": notification_type,
        "relatedCaseId": related_case_id,
        "relatedTaskId": related_task_id,
        "hearingDate": hearing_date,
        "dueDate": due_date,
        "readAt": None,
        "dedupeKey": dedupe_key,
        "channels": {
            "inApp": "sent",
            "email": "pending",
            "sms": "pending",
            "whatsapp": "pending",
        },
        "createdBy": created_by,
        "modifiedBy": created_by,
        "createdAt": now,
        "modifiedAt": now,
    }

    try:
        result = await db.notifications.insert_one(notification)
        return str(result.inserted_id)
    except DuplicateKeyError:
        return None


async def notify_hearing_date_changed(
    case: Dict[str, Any],
    old_hearing_date: Optional[datetime],
    new_hearing_date: datetime,
    actor: Optional[str],
) -> None:
    client_id = case.get("clientId")
    if not client_id:
        return

    case_id = str(case.get("_id") or case.get("id"))
    old_label = old_hearing_date.strftime("%d %b %Y") if old_hearing_date else "the previous date"
    new_label = new_hearing_date.strftime("%d %b %Y")
    dedupe_key = f"hearing-change:{case_id}:{new_hearing_date.isoformat()}:{client_id}"

    await create_notification(
        recipient_id=client_id,
        recipient_role="Client",
        title="Hearing date changed",
        message=f"{case.get('caseTitle', 'Your case')} hearing changed from {old_label} to {new_label}.",
        notification_type="hearing_date_changed",
        related_case_id=case_id,
        hearing_date=new_hearing_date,
        dedupe_key=dedupe_key,
        created_by=actor or "system",
    )


async def run_reminder_scan() -> Dict[str, int]:
    await ensure_reminder_indexes()
    created = {"hearing": 0, "task": 0}
    today = datetime.utcnow().date()
    async for case in db.cases.find({"caseStatus": {"$nin": ["Closed", "closed"]}}):
        hearing_date = case.get("hearingDate")
        if not isinstance(hearing_date, datetime):
            continue

        days_until = (_date_only(hearing_date) - today).days
        reminder = HEARING_REMINDER_DAYS.get(days_until)
        if not reminder:
            continue

        if days_until == 0 and datetime.utcnow() < hearing_date:
            continue

        reminder_type, title = reminder
        case_id = str(case["_id"])
        recipients = [
            (case.get("advocateId"), "Advocate"),
            (case.get("clientId"), "Client"),
        ]

        for recipient_id, role in recipients:
            if not recipient_id:
                continue
            notification_id = await create_notification(
                recipient_id=recipient_id,
                recipient_role=role,
                title=title,
                message=f"{case.get('caseTitle', 'Case')} is listed at {case.get('courtLocation', 'court')}.",
                notification_type=reminder_type,
                related_case_id=case_id,
                hearing_date=hearing_date,
                dedupe_key=f"hearing:{case_id}:{hearing_date.isoformat()}:{reminder_type}:{recipient_id}",
            )
            if notification_id:
                created["hearing"] += 1

    async for task in db.tasks.find({"status": {"$nin": ["Closed", "closed", "Completed", "completed"]}}):
        due_date = task.get("dueDate")
        if not isinstance(due_date, datetime):
            continue

        days_until = (_date_only(due_date) - today).days
        if days_until == 1:
            reminder_type = "task_due_tomorrow"
            title = "Task due tomorrow"
            dedupe_suffix = "tomorrow"
        elif days_until == 0:
            reminder_type = "task_due_today"
            title = "Task due today"
            dedupe_suffix = "today"
        elif days_until < 0:
            reminder_type = "task_overdue"
            title = "Task overdue"
            dedupe_suffix = today.isoformat()
        else:
            continue

        task_id = str(task["_id"])
        recipients = [(task.get("advocateId"), "Advocate")]
        if task.get("notifyClient") and task.get("clientId"):
            recipients.append((task.get("clientId"), "Client"))

        for recipient_id, role in recipients:
            if not recipient_id:
                continue
            notification_id = await create_notification(
                recipient_id=recipient_id,
                recipient_role=role,
                title=title,
                message=f"{task.get('title', 'Task')} for this case is due {due_date.strftime('%d %b %Y')}.",
                notification_type=reminder_type,
                related_case_id=task.get("caseId"),
                related_task_id=task_id,
                due_date=due_date,
                dedupe_key=f"task:{task_id}:{dedupe_suffix}:{recipient_id}",
            )
            if notification_id:
                created["task"] += 1

    return created


async def get_upcoming_deadlines(user_id: str, role: str, days: int = 14) -> List[Dict[str, Any]]:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = today_start + timedelta(days=days)
    deadlines: List[Dict[str, Any]] = []

    async for case in db.cases.find({"hearingDate": {"$lte": end}, "caseStatus": {"$nin": ["Closed", "closed"]}}):
        if not user_can_access_case(case, user_id, role):
            continue
        hearing_date = case.get("hearingDate")
        if not isinstance(hearing_date, datetime):
            continue
        deadlines.append(
            {
                "id": str(case["_id"]),
                "type": "hearing",
                "title": case.get("caseTitle", "Case hearing"),
                "caseId": str(case["_id"]),
                "caseTitle": case.get("caseTitle", ""),
                "date": hearing_date,
                "status": "overdue" if hearing_date < today_start else "upcoming",
                "courtLocation": case.get("courtLocation", ""),
            }
        )

    task_query: Dict[str, Any] = {"dueDate": {"$lte": end}, "status": {"$nin": ["Completed", "completed", "Closed", "closed"]}}
    normalized_role = (role or "").lower()
    if normalized_role == "advocate":
        task_query["advocateId"] = user_id
    elif normalized_role == "client":
        task_query["clientId"] = user_id
        task_query["notifyClient"] = True
    elif normalized_role != "admin":
        return []

    async for task in db.tasks.find(task_query):
        due_date = task.get("dueDate")
        if not isinstance(due_date, datetime):
            continue
        deadlines.append(
            {
                "id": str(task["_id"]),
                "type": "task",
                "title": task.get("title", "Task"),
                "caseId": task.get("caseId"),
                "caseTitle": task.get("caseTitle", ""),
                "date": due_date,
                "status": "overdue" if due_date < today_start else task.get("status", "Open"),
                "priority": task.get("priority", "Normal"),
            }
        )

    return sorted(deadlines, key=lambda item: item["date"])


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    return _serialize(doc)
