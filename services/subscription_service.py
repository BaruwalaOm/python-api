from datetime import datetime
from typing import Optional

from bson import ObjectId

from db.mongodb import db


async def expire_due_subscriptions(user_id: Optional[str] = None) -> int:
    """Update expired subscriptions: isActive=false, status=EXPIRED."""
    now = datetime.utcnow()
    query = {
        "endDate": {"$lt": now},
        "status": {"$ne": "EXPIRED"},
    }

    if user_id:
        try:
            query["$or"] = [{"userId": user_id}, {"userId": ObjectId(user_id)}]
        except Exception:
            query["userId"] = user_id

    result = await db.userSubscriptions.update_many(
        query,
        {"$set": {"isActive": False, "status": "EXPIRED"}},
    )
    return result.modified_count
