from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .base_model import BaseEntity


class Task(BaseEntity):
    id: Optional[str] = None
    caseId: str
    title: str
    description: Optional[str] = ""
    dueDate: datetime
    status: str = "Open"
    priority: str = "Normal"
    assignedTo: Optional[str] = None
    advocateId: Optional[str] = None
    clientId: Optional[str] = None
    notifyClient: bool = False
    completedAt: Optional[datetime] = None
