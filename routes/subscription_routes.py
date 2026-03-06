from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Path
from models.payment import Payment, PaymentRequestModel, PhonePeCallback
from models.subscriptionPackage import  GatewayUpdateRequest, SubscriptionPackage
from models.userSubscription import UserSubscription
from bson import ObjectId
from db.mongodb import db

router = APIRouter()

@router.get("/subscription-packages", response_model=List[SubscriptionPackage])
async def get_subscription_packages():
    cursor = db.subscriptionPackages.find({})
    packages = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        packages.append(SubscriptionPackage(**doc))
    return packages

@router.put("/update-subscription-packages/{package_id}", response_model=SubscriptionPackage)
async def update_subscription_package(package_id: str, updated_data: SubscriptionPackage):
    try:
        obj_id = ObjectId(package_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid subscription package ID")

    update_dict = updated_data.dict(exclude={"id"})

    result = await db.subscriptionPackages.update_one({"_id": obj_id}, {"$set": update_dict})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subscription package not found")

    updated_doc = await db.subscriptionPackages.find_one({"_id": obj_id})
    updated_doc["id"] = str(updated_doc["_id"])
    return SubscriptionPackage(**updated_doc)

@router.get("/subscription-packageById/{package_id}", response_model=SubscriptionPackage)
async def get_subscription_package_by_id(package_id: str):
    if not ObjectId.is_valid(package_id):
        raise HTTPException(status_code=400, detail="Invalid subscription package ID.")

    package = await db.subscriptionPackages.find_one({"_id": ObjectId(package_id)})
    if not package:
        raise HTTPException(status_code=404, detail="Subscription package not found.")

    package["id"] = str(package["_id"])
    return SubscriptionPackage(**package)

@router.post("/add-user-subscriptions")
async def add_user_subscription(subscription: UserSubscription):
    try:
        # Ensure referenced subscription package exists
        subscription_package = await db.subscriptionPackages.find_one(
            {"_id": ObjectId(subscription.subscriptionPackageId)}
        )
        if not subscription_package:
            raise HTTPException(status_code=404, detail="Subscription package not found.")

        # Convert to dict and set _id if not present
        sub_dict = subscription.dict(exclude_none=True)
        sub_dict["_id"] = ObjectId() if not subscription.id else ObjectId(subscription.id)
        sub_dict["userId"] = ObjectId(subscription.userId)
        sub_dict["subscriptionPackageId"] = ObjectId(subscription.subscriptionPackageId)

        await db.userSubscriptions.insert_one(sub_dict)
        return {"message": "User subscription added successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user-subscription/{id}", response_model=UserSubscription)
async def get_user_subscription_by_id(id: str = Path(..., description="User subscription ID")):
    try:
        subscription = await db.userSubscriptions.find_one({"_id": ObjectId(id)})
        if not subscription:
            raise HTTPException(status_code=404, detail="User subscription not found.")

        # Convert ObjectId fields to strings
        subscription["id"] = str(subscription["_id"])
        subscription["userId"] = str(subscription["userId"])
        subscription["subscriptionPackageId"] = str(subscription["subscriptionPackageId"])

        return UserSubscription(**subscription)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/user-subscription/by-user/{user_id}")
async def get_user_subscription_by_user_id(user_id: str):
    subscription = await db.userSubscriptions.find_one({"userId": user_id})
    if not subscription:
        raise HTTPException(status_code=404, detail="User subscription not found.")
    subscription["id"] = str(subscription["_id"])
    subscription.pop("_id", None)
    return subscription
    
@router.get("/user-subscriptions", response_model=List[UserSubscription])
async def get_all_user_subscriptions():
    cursor = db.userSubscriptions.find({})
    subscriptions = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        subscriptions.append(UserSubscription(**doc))
    return subscriptions

@router.get("/user-subscriptions/latest/{user_id}", response_model=UserSubscription)
async def get_latest_user_subscription(user_id: str):
    now = datetime.utcnow()

    # 1. Check for future (upcoming) subscription
    upcoming = await db.userSubscriptions.find_one(
        {
            "userId": user_id,
            "startDate": {"$gt": now}
        },
        sort=[("startDate", 1)]  # earliest future plan
    )

    if upcoming:
        upcoming["id"] = str(upcoming["_id"])
        upcoming.pop("_id", None)
        return upcoming

    # 2. Else return active plan
    current = await db.userSubscriptions.find_one(
        {
            "userId": user_id,
            "startDate": {"$lte": now},
            "endDate": {"$gte": now},
            "isActive": True
        },
        sort=[("startDate", -1)]
    )

    if current:
        current["id"] = str(current["_id"])
        current.pop("_id", None)
        return current
    raise HTTPException(status_code=404, detail="No subscription found")

@router.post("/settings/update-payment-gateway")
async def update_selected_gateway(req: GatewayUpdateRequest):
    if req.gateway not in ["PhonePe", "Razorpay"]:
        raise HTTPException(status_code=400, detail="Unsupported gateway.")

    await db.paymentGatewaySettings.update_one(
        {"key": "selectedPayementGateway"},
        {"$set": {"key": "selectedPayementGateway", "value": req.gateway}},
        upsert=True
    )
    return {"message": "Gateway updated successfully."}

@router.get("/settings/payment-gateway")
async def get_selected_gateway():
    setting = await db.paymentGatewaySettings.find_one({"key": "selectedPayementGateway"})
    return {
        "gateway": setting["value"] if setting and "value" in setting else "Razorpay"
    }