from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

mongo_client = AsyncIOMotorClient(settings.mongo_uri)
db = mongo_client[settings.db_name]

def get_db():
    try:
        return db
    except Exception as e:
        print(e)
        raise e