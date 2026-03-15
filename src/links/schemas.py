from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class ShortLinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None


class LinkTopItem(BaseModel):
    short_code: str
    original_url: str
    num_clicks: int
    last_used_at: Optional[datetime] = None