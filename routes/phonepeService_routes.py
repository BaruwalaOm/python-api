from datetime import datetime, time, timedelta
import uuid
from fastapi import APIRouter, HTTPException, Path
from models.payment import Payment, PaymentRequestModel, PhonePeCallback
from models.userSubscription import UserSubscription
from bson import ObjectId
from db.mongodb import db

router = APIRouter()

PHONEPE_MERCHANT_ID = "YOUR_MERCHANT_ID"
PHONEPE_SALT_KEY = "YOUR_SALT_KEY"
PHONEPE_BASE_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"  # Use sandbox URL
REDIRECT_URL = "https://yourdomain.com/payment/success"
BASE_URL = "http://127.0.0.1:8000/subscription"

@router.post("/payment/phonepe-initiate")
async def initiate_phonepe_payment(payment_req: PaymentRequestModel):
    try:
        order_id = f"ORDER_{uuid.uuid4().hex[:10].upper()}"
        amount_in_paise = int(payment_req.amount * 100)

        # Construct the payment payload for PhonePe
        payload = {
            "merchantId": PHONEPE_MERCHANT_ID,
            "merchantTransactionId": order_id,
            "merchantUserId": str(payment_req.userId),
            "amount": amount_in_paise,
            "callbackUrl": f"{BASE_URL}/payment/phonepe-callback",
            "mobileNumber": "9999999999",  # Optional
            "paymentInstrument": {
                "type": "PAY_PAGE"
            }
        }

        # Store payment record in DB
        payment = Payment(
            id=None,
            orderId=order_id,
            amount=payment_req.amount,
            status="INITIATED",
            subscriptionPackageId=payment_req.subscriptionPackageId,
            userId=payment_req.userId,
            paymentDate=datetime.utcnow(),
            providerTransactionId=None,
            paymentMode=None
        )
        await db.payments.insert_one(payment.dict(exclude_none=True))

        return { "url": f"https://securegw.phonepe.com/v3/checkout/{order_id}" }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payment/phonepe-callback")
async def phonepe_callback(callback: PhonePeCallback):
    try:
        # Update payment record with success
        result = await db.payments.update_one(
            {"orderId": callback.orderId},
            {
                "$set": {
                    "status": callback.status,
                    "providerTransactionId": callback.providerReferenceId,
                    "paymentMode": "Phonepe",
                    "paymentDate": datetime.utcnow(),
                }
            }
        )

        if callback.status == "SUCCESS":
            # Create user subscription
            plan = await db.subscriptionPackages.find_one({"_id": ObjectId(callback.subscriptionPackageId)})
            end_date = datetime.utcnow() + timedelta(days=30 * plan["durationMonth"])

            subscription = UserSubscription(
                userId=callback.userId,
                subscriptionPackageId=callback.subscriptionPackageId,
                startDate=datetime.utcnow(),
                endDate=end_date,
                isActive=True,
                createdBy="phonepe",
                modifiedBy="phonepe",
                createdAt=datetime.utcnow(),
                modifiedAt=datetime.utcnow()
            )
            await db.userSubscriptions.insert_one(subscription.dict(exclude_none=True))

        return {"message": "Payment processed successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
