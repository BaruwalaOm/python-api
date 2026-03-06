from typing import List, Optional
from datetime import datetime
from models.user import User
from .base_model import BaseEntity

class Client(BaseEntity):
    id: Optional[str]
    user: User 
    cases: Optional[List["Case"]] = []

from models.case import Case
Client.update_forward_refs()