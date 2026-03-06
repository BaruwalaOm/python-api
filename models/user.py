from datetime import datetime
from typing import List, Optional
from pydantic import EmailStr, Field

from .base_model import BaseEntity

class User(BaseEntity):
    firstName: str = Field(..., max_length=100)
    lastName: str = Field(..., max_length=100)
    email: EmailStr
    role: str = "Client"
    username: str
    password: str
    confirmPassword: Optional[str] = None
    isActive: bool = True
    # confirmIndiaAdvocate: bool
    # userSubscriptions: List["UserSubscription"] = []
    # cases: List["Case"] = []

# 🔄 Delayed import for resolving forward refs
from models.case import Case
from models.userSubscription import UserSubscription

User.update_forward_refs()

# from datetime import datetime
# from typing import List, Optional
# from pydantic import EmailStr, Field

# from models.case import Case
# from models.userSubscription import UserSubscription
# from .base_model import BaseEntity

# class User(BaseEntity):
#     Firstname: str = Field(..., max_length=100)
#     Lastname: str = Field(..., max_length=100)
#     Address: Optional[str] = Field(default="", max_length=500)
#     DateOfBirth: Optional[datetime] = None
#     AadharNumber: Optional[str] = Field(default="", max_length=12)
#     PAN: Optional[str] = Field(default="", max_length=10)
#     VotingId: Optional[str] = ""
#     City: Optional[str] = ""
#     State: Optional[str] = ""
#     Country: Optional[str] = "INDIA"
#     Email: EmailStr
#     MobileNo: str
#     Gender: str
#     Role: str
#     Username: str
#     Password: str
#     CasesFM: List["Case"] = []
#     UserSubscriptionsFM: List["UserSubscription"] = []
