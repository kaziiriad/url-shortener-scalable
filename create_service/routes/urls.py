from common.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from common.db.nosql.connection import get_db
from common.db.sql.connection import get_db_async
from common.core.redis_client import RedisClient
from create_service.services.url_service import URLService
from common.models.schemas import URLCreate

url_router = APIRouter()

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