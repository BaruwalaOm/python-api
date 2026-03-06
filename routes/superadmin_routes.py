from datetime import datetime
from http.client import InvalidURL
from typing import List
from models.auth import RegisterFM
from fastapi import APIRouter, HTTPException, Request
from db.mongodb import db
from models.user import User
from models.advocate import Advocate
from bson import ObjectId

router = APIRouter()

# @router.post("/add-admin")
# async def add_admin(user: User):
#     user.Role = "Admin"
#     result = await db.users.insert_one(user.dict(by_alias=True))
#     if result.inserted_id:
#         return {"status": "Success", "message": "Admin Added Successfully...!"}
#     raise HTTPException(status_code=500, detail="Insert Admin data failed..!")

# @router.post("/add-Advocate")
# async def add_Advocate(user: User, specialization: str):
#     user_dict = user.dict()
#     user_dict["_id"] = ObjectId()
#     user_dict["Id"] = str(user_dict["_id"])

#     await db.users.insert_one(user_dict)

#     Advocate = Advocate(
#         Id=user_dict["Id"],
#         AdvocateUniqueNumber=f"LAW-{user_dict['MobileNo'][-4:]}",
#         Specialization=specialization,
#         User=user
#     )
#     await db.advocates.insert_one(Advocate.dict(by_alias=True))

#     return {"message": "Advocate added", "Advocate_id": Advocate.Id}


# @router.put("/Advocates/{Advocate_id}")
# async def update_Advocate(Advocate_id: str, Advocate: Advocate, request: Request):
#     logged_in_user = request.headers.get("X-UserId", "system")
#     try:
#         user_oid = ObjectId(Advocate.UserId)
#         Advocate_oid = ObjectId(Advocate_id)
#     except InvalidURL:
#         raise HTTPException(status_code=400, detail="Invalid ObjectId format")

#     if not Advocate.UserId or not Advocate.User:
#         raise HTTPException(status_code=400, detail="Missing User or UserId")

#     # Set modified by
#     Advocate.ModifiedBy = logged_in_user
#     Advocate.User.ModifiedBy = logged_in_user

#     # Update user
#     await db.users.replace_one({"_id": user_oid}, Advocate.User.dict(by_alias=True))

#     # Update Advocate
#     update_result = await db.advocates.replace_one(
#         {"_id": Advocate_oid},
#         Advocate.dict(exclude={"User"}, by_alias=True)
#     )

#     if update_result.modified_count or update_result.matched_count:
#         return {"status": "Success", "message": "Advocate Updated Successfully...!"}

#     raise HTTPException(status_code=500, detail="Could not update Advocate data.")


@router.get("/Advocates", response_model=List[RegisterFM])
async def get_all_advocates():
    results = []
    try:
        # Fetch users with role 'Advocate'
        async for user in db.users.find({"role": {"$in": ["Advocate", "Admin"]}}):
            user["uid"] = str(user["_id"])
            user["confirmPassword"] = user["password"]
            user["advocate"] = None  # Or {} if needed

            results.append(RegisterFM(**user))

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# @router.get("/Advocates/{Advocate_id}", response_model=Advocate)
# async def get_Advocate(Advocate_id: str):
#     AdvocateCollection = db.advocates
#     Advocate = await AdvocateCollection.find_one({"_id": ObjectId(Advocate_id)})
#     if Advocate:
#         return Advocate(**Advocate, id=str(Advocate["_id"]))
#     raise HTTPException(status_code=404, detail="Advocate not found")

@router.get("/advocates/{advocate_id}", response_model=RegisterFM)
async def get_advocate_by_id(advocate_id: str):
    try:
        if not ObjectId.is_valid(advocate_id):
            raise HTTPException(status_code=400, detail="Invalid advocate ID format.")

        user = await db.users.find_one({"_id": ObjectId(advocate_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Add confirmPassword manually (required for RegisterFM)
        user["uid"] = str(user["_id"])
        user["confirmPassword"] = user["password"]

        # Advocate sub-object (optional or nested under user)
        advocate = await db.advocates.find_one({"_id": ObjectId(advocate_id)})
        user["advocate"] = advocate or None

        return RegisterFM(**user)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# @router.delete("/Advocates/{Advocate_id}")
# async def remove_Advocate(Advocate_id: str):
#     res = await db.advocates.delete_one({"_id": ObjectId(Advocate_id)})
#     if res.deleted_count:
#         return {"status": "Success", "message": "Advocate Removed Successfully...!"}
#     raise HTTPException(status_code=500, detail="Advocate deletion failed..!")
