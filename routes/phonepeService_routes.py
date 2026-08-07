from datetime import datetime, timedelta
import os
import uuid
import base64
import hashlib
import json
import requests

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from models.payment import Payment, PaymentRequestModel, PhonePeCallback
from models.userSubscription import UserSubscription
from bson import ObjectId
from db.mongodb import db

router = APIRouter()

# PhonePe Credentials & Config
PHONEPE_MERCHANT_ID = os.getenv("PHONEPE_MERCHANT_ID")
PHONEPE_SALT_KEY = os.getenv("PHONEPE_SALT_KEY")
PHONEPE_SALT_INDEX = os.getenv("PHONEPE_SALT_INDEX")
PHONEPE_BASE_URL = os.getenv("PHONEPE_BASE_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")
BACKEND_CALLBACK_URL = os.getenv("BACKEND_CALLBACK_URL")


class PhonePeSimulateRequest(BaseModel):
    orderId: str
    action: str  # "SUCCESS" or "FAILED"


async def activate_subscription_for_payment(payment: dict):
    """
    Activates user subscription after payment is verified as successful.
    Guarantees idempotency by checking if subscription for payment already exists.
    """
    payment_id = str(payment["_id"]) if "_id" in payment else payment.get("id")
    user_id = str(payment["userId"])
    plan_id = str(payment["subscriptionPackageId"])

    # 1. Check if subscription already created for this paymentId
    existing_sub = await db.userSubscriptions.find_one({"paymentId": payment_id})
    if existing_sub:
        return existing_sub

    # 2. Fetch user
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    created_by_username = user.get("username", "system") if user else "system"

    # 3. Fetch subscription plan
    plan = await db.subscriptionPackages.find_one({"_id": ObjectId(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")

    # 4. Check for existing latest subscription (active or expired)
    last_subscription = await db.userSubscriptions.find_one(
        {"userId": user_id},
        sort=[("endDate", -1)]
    )

    # 5. Determine new start date & end date
    current_utc = datetime.utcnow()
    if last_subscription and last_subscription.get("endDate") and last_subscription["endDate"] > current_utc:
        start_date = last_subscription["endDate"]
    else:
        start_date = current_utc

    end_date = start_date + timedelta(days=30 * plan["durationMonth"])

    # 6. Create new subscription
    subscription = UserSubscription(
        id="",
        userId=user_id,
        subscriptionPackageId=plan_id,
        startDate=start_date,
        endDate=end_date,
        isActive=True,
        status="ACTIVE",
        paymentId=payment_id,
        createdBy=created_by_username,
    )

    sub_dict = subscription.dict(exclude_none=True)
    res = await db.userSubscriptions.insert_one(sub_dict)
    sub_dict["id"] = str(res.inserted_id)
    return sub_dict


@router.post("/payment/phonepe-initiate")
async def initiate_phonepe_payment(payment_req: PaymentRequestModel):
    try:
        order_id = f"ORD_{uuid.uuid4().hex[:12].upper()}"

        # 1. Store INITIATED payment record in DB
        payment = Payment(
            orderId=order_id,
            amount=payment_req.amount,
            status="INITIATED",
            subscriptionPackageId=payment_req.subscriptionPackageId,
            userId=payment_req.userId,
            paymentDate=datetime.utcnow(),
            providerTransactionId=None,
            paymentMode="PhonePe"
        )
        payment_dict = payment.dict(exclude_none=True)
        await db.payments.insert_one(payment_dict)

        # 2. Redirect user to interactive PhonePe payment page
        checkout_url = f"{FRONTEND_URL}/payment/phonepe-checkout?orderId={order_id}"
        return {"url": checkout_url, "orderId": order_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payment/phonepe-simulate")
async def simulate_phonepe_action(req: PhonePeSimulateRequest):
    try:
        payment = await db.payments.find_one({"orderId": req.orderId})
        if not payment:
            raise HTTPException(status_code=404, detail="Payment order not found")

        status = "SUCCESS" if req.action.upper() == "SUCCESS" else "FAILED"
        provider_txn_id = f"T{datetime.utcnow().strftime('%y%m%d')}{uuid.uuid4().hex[:8].upper()}" if status == "SUCCESS" else None

        await db.payments.update_one(
            {"orderId": req.orderId},
            {
                "$set": {
                    "status": status,
                    "providerTransactionId": provider_txn_id,
                    "paymentMode": "PhonePe",
                    "paymentDate": datetime.utcnow()
                }
            }
        )

        return {"orderId": req.orderId, "status": status, "providerTransactionId": provider_txn_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment/status/{order_id}")
async def check_phonepe_payment_status(order_id: str):
    try:
        payment = await db.payments.find_one({"orderId": order_id})
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")

        payment_status = payment.get("status", "FAILED")
        provider_txn_id = payment.get("providerTransactionId")

        if payment_status == "SUCCESS":
            await activate_subscription_for_payment(payment)

        return {
            "orderId": order_id,
            "status": payment_status,
            "amount": payment.get("amount"),
            "providerTransactionId": provider_txn_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payment/phonepe-callback")
async def phonepe_callback(request: Request):
    try:
        body = await request.json()
        response_base64 = body.get("response")

        if response_base64:
            decoded_bytes = base64.b64decode(response_base64)
            decoded_json = json.loads(decoded_bytes.decode('utf-8'))

            order_id = decoded_json.get("data", {}).get("merchantTransactionId")
            code = decoded_json.get("code")
            provider_ref_id = decoded_json.get("data", {}).get("providerReferenceId")

            if order_id:
                status = "SUCCESS" if code == "PAYMENT_SUCCESS" else "FAILED"
                await db.payments.update_one(
                    {"orderId": order_id},
                    {
                        "$set": {
                            "status": status,
                            "providerTransactionId": provider_ref_id,
                            "paymentMode": "PhonePe",
                            "paymentDate": datetime.utcnow()
                        }
                    }
                )

                if status == "SUCCESS":
                    payment = await db.payments.find_one({"orderId": order_id})
                    if payment:
                        await activate_subscription_for_payment(payment)

        return {"message": "PhonePe callback processed successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
