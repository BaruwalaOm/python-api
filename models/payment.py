from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from models.base_model import BaseEntity


class Payment(BaseEntity):
    id: Optional[str] = None
    orderId: str
    amount: float
    status: str
    subscriptionPackageId: str  # Reference to SubscriptionPackage._id
    userId: str                 # Reference to ApplicationUser._id
    paymentDate: datetime
    providerTransactionId: Optional[str] = None  # Transaction ref from PhonePe
    paymentMode: Optional[str] = None 
    # SubscriptionPackage: Optional["SubscriptionPackage"] = None
    # User: Optional["User"] = None

class PhonePeCallback(BaseModel):
    transactionId: str
    providerReferenceId: Optional[str]
    amount: int
    code: str
    success: bool

class PaymentRequestModel(BaseModel):
    userId: str
    subscriptionPackageId: str
    amount: int

class RazorpayCallback(BaseModel):
    id: Optional[str] = None
    amount: float
    orderId: str
    status: str  
    userId: str
    subscriptionPackageId: str
    paymentDate: datetime
    razorpayPaymentId: Optional[str] = None