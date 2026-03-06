from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class BaseEntity(BaseModel):
    # _id : any
    createdBy: Optional[str] = None
    modifiedBy: Optional[str] = None
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    modifiedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
