from datetime import datetime
from typing import Literal, Optional
from models.base_model import BaseEntity


class UserSubscription(BaseEntity):
    id: Optional[str]
    userId: str
    subscriptionPackageId: str 
    paymentId: Optional[str] = None  
    startDate: datetime
    endDate: datetime
    isActive: bool
    status: Literal["ACTIVE", "SCHEDULED", "EXPIRED"]
