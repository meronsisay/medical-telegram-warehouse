"""
Pydantic schemas for API request/response validation.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


# ============================================
# Channel Schemas
# ============================================
class ChannelActivity(BaseModel):
    """Channel activity response."""
    date: str
    post_count: int
    avg_views: float


class ChannelInfo(BaseModel):
    """Channel information."""
    channel_name: str
    channel_type: str
    total_posts: int
    avg_views: float


# ============================================
# Message Schemas
# ============================================
class MessageResponse(BaseModel):
    """Message search response."""
    message_id: int
    message_text: str
    view_count: int
    forward_count: int
    has_image: bool
    channel_name: str
    message_date: datetime
    image_category: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response wrapper."""
    query: str
    total_results: int
    results: List[MessageResponse]


# ============================================
# Report Schemas
# ============================================
class TopProduct(BaseModel):
    """Top product/term response."""
    term: str
    frequency: int
    channels: List[str]


class VisualContentStats(BaseModel):
    """Visual content statistics."""
    channel_name: str
    total_images: int
    product_display: int
    lifestyle: int
    promotional: int
    avg_views: float


class ReportResponse(BaseModel):
    """Generic report response."""
    report_type: str
    data: List[dict]
    total: int


# ============================================
# Error Schemas
# ============================================
class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    status_code: int