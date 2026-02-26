from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class URLBase(BaseModel):
    long_url: str = Field(..., description="The long URL")
    user_id: Optional[str] = Field(default=None, description="The user ID")

    @validator('long_url')
    def validate_url(cls, v):
        if not v.startswith('http://') and not v.startswith('https://'):
            return f'https://{v}'
        return v

class URLCreate(URLBase):
    pass

class URLUpdate(BaseModel):
    long_url: Optional[str] = Field(default=None, description="The long URL")
    expires_at: Optional[datetime] = Field(default=None, description="The expiration date")

class URLDelete(BaseModel):
    short_url_id: str = Field(..., description="The short URL ID to delete")

class URL(URLBase):
    short_url_id: str = Field(..., description="The short URL ID")
    created_at: datetime = Field(default_factory=datetime.now, description="The creation date")
    updated_at: datetime = Field(default_factory=datetime.now, description="The update date")
    expires_at: Optional[datetime] = Field(default=None, description="The expiration date")
    is_active: bool = Field(default=True, description="The active status")
    is_deleted: bool = Field(default=False, description="The deleted status")
    is_expired: bool = Field(default=False, description="The expired status")

    class Config:
        from_attributes = True
    