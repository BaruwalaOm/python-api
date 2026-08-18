import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from fastapi import FastAPI
from routes import razorPayService_routes
from routes import phonepeService_routes
from routes.seed import seed_admin_user, seed_subscription_packages
from routes import subscription_routes
from routes import advocate_routes
from routes import superadmin_routes
from routes import account_routes
from routes import notification_routes
from services.reminder_service import ensure_reminder_indexes, run_reminder_scan
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Case Tracker API")


async def reminder_loop():
    while True:
        now = datetime.utcnow()
        next_morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if next_morning <= now:
            next_morning += timedelta(days=1)
        sleep_seconds = min((next_morning - now).total_seconds(), 6 * 60 * 60)
        await asyncio.sleep(sleep_seconds)
        try:
            await run_reminder_scan()
        except Exception as exc:
            print(f"Reminder scan failed: {exc}")

origins = [
    "http://localhost:9002",  # React frontend
    "http://192.168.0.104:9002",
    "https://caseconnecter-frontend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

app.include_router(notification_routes.router, prefix="/advocate", tags=["Reminders"])

@app.on_event("startup")
async def startup_event():
    await seed_subscription_packages()
    await seed_admin_user()
    await ensure_reminder_indexes()
    await run_reminder_scan()
    app.state.reminder_task = asyncio.create_task(reminder_loop())

@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "reminder_task", None)
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

# @app.get("/")
# def root():
#     return {"message": "Welcome to Case Tracker"}
