from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from common.db.nosql.connection import get_db
from common.core.redis_client import RedisClient
# This service will be created later
from redirect_service.services.redirect_service import RedirectService

redirect_router = APIRouter()

@redirect_router.get("/{short_key}")
async def handle_redirect(
    short_key: str,
    mongo_db=Depends(get_db),
    redis_client: RedisClient = Depends(RedisClient)
):
    """
    Redirects a short URL to its original long URL.
    """
    long_url = await RedirectService.get_long_url(short_key, mongo_db, redis_client)
    if not long_url:
        raise HTTPException(status_code=404, detail="URL not found")
    return RedirectResponse(url=long_url)
    
    # Placeholder until service is implemented
    # if short_key == "test":
    #     return RedirectResponse(url="https://google.com")
    # raise HTTPException(status_code=404, detail="URL not found")
