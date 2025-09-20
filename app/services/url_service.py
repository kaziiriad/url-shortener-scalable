from datetime import datetime, timedelta, timezone
from app.db.nosql.connection import get_db
from app.models.schemas import URL, URLCreate, URLDelete
from app.db.sql.models import URL as URLModel
from fastapi import HTTPException
import logging
from app.db.sql.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)

class URLService:
    def __init__(self, session: AsyncSessionLocal, mongo_db=None):
        self.db = mongo_db if mongo_db is not None else get_db()
        self.key_db = session
        self.logger = logger

    async def store_url(self, url: URLCreate):
        try:
            unused_url = await URLModel.get_unused_key(self.key_db)
            if unused_url is not None:
                short_url_id = unused_url.key
            else:
                # activate pre-population of keys
                await URLModel.pre_populate_keys(self.key_db, 1)
                unused_url = await URLModel.get_unused_key(self.key_db)
                short_url_id = unused_url.key
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=15) 
            url_data = URL(
                short_url_id=short_url_id,
                long_url=url.long_url,
                user_id=url.user_id,
                expires_at=expires_at
            )
            await self.db.urls.insert_one(url_data.model_dump())
            self.logger.info(f"URL stored successfully: {short_url_id}")
            return url_data
        except Exception as e:
            self.logger.error(f"Error storing URL: {e}")
            raise HTTPException(status_code=500, detail=f"Error storing URL to MongoDB: {str(e)}")
        
    async def get_url(self, short_url_id: str):
        try:
            url_data = await self.db.urls.find_one({"short_url_id": short_url_id}).to_dict()
            self.logger.info(f"URL retrieved successfully: {short_url_id}")
            return url_data
        except Exception as e:
            self.logger.error(f"Error getting URL: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting URL from MongoDB: {str(e)}")
        
    async def delete_url(self, url_data: URLDelete):
        try:
            await self.db.urls.delete_one({"short_url_id": url_data.short_url_id})
            self.logger.info(f"URL deleted successfully: {url_data.short_url_id}")
        except Exception as e:
            self.logger.error(f"Error deleting URL: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting URL from MongoDB: {str(e)}")