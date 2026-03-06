# seed.py

from datetime import datetime
import bcrypt
from bson import ObjectId
from models.subscriptionPackage import SubscriptionPackage  # your Pydantic model
from db.mongodb import db  # your MongoDB collection

async def seed_subscription_packages():
    existing = await db.subscriptionPackages.count_documents({})
    if existing > 0:
        print("Subscription packages already exist. Skipping seeding.")
        return

    static_packages = [
        {
            "_id": ObjectId(),
            "name": "Trial Access",
            "durationMonth": 1,
            "isTrial": True,
            "packagePrice": 0,
            "isActive": True,
            "description": "Full access for 1 month.",
            "createdAt": datetime.utcnow(),
            "createdBy": "admin@123.com",
            "modifiedBy": "",
            "modifiedAt": datetime.utcnow()
        },
        {
            "_id": ObjectId(),
            "name": "3 Month Access",
            "durationMonth": 3,
            "isTrial": False,
            "packagePrice": 300,
            "isActive": True,
            "description": "₹300 for 3 months.",
            "createdAt": datetime.utcnow(),
            "createdBy": "admin@123.com",
            "modifiedBy": "",
            "modifiedAt": datetime.utcnow()
        },
        {
            "_id": ObjectId(),
            "name": "6 Month Access",
            "durationMonth": 6,  
            "isTrial": False,
            "packagePrice": 500,
            "isActive": True,
            "description": "₹500 for 6 months.",
            "createdAt": datetime.utcnow(),
            "createdBy": "admin@123.com",
            "modifiedBy": "",
            "modifiedAt": datetime.utcnow()
        },
        {
            "_id": ObjectId(),
            "name": "12 Month Access",
            "durationMonth": 12,
            "isTrial": False,
            "packagePrice": 800,
            "isActive": True,
            "description": "₹800 for 12 months.",
            "createdAt": datetime.utcnow(),
            "createdBy": "admin@123.com",
            "modifiedBy": "",
            "modifiedAt": datetime.utcnow()
        },
    ]

    await db.subscriptionPackages.insert_many(static_packages)
    print("Seeded subscription packages successfully.")


async def seed_admin_user():
    email = "admin@123.com"
    existing = await db.users.find_one({"email": email})
    if existing:
        print("Admin user already exists. Skipping seeding.")
        return

    # hashed_password = bcrypt.hashpw("Admin@123".encode("utf-8"), bcrypt.gensalt())

    admin_user = {
        "_id": ObjectId(),
        "uid": "",
        "firstName": "Admin",
        "lastName": "Test",
        "email": email,
        "role": "Admin",
        "username": email,
        "password": "Admin@123",
        "isActive": True,
        "advocate": [],
        "subscriptionPackageId": "",
        "createdAt": datetime.utcnow(),
        "createdBy": "system",
        "modifiedAt": datetime.utcnow(),
        "modifiedBy": ""
    }

    await db.users.insert_one(admin_user)
    print("Admin user seeded successfully.")  