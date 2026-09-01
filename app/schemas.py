from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: str | None = Field(default=None, min_length=3, max_length=10, pattern=r"^[a-zA-Z0-9_-]+$")


class LinkUpdate(BaseModel):
    original_url: HttpUrl


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    original_url: HttpUrl
    click_count: int
    created_at: datetime


class ClickEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    short_code: str
    clicked_at: datetime
    user_agent: str | None = None
    referrer: str | None = None
    ip_address: str | None = None


class ItemCount(BaseModel):
    name: str
    count: int


class LinkAnalyticsResponse(BaseModel):
    short_code: str
    original_url: HttpUrl
    total_clicks: int
    created_at: datetime
    top_referrers: list[ItemCount]
    top_user_agents: list[ItemCount]
    recent_events: list[ClickEventResponse]