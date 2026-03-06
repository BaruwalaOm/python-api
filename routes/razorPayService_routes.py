from datetime import datetime, timedelta
import hashlib
import hmac
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import razorpay
from models.payment import Payment, PaymentRequestModel, RazorpayCallback
from models.userSubscription import UserSubscription
from bson import ObjectId
from db.mongodb import db

router = APIRouter()

RAZORPAY_KEY_ID = "rzp_test_ROay1NIJqVnISl"
RAZORPAY_KEY_SECRET = "eCUqj25ustDl2vFLid7MdfRJ"
WEBHOOK_SECRET = "mysecretwebhook"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@router.post("/payment/razorpay-initiate")
async def initiate_razorpay_payment(payment_req: PaymentRequestModel):
    try:
        amount_in_paise = int(payment_req.amount * 100)

        # 1. Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": f"RAZOR_{uuid.uuid4().hex[:10].upper()}",
            "payment_capture": 1
        })

        order_id = razorpay_order["id"]

        # 2. Save payment to DB
        payment = Payment(
            orderId=order_id,
            amount=payment_req.amount,
            status="INITIATED",
            subscriptionPackageId=payment_req.subscriptionPackageId,
            userId=payment_req.userId,
            paymentDate=datetime.utcnow()
        )
        await db.payments.insert_one(payment.dict(exclude_none=True))

        # 3. Return real Razorpay order_id
        return {
            "orderId": order_id,
            "amount": amount_in_paise,
            "key": RAZORPAY_KEY_ID  # Frontend will need this for checkout.js
        }
  
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

   
@router.post("/payment/razorpay-callback")
async def razorpay_callback(callback: Payment):
    try:
        update_result = await db.payments.update_one(
            {"orderId": callback.orderId},
            {
                "$set": {
                    "status": callback.status,
                    "providerTransactionId": callback.providerTransactionId,
                    "paymentMode": "Razorpay",
                    "paymentDate": callback.paymentDate or datetime.utcnow(),
                    "amount": callback.amount,
                    "userId": callback.userId,
                    "subscriptionPackageId": callback.subscriptionPackageId,
                }
            }
        )

        # 2. Fetch updated payment to get ID
        updated_payment = await db.payments.find_one({"orderId": callback.orderId})
        if updated_payment and "_id" in updated_payment:
            await db.payments.update_one(
                {"_id": updated_payment["_id"]},
                {"$set": {"id": str(updated_payment["_id"])}}
            )
        payment_id = str(updated_payment["_id"]) if updated_payment else None

          # ✅ 3. Get username from users collection
        user = await db.users.find_one({"_id": ObjectId(callback.userId)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        created_by_username = user.get("username", "system")

        # ✅ Only create subscription if payment succeeded
        if callback.status == "SUCCESS":
            plan = await db.subscriptionPackages.find_one({"_id": ObjectId(callback.subscriptionPackageId)})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found.")

            # ✅ 1. Check for existing latest subscription (active or expired)
            last_subscription = await db.userSubscriptions.find_one(
                {"userId": callback.userId},
                sort=[("endDate", -1)]
            )
        
            # ✅ 2. Determine new start date
            current_utc = datetime.utcnow()
            if last_subscription and last_subscription.get("endDate") > current_utc:
                start_date = last_subscription["endDate"]
            else:
                start_date = current_utc
        
            # ✅ 3. Calculate end date
            end_date = start_date + timedelta(days=30 * plan["durationMonth"])
        
            # ✅ 4. Create new subscription
            subscription = UserSubscription(
                id="",
                userId=callback.userId,
                subscriptionPackageId=callback.subscriptionPackageId,
                startDate=start_date,
                endDate=end_date,
                isActive=True,
                status="ACTIVE",
                paymentId=payment_id,
                createdBy=created_by_username,
            )

            await db.userSubscriptions.insert_one(subscription.dict(exclude_none=True))

        return {"message": "Razorpay payment processed successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

