from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Query

from db.mongodb import db
from models.task import Task
from services.reminder_service import (
    create_notification,
    get_upcoming_deadlines,
    run_reminder_scan,
    serialize_doc,
    user_can_access_case,
)

router = APIRouter()


async def _get_case_or_404(case_id: str):
    if not ObjectId.is_valid(case_id):
        raise HTTPException(status_code=400, detail="Invalid case ID")
    case = await db.cases.find_one({"_id": ObjectId(case_id)})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/notifications", response_model=List[dict])
async def list_notifications(
    userId: str = Query(...),
    role: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    await run_reminder_scan()
    notifications = []
    async for item in db.notifications.find({"recipientId": userId}).sort("createdAt", -1).limit(limit):
        notifications.append(serialize_doc(item))
    return notifications


@router.get("/notifications/unread-count")
async def unread_count(userId: str = Query(...), role: str = Query(...)):
    await run_reminder_scan()
    count = await db.notifications.count_documents({"recipientId": userId, "readAt": None})
    return {"count": count}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, userId: str = Query(...)):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "recipientId": userId},
        {"$set": {"readAt": datetime.utcnow(), "modifiedAt": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@router.put("/notifications/read-all")
async def mark_all_notifications_read(userId: str = Query(...)):
    await db.notifications.update_many(
        {"recipientId": userId, "readAt": None},
        {"$set": {"readAt": datetime.utcnow(), "modifiedAt": datetime.utcnow()}},
    )
    return {"message": "Notifications marked as read"}


@router.get("/deadlines/upcoming", response_model=List[dict])
async def upcoming_deadlines(
    userId: str = Query(...),
    role: str = Query(...),
    days: int = Query(default=14, ge=1, le=90),
):
    return await get_upcoming_deadlines(userId, role, days)


@router.post("/reminders/run")
async def run_reminders_now():
    return await run_reminder_scan()


@router.get("/tasks", response_model=List[dict])
async def list_tasks(
    userId: str = Query(...),
    role: str = Query(...),
    caseId: Optional[str] = Query(default=None),
):
    query = {}
    if caseId:
        case = await _get_case_or_404(caseId)
        if not user_can_access_case(case, userId, role):
            raise HTTPException(status_code=403, detail="Not allowed to view tasks for this case")
        query["caseId"] = caseId
        if role.lower() == "client":
            query["clientId"] = userId
            query["notifyClient"] = True
    elif role.lower() == "advocate":
        query["advocateId"] = userId
    elif role.lower() == "client":
        query["clientId"] = userId
        query["notifyClient"] = True
    elif role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")

    tasks = []
    async for task in db.tasks.find(query).sort("dueDate", 1):
        tasks.append(serialize_doc(task))
    return tasks


@router.post("/tasks")
async def create_task(task: Task, userId: str = Query(...), role: str = Query(...)):
    case = await _get_case_or_404(task.caseId)
    if role.lower() not in {"advocate", "admin"} or not user_can_access_case(case, userId, role):
        raise HTTPException(status_code=403, detail="Only the assigned advocate or admin can create tasks")

    now = datetime.utcnow()
    task_dict = task.dict(exclude={"id"}, exclude_none=True)
    task_dict["_id"] = ObjectId()
    task_dict["advocateId"] = case.get("advocateId")
    task_dict["clientId"] = case.get("clientId")
    task_dict["caseTitle"] = case.get("caseTitle", "")
    task_dict["createdAt"] = task_dict.get("createdAt") or now
    task_dict["modifiedAt"] = now
    task_dict["createdBy"] = userId
    task_dict["modifiedBy"] = userId
    await db.tasks.insert_one(task_dict)

    if task.notifyClient and case.get("clientId"):
        await create_notification(
            recipient_id=case["clientId"],
            recipient_role="Client",
            title="New case task",
            message=f"{task.title} was added to {case.get('caseTitle', 'your case')}.",
            notification_type="task_created",
            related_case_id=task.caseId,
            related_task_id=str(task_dict["_id"]),
            due_date=task.dueDate,
            dedupe_key=f"task-created:{str(task_dict['_id'])}:{case['clientId']}",
            created_by=userId,
        )

    return {"message": "Task created", "task_id": str(task_dict["_id"])}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    data: dict = Body(...),
    userId: str = Query(...),
    role: str = Query(...),
):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID")
    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    case = await _get_case_or_404(task["caseId"])
    if role.lower() not in {"advocate", "admin"} or not user_can_access_case(case, userId, role):
        raise HTTPException(status_code=403, detail="Only the assigned advocate or admin can update tasks")

    allowed = {"title", "description", "dueDate", "status", "priority", "assignedTo", "notifyClient"}
    update = {key: value for key, value in data.items() if key in allowed}
    if "dueDate" in update and isinstance(update["dueDate"], str):
        update["dueDate"] = datetime.fromisoformat(update["dueDate"].replace("Z", "+00:00")).replace(tzinfo=None)
    if update.get("status", "").lower() == "completed":
        update["completedAt"] = datetime.utcnow()
    elif "status" in update:
        update["completedAt"] = None
    update["modifiedAt"] = datetime.utcnow()
    update["modifiedBy"] = userId

    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update})
    return {"message": "Task updated"}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, userId: str = Query(...), role: str = Query(...)):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID")
    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    case = await _get_case_or_404(task["caseId"])
    if role.lower() not in {"advocate", "admin"} or not user_can_access_case(case, userId, role):
        raise HTTPException(status_code=403, detail="Only the assigned advocate or admin can delete tasks")

    await db.tasks.delete_one({"_id": ObjectId(task_id)})
    return {"message": "Task deleted"}
