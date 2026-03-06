import asyncio
from fastapi import FastAPI
from routes import razorPayService_routes
from routes import phonepeService_routes
from routes.seed import seed_admin_user, seed_subscription_packages
from routes import subscription_routes
from routes import advocate_routes
from routes import superadmin_routes
from routes import account_routes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Case Tracker API")

origins = [
    "http://localhost:9002",  # React frontend
    "http://192.168.0.104:9002",
    # You can add more allowed origins here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Specific frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advocate_routes.router, prefix="/advocate", tags=["Advocate"])

app.include_router(superadmin_routes.router, prefix="/superadmin", tags=["SuperAdmin"])

app.include_router(account_routes.router, prefix="/account", tags=["Account"])

app.include_router(subscription_routes.router, prefix="/subscription", tags=["Subscription"])

app.include_router(phonepeService_routes.router, prefix="/phonepe", tags=["PhonePe"])

app.include_router(razorPayService_routes.router, prefix="/razorpay", tags=["RazorPay"])

@app.on_event("startup")
async def startup_event():
    await seed_subscription_packages()
    await seed_admin_user()

# @app.get("/")
# def root():
#     return {"message": "Welcome to Case Tracker"}
