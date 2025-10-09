"""
Main FastAPI application for Prontivus backend.
"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.logging import configure_logging, get_logger, request_logger
from app.db.base import check_database_health
from app.api.v1 import auth, clinics, users, patients, appointments, medical_records, files, invoices, licenses, sync, webhooks, dashboard, reports, cid10, medical_records_lock, medical_records_files, prescriptions_advanced, prescriptions_basic, prescription_verification, password_reset, reports_advanced, tiss_basic, websocket  # tiss temporarily disabled


# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    import os
    # Startup
    logger.info("Starting Prontivus backend", version=settings.app_version)
    
    # Health check (skip if SKIP_DB_CHECK is set)
    if os.getenv("SKIP_DB_CHECK") != "1":
        try:
            health = await check_database_health()
            if health["status"] != "healthy":
                logger.warning("Database health check failed - running without database", health=health)
            else:
                logger.info("Database connected successfully")
        except Exception as e:
            logger.warning(f"Database not available - running in development mode without DB: {e}")
    else:
        logger.warning("Database check skipped (SKIP_DB_CHECK=1)")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Prontivus backend")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Medical SaaS Backend API for Prontivus",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted host middleware
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.prontivus.com", "prontivus.com"]
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    await request_logger.log_request(request, response, process_time)
    
    return response


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(
        "Unhandled exception",
        exception=str(exc),
        path=request.url.path,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_health = await check_database_health()
    return {
        "status": "healthy" if db_health["status"] == "healthy" else "unhealthy",
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": db_health["status"],
        "timestamp": db_health["timestamp"]
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check endpoint."""
    db_health = await check_database_health()
    
    return {
        "status": "healthy" if db_health["status"] == "healthy" else "unhealthy",
        "version": settings.app_version,
        "environment": settings.app_env,
        "services": {
            "database": db_health,
            "redis": {"status": "unknown"},  # TODO: Add Redis health check
            "storage": {"status": "unknown"},  # TODO: Add S3/MinIO health check
        },
        "timestamp": db_health["timestamp"]
    }


# API routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(clinics.router, prefix="/api/v1/clinics", tags=["Clinics"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(medical_records.router, prefix="/api/v1/medical_records", tags=["Medical Records"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["Invoices"])
app.include_router(licenses.router, prefix="/api/v1/licenses", tags=["Licenses"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Sync"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
# app.include_router(tiss.router, tags=["TISS"])  # advanced TISS - temporarily disabled
app.include_router(tiss_basic.router, tags=["TISS"])  # basic CRUD used by UI
app.include_router(cid10.router, prefix="/api/v1", tags=["CID-10"])
app.include_router(medical_records_lock.router, prefix="/api/v1", tags=["Medical Records"])
app.include_router(medical_records_files.router, prefix="/api/v1", tags=["Medical Records"])
app.include_router(prescriptions_basic.router, prefix="/api/v1", tags=["Prescriptions"])
app.include_router(prescriptions_advanced.router, prefix="/api/v1", tags=["Prescriptions"])
app.include_router(prescription_verification.router, prefix="/api/v1", tags=["Public"])
app.include_router(password_reset.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(reports_advanced.router, prefix="/api/v1", tags=["Reports"])
app.include_router(websocket.router, tags=["WebSocket"])  # WebSocket for real-time notifications


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.app_version,
        "environment": settings.app_env,
        "docs": "/docs" if settings.debug else "Documentation not available in production"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )