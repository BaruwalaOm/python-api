from pydantic import BaseModel
from typing import List, Optional
from models.advocate import Advocate
from models.client import Client
from models.userSubscription import UserSubscription

class LoginFM(BaseModel):
    username: str
    password: str

class RegisterFM(BaseModel):
    uid: Optional[str]
    firstName: str 
    lastName: str 
    email: str
    role: str = "Advocate"
    username: str
    password: str
    confirmPassword: str
    isActive: Optional[bool] = True
    advocate: Optional["Advocate"] = None
    subscriptionPackageId: Optional[str] = None

    # confirmIndiaAdvocate: bool 
    # client: Optional["Client"] = None
    # userSubscriptions: List["UserSubscription"] = []
