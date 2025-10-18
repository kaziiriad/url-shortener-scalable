from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.nosql.connection import get_db
from app.db.sql.connection import get_db_async
from app.core.redis_client import RedisClient
from app.services.url_service import URLService
from app.models.schemas import URLCreate

url_router = APIRouter()

# Redirect function (used at root level in main.py)
async def get_url(key: str, db: get_db = Depends(get_db)):
    try:
        redis_client = RedisClient()
        url_data = await URLService.get_url(mongo_db=db, redis_client=redis_client, short_url_id=key)
        
        if url_data:
            return RedirectResponse(url=url_data["long_url"], status_code=302)
        else:
            raise HTTPException(status_code=404, detail="Short URL not found or expired")
            
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting URL via API: {str(e)}")
        
@url_router.post("/create")
async def create_url(url: URLCreate, session: AsyncSession = Depends(get_db_async), mongo_db = Depends(get_db)):
    try:
        # Use the URLService classmethod directly
        url_data = await URLService.store_url(session=session, mongo_db=mongo_db, url=url)
        
        # Store URL mapping in Redis for fast retrieval
        redis_client = RedisClient()
        await redis_client.set(url_data.short_url_id, url_data.model_dump_json(), expires_in=1800)
        
        return {
            "message": "URL created successfully",
            "short_url": f"{settings.base_url}/{url_data.short_url_id}",
            "long_url": url_data.long_url,
            "expires_at": url_data.expires_at
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating URL via API: {str(e)}")