from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

client = None
db = None
users_collection = None  # Add your collections here
doctors_collection = None

async def init_db():
    global client, db, users_collection,doctors_collection
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        db = client["myapp"]  # ✅ Explicitly select your DB
        users_collection = db["users"]
        doctors_collection = db["doctors"]

        print("✅ MongoDB Connected")
    except Exception as e:
        print("❌ MongoDB Connection Error:", e)
        raise e
def get_users_collection():
    if users_collection is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return users_collection
def get_doctors_collection():
    if doctors_collection is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return doctors_collection
def get_db():
    global db
    if db is None:
        raise RuntimeError("MongoDB not initialized. Call init_db() first.")
    return db


async def close_db():
    global client
    if client:
        client.close()
        print("🛑 MongoDB Connection Closed")
