from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from models.userSubscription import UserSubscription
from db.mongodb import db
from models.auth import RegisterFM, LoginFM
from models.user import User
from models.advocate import Advocate
from bson import ObjectId

router = APIRouter()

@router.post("/register")
async def register_user(registerFM: RegisterFM):
    # Password match validation
    if registerFM.password != registerFM.confirmPassword:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    # Check if username or email exists
    existing_user = await db.users.find_one({"$or": [{"username": registerFM.username}, {"email": registerFM.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists.")

    # Prepare user document (exclude `advocate`)
    user_dict = registerFM.dict(exclude={"advocate", "confirmPassword"}, exclude_unset=True)
    user_dict["_id"] = ObjectId()
    user_dict["createdAt"] = datetime.utcnow()
    user_dict["modifiedAt"] = datetime.utcnow()
    user_dict["createdBy"] = registerFM.email

    # Insert user
    await db.users.insert_one(user_dict)

    # If Advocate, insert into advocates collection
    if registerFM.role.lower() == "advocate" and registerFM.advocate:
        advocate_dict = registerFM.advocate.dict()
        advocate_dict["_id"] = user_dict["_id"]  # Same ID as user
        advocate_dict["createdBy"] = registerFM.email
        await db.advocates.insert_one(advocate_dict)

        # Assign Trial Package
        trial_package = await db.subscriptionPackages.find_one({
            "isTrial": True,
            "isActive": True
        })

        if not trial_package:
            raise HTTPException(status_code=404, detail="No active trial subscription package found.")

        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=trial_package["durationMonth"] * 30)

        subscription = UserSubscription(
            id="",
            userId=str(user_dict["_id"]),
            subscriptionPackageId=str(trial_package["_id"]),
            startDate=start_date,
            endDate=end_date,
            isActive=True,
            description=trial_package["description"],
            status="ACTIVE",
            createdBy=user_dict["username"],
            createdAt=start_date,
            modifiedAt=start_date,
        )

        await db.userSubscriptions.insert_one(subscription.dict(exclude_none=True))

        # Optionally update user
        await db.users.update_one(
            {"_id": user_dict["_id"]},
            {"$set": {"subscriptionPackageId": str(trial_package["_id"])}}
        )


    response_data = {  
        "id": str(user_dict["_id"]),
        "username": user_dict["username"],
        "role": user_dict.get("role"),
        "firstname": user_dict["firstName"],
        "lastname": user_dict["lastName"],
        "createdAt": user_dict["createdAt"],
        "paymentId": "",
        "subscriptionPackageId": str(trial_package["_id"])
    }
    return {"message": "User registered successfully", "user": response_data}

@router.post("/login")
async def login_user(loginFM: LoginFM):
    print("Received login:", loginFM.dict())
    user = await db.users.find_one({"username": loginFM.username})
    print("Received user:", user)
    
    if not user or user["password"] != loginFM.password:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    
    response_data = {
        "id": str(user["_id"]),
        "username": user["username"],
        "role": user.get("role"),
        "firstname": user["firstName"],
        "lastname": user["lastName"],
        "createdAt": user["createdAt"],
        "subscriptionPackageId": user.get("subscriptionPackageId", ""),
    }

    return {"message": "Login successful", "user": response_data}

@router.get("/users", response_model=List[dict])
async def get_all_users():
    try:
         # Fetch all users with roles Advocate, Admin, or Client
        users_cursor = db.users.find({"role": {"$in": ["Advocate", "Admin", "Client"]}})
        users = []
        async for user in users_cursor:
            user["_id"] = str(user["_id"])
            if user.get("advocate") and isinstance(user["advocate"], dict):
                user["advocate"]["id"] = str(user["advocate"].get("id", ""))
            users.append(user)

        return users

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")
    
@router.delete("/users/{user_id}", summary="Delete a user and related records")
async def delete_user(user_id: str):
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    try:
        # 1️⃣ Delete from users
        user_res = await db.users.delete_one({"_id": obj_id})
        if user_res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        # 2️⃣ Delete from clients
        client_res = await db.clients.delete_many({
            "$or": [
                {"_id": obj_id},
                {"user.uid": user_id},
                {"user._id": user_id},
            ]
        })

        # 3️⃣ Delete from advocates
        advocate_res = await db.advocates.delete_many({
            "$or": [
                {"_id": obj_id},
                {"userId": user_id},
                {"uid": user_id},
            ]
        })

        return {
            "users_deleted": user_res.deleted_count,
            "clients_deleted": client_res.deleted_count,
            "advocates_deleted": advocate_res.deleted_count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


