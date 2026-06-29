"""
All API endpoints for the Medical Telegram Data Warehouse.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from .database import get_db
from .schemas import (
    ChannelActivity,
    MessageResponse,
    SearchResponse,
    TopProduct,
    VisualContentStats,
    ErrorResponse
)

router = APIRouter()


# ============================================
# Health & Root
# ============================================
@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Medical Telegram Data Warehouse API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "channels": "/api/channels/{channel_name}/activity",
            "search": "/api/search/messages?query={keyword}",
            "top_products": "/api/reports/top-products",
            "visual_content": "/api/reports/visual-content"
        }
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "medical-telegram-api"}


# ============================================
# Endpoint 1: Top Products
# ============================================
@router.get(
    "/api/reports/top-products",
    response_model=List[TopProduct],
    summary="Get most frequently mentioned products",
    description="Returns the most frequently mentioned terms/products across all channels."
)
async def get_top_products(
    limit: int = Query(10, ge=1, le=50, description="Number of top products to return"),
    db: Session = Depends(get_db)
):
    """
    Get most frequently mentioned terms/products across all channels.
    
    - **limit**: Number of results (1-50, default: 10)
    
    Returns terms with frequency and which channels mentioned them.
    """
    query = text("""
        WITH word_counts AS (
            SELECT 
                LOWER(TRIM(REGEXP_REPLACE(word, '[^a-zA-Z0-9]', '', 'g'))) as term,
                COUNT(*) as frequency,
                ARRAY_AGG(DISTINCT c.channel_name) as channels
            FROM "1_marts".fct_messages f
            JOIN "1_marts".dim_channels c ON f.channel_key = c.channel_key
            CROSS JOIN LATERAL regexp_split_to_table(f.message_text, '\s+') as word
            WHERE LENGTH(word) > 3
            GROUP BY term
        )
        SELECT term, frequency, channels
        FROM word_counts
        WHERE term NOT IN (
            'this', 'that', 'with', 'from', 'have', 'were', 'they', 
            'will', 'would', 'could', 'should', 'about', 'what', 'when', 
            'where', 'which', 'there', 'their', 'been', 'being', 'than', 
            'then', 'these', 'them', 'your', 'yours', 'into', 'just', 
            'like', 'more', 'some', 'such', 'very', 'can', 'all', 'are',
            'one', 'has', 'had', 'him', 'her', 'our', 'out', 'see'
        )
        ORDER BY frequency DESC
        LIMIT :limit
    """)
    
    try:
        result = db.execute(query, {"limit": limit})
        return [{"term": row[0], "frequency": row[1], "channels": row[2]} for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Endpoint 2: Channel Activity (FIXED)
# ============================================
@router.get(
    "/api/channels/{channel_name}/activity",
    response_model=List[ChannelActivity],
    summary="Get channel posting activity",
    description="Returns posting activity and trends for a specific channel."
)
async def get_channel_activity(
    channel_name: str,
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """
    Get posting activity for a specific channel.
    
    - **channel_name**: Name of the channel (e.g., "CheMed")
    - **days**: Number of days to look back (1-90, default: 30)
    
    Returns daily post counts and average views.
    """
    # Fixed: Use make_interval for proper parameterized query
    query = text("""
        SELECT 
            d.full_date::date as date,
            COUNT(f.message_id) as post_count,
            COALESCE(AVG(f.view_count), 0) as avg_views
        FROM "1_marts".fct_messages f
        JOIN "1_marts".dim_dates d ON f.date_key = d.date_key
        JOIN "1_marts".dim_channels c ON f.channel_key = c.channel_key
        WHERE c.channel_name = :channel_name
            AND d.full_date >= NOW() - make_interval(days := :days)
        GROUP BY d.full_date
        ORDER BY d.full_date DESC
    """)
    
    try:
        result = db.execute(query, {"channel_name": channel_name, "days": days})
        rows = [{"date": str(row[0]), "post_count": row[1], "avg_views": float(row[2])} for row in result]
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Channel '{channel_name}' not found or has no activity in the last {days} days"
            )
        return rows
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Endpoint 3: Message Search
# ============================================
@router.get(
    "/api/search/messages",
    response_model=SearchResponse,
    summary="Search messages by keyword",
    description="Searches for messages containing a specific keyword."
)
async def search_messages(
    query: str = Query(..., min_length=1, description="Search keyword or phrase"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Search for messages containing a specific keyword.
    
    - **query**: Search term (e.g., "paracetamol")
    - **limit**: Number of results (1-100, default: 20)
    
    Returns messages with channel, date, and engagement metrics.
    """
    search_text = f"%{query}%"
    sql = text("""
        SELECT 
            f.message_id,
            f.message_text,
            f.view_count,
            f.forward_count,
            f.has_image,
            c.channel_name,
            d.full_date as message_date,
            id.image_category
        FROM "1_marts".fct_messages f
        JOIN "1_marts".dim_channels c ON f.channel_key = c.channel_key
        JOIN "1_marts".dim_dates d ON f.date_key = d.date_key
        LEFT JOIN "1_marts".fct_image_detections id ON f.message_id = id.message_id
        WHERE f.message_text ILIKE :search_text
        ORDER BY f.view_count DESC
        LIMIT :limit
    """)
    
    try:
        result = db.execute(sql, {"search_text": search_text, "limit": limit})
        results = [{
            "message_id": row[0],
            "message_text": row[1],
            "view_count": row[2],
            "forward_count": row[3],
            "has_image": row[4],
            "channel_name": row[5],
            "message_date": row[6],
            "image_category": row[7]
        } for row in result]
        
        return SearchResponse(
            query=query,
            total_results=len(results),
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Endpoint 4: Visual Content Stats
# ============================================
@router.get(
    "/api/reports/visual-content",
    response_model=List[VisualContentStats],
    summary="Get visual content statistics",
    description="Returns statistics about image usage across channels."
)
async def get_visual_content_stats(
    db: Session = Depends(get_db)
):
    """
    Get visual content statistics by channel.
    
    Returns:
    - Total images per channel
    - Breakdown by category (product_display, lifestyle, promotional)
    - Average views for images
    """
    query = text("""
        SELECT 
            c.channel_name,
            COUNT(id.message_id) as total_images,
            SUM(CASE WHEN id.is_product_display = 1 THEN 1 ELSE 0 END) as product_display,
            SUM(CASE WHEN id.is_lifestyle = 1 THEN 1 ELSE 0 END) as lifestyle,
            SUM(CASE WHEN id.is_promotional = 1 THEN 1 ELSE 0 END) as promotional,
            COALESCE(AVG(id.view_count), 0) as avg_views
        FROM "1_marts".fct_image_detections id
        JOIN "1_marts".dim_channels c ON id.channel_key = c.channel_key
        GROUP BY c.channel_name
        ORDER BY total_images DESC
    """)
    
    try:
        result = db.execute(query)
        return [{
            "channel_name": row[0],
            "total_images": row[1],
            "product_display": row[2],
            "lifestyle": row[3],
            "promotional": row[4],
            "avg_views": float(row[5])
        } for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Endpoint 5: Channel List (Bonus)
# ============================================
@router.get(
    "/api/channels",
    summary="Get all channels",
    description="Returns a list of all channels with basic information."
)
async def get_channels(
    db: Session = Depends(get_db)
):
    """Get all channels with basic information."""
    query = text("""
        SELECT 
            channel_name,
            channel_type,
            total_posts,
            avg_views
        FROM "1_marts".dim_channels
        ORDER BY total_posts DESC
    """)
    
    try:
        result = db.execute(query)
        return [{
            "channel_name": row[0],
            "channel_type": row[1],
            "total_posts": row[2],
            "avg_views": float(row[3]) if row[3] else 0
        } for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")