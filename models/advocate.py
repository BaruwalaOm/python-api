from typing import List, Optional
from datetime import datetime

from models.user import User
from models.case import Case
from .base_model import BaseEntity

class Advocate(BaseEntity):
    id: Optional[str]
    Specialization: str
    advocateEnrollmentNumber: str
    # User: Optional["User"]
    # Cases: List["Case"] = []
