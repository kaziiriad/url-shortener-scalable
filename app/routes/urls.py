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

url_router = APIRouter()

# Redirect function (used at root level in main.py)
async def get_url(key: str, db: get_db = Depends(get_db)):
    try:
        # Try Redis first for fast lookup
        redis_client = RedisClient()
        long_url = await redis_client.get(key)
        
        if long_url:
            return RedirectResponse(url=long_url, status_code=302)
        else:
            url_data = await db.urls.find_one({"short_url_id": key})
            if url_data:
                return RedirectResponse(url=url_data["long_url"], status_code=302)
            else:
                raise HTTPException(status_code=404, detail="Short URL not found or expired")   
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Short URL not found or expired")
        raise HTTPException(status_code=500, detail=str(e))
        
@url_router.post("/create")
async def create_url(url: URLCreate, session: AsyncSession = Depends(get_db_async)):
    try:
        # Get unused key from SQL database
        unused_url = await URL.get_unused_key(session)
        if unused_url:
            short_url_id = unused_url.key
            
            # Mark the key as used
            unused_url.is_used = True
            session.add(unused_url)
            await session.commit()
            
            # Store URL mapping in Redis for fast retrieval
            redis_client = RedisClient()
            
            await redis_client.set(short_url_id, url.long_url, expires_in=1800)
            
            return {
                "message": "URL created successfully",
                "short_url": f"{settings.base_url}/{short_url_id}",
                "long_url": url.long_url,
                "expires_at": url.expires_at
            }
        else:
            raise HTTPException(status_code=503, detail="No unused keys available. Please try again later.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



