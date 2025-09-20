from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.nosql.connection import get_db
from datetime import datetime, timezone
from app.db.sql.models import URL
from app.db.sql.connection import get_db_async
from app.core.redis_client import RedisClient
from app.services.url_service import URLService
from app.models.schemas import URLCreate, URLDelete
import json

url_router = APIRouter()

# Redirect function (used at root level in main.py)
async def get_url(key: str, db: get_db = Depends(get_db)):
    try:
        # Try Redis first for fast lookup
        redis_client = RedisClient()
        redis_data = await redis_client.get(key)
        
        if redis_data:
            url_data = json.loads(redis_data)
            expired_at = url_data.get("expires_at")
            if expired_at and datetime.fromisoformat(expired_at) < datetime.now(timezone.utc):
                await redis_client.delete(key)
                raise HTTPException(status_code=404, detail="Short URL not found or expired")
            else:
                return RedirectResponse(url=url_data["long_url"], status_code=302)
        else:
            url_data = await db.urls.find_one({"short_url_id": key})
            if url_data:
                return RedirectResponse(url=url_data["long_url"], status_code=302)
            else:
                raise HTTPException(status_code=404, detail="Short URL not found or expired")
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Short URL not found or expired")
        raise HTTPException(status_code=500, detail=f"Error getting URL via API: {str(e)}")
        
@url_router.post("/create")
async def create_url(url: URLCreate, session: AsyncSession = Depends(get_db_async), mongo_db = Depends(get_db)):
    try:
        # Get unused key from SQL database
        url_service = URLService(session, mongo_db)
        url_data = await url_service.store_url(url)
        # Store URL mapping in Redis for fast retrieval
        redis_client = RedisClient()
        await redis_client.set(url_data.short_url_id, url_data.model_dump_json(), expires_in=1800)
        return {
            "message": "URL created successfully",
            "short_url": f"{settings.base_url}/{url_data.short_url_id}",
            "long_url": url_data.long_url,
            "expires_at": url_data.expires_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating URL via API: {str(e)}")


