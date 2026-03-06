from typing import Optional
from pydantic import BaseModel
from models.base_model import BaseEntity


class SubscriptionPackage(BaseEntity):
    id: Optional[str]
    name: str
    durationMonth: int
    isTrial: bool
    packagePrice: int
    isActive: bool
    description: str

class GatewayUpdateRequest(BaseModel):
    gateway: str