from datetime import datetime, timedelta
from app.db.nosql.connection import get_db
from app.models.schemas import URL, URLCreate, URLDelete
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class URLService:
    def __init__(self):
        self.db = get_db()
        self.logger = logger

    async def store_url(self, url: URLCreate, short_url_id: str):
        try:
            now = datetime.now()
            expires_at = now + timedelta(days=url.expires_at) if url.expires_at else None
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
            raise HTTPException(status_code=500, detail=str(e))
        
    async def get_url(self, short_url_id: str):
        try:
            url_data = await self.db.urls.find_one({"short_url_id": short_url_id}).to_dict()
            self.logger.info(f"URL retrieved successfully: {short_url_id}")
            return url_data
        except Exception as e:
            self.logger.error(f"Error getting URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        
    async def delete_url(self, url_data: URLDelete):
        try:
            await self.db.urls.delete_one({"short_url_id": url_data.short_url_id})
            self.logger.info(f"URL deleted successfully: {url_data.short_url_id}")
        except Exception as e:
            self.logger.error(f"Error deleting URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))