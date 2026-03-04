from pydantic import BaseModel, Field, validator, field_validator
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import re

# Blocked URL schemes (security risk)
BLOCKED_SCHEMES = {
    'javascript:', 'data:', 'file:', 'ftp:', 'mailto:',
    'tel:', 'sms:', 'vbscript:', 'about:', 'chrome:',
    'chrome-extension:', 'moz-extension:', 'ms-office:',
}

# Maximum URL length to prevent abuse
MAX_URL_LENGTH = 2048

def is_valid_url(url: str) -> tuple[bool, str]:
    """
    Validate URL for security and correctness.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Check for empty string
    if not url or not url.strip():
        return False, "URL cannot be empty"

    # Check URL length
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL too long (maximum {MAX_URL_LENGTH} characters)"

    # Check for blocked schemes (case-insensitive)
    url_lower = url.lower()
    for blocked in BLOCKED_SCHEMES:
        if url_lower.startswith(blocked):
            return False, f"URL scheme '{blocked}' is not allowed"

    # Check for null bytes
    if '\x00' in url:
        return False, "URL contains null bytes"

    # Try to parse the URL
    try:
        parsed = urlparse(url)

        # Must have a scheme and network location
        if not parsed.scheme:
            return False, "URL must include a scheme (http:// or https://)"

        if parsed.scheme not in ('http', 'https'):
            return False, "Only http:// and https:// schemes are allowed"

        if not parsed.netloc:
            return False, "URL must include a domain name"

        # Check for localhost/private IPs if needed (currently allowed for testing)
        # In production, you might want to block: localhost, 127.0.0.1, 0.0.0.0, ::1

        return True, ""

    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

class URLBase(BaseModel):
    long_url: str = Field(..., description="The long URL", min_length=1)
    user_id: Optional[str] = Field(default=None, description="The user ID")

    @field_validator('long_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate and sanitize the URL."""
        # Trim whitespace
        v = v.strip()

        # Validate URL
        is_valid, error_msg = is_valid_url(v)
        if not is_valid:
            raise ValueError(error_msg)

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
    