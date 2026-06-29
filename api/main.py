"""
FastAPI application for Medical Telegram Data Warehouse.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .endpoints import router

# Create FastAPI app
app = FastAPI(
    title="Medical Telegram Data Warehouse API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all endpoints
app.include_router(router)

# Root endpoint is defined in endpoints.py