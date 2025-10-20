"""
Main FastAPI application for Prontivus backend.
"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import structlog
import os

from app.core.config import settings
from app.core.logging import configure_logging, get_logger, request_logger
from app.db.base import check_database_health
from app.api.v1 import auth, clinics, users, patients, appointments, appointment_requests, medical_records, files, invoices, licenses, sync, webhooks, dashboard, reports, cid10, medical_records_lock, medical_records_files, prescriptions_simple, prescriptions_advanced, prescriptions_basic, prescription_verification, password_reset, reports_advanced, tiss_basic, tiss, websocket, emergency_fix, two_fa, payments, consultations, billing, consultation_management, quick_actions, telemedicine, patient_call_system, print, consultation_finalization, user_management  # Complete consultation workflow + billing + extended features + telemedicine + patient call system + print + finalization + user management


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

# CORS middleware - Must be added before other middleware
# Enhanced CORS configuration for better compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:8080",
        "http://localhost:8000",
        "https://prontivus-frontend-ten.vercel.app",
        "https://prontivus.com",
        "https://www.prontivus.com",
        "https://prontivus-frontend.vercel.app",
        "https://prontivus-frontend-git-main.vercel.app",
        "https://prontivus-frontend-git-develop.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Cache-Control",
        "Pragma"
    ],
    expose_headers=[
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers"
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Trusted host middleware
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "*.prontivus.com", 
            "prontivus.com",
            "*.onrender.com",  # Allow Render.com hosting
            "prontivus-backend-wnw2.onrender.com"  # Specific backend host
        ]
    )


# CORS preflight handler
@app.options("/{path:path}")
async def options_handler(request: Request, path: str):
    """Handle CORS preflight requests."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD",
            "Access-Control-Allow-Headers": "Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers, Cache-Control, Pragma",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )

# Custom CORS handler for better compatibility
@app.middleware("http")
async def cors_handler(request: Request, call_next):
    """Custom CORS handler to ensure all requests are handled properly."""
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = Response()
        origin = request.headers.get("origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response
    
    # Process the request
    response = await call_next(request)
    
    # Add CORS headers to all responses
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

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
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging."""
    error_details = exc.errors()
    logger.error(
        "Validation error",
        path=request.url.path,
        method=request.method,
        errors=error_details,
        body=await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
    )
    
    # Ensure CORS headers are included in error responses
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.cors_origins_list:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    
    return JSONResponse(
        status_code=422,
        content={"detail": error_details},
        headers=headers
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )
    
    # Ensure CORS headers are included in error responses
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.cors_origins_list:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
        headers=headers
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
    
    # Ensure CORS headers are included in error responses
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.cors_origins_list:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error", 
            "status_code": 500,
            "detail": str(exc) if settings.debug else "An error occurred"
        },
        headers=headers
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
# Re-enable working routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(two_fa.router, prefix="/api/v1/two_fa", tags=["Two-Factor Authentication"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(clinics.router, prefix="/api/v1/clinics", tags=["Clinics"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(appointment_requests.router, prefix="/api/v1/appointment_requests", tags=["Appointment Requests"])
app.include_router(medical_records.router, prefix="/api/v1/medical_records", tags=["Medical Records"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["Invoices"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(consultations.router, prefix="/api/v1/consultations", tags=["Consultations"])

# Test consultation_management router with different prefix
app.include_router(consultation_management.router, prefix="/api/v1/consultation-mgmt", tags=["Consultation Management"])  # TEST: Try different prefix
# Re-enable additional working routers
app.include_router(quick_actions.router, prefix="/api/v1/quick_actions", tags=["Quick Actions"])
app.include_router(licenses.router, prefix="/api/v1/licenses", tags=["Licenses"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Sync"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
# Re-enable advanced TISS endpoints
app.include_router(tiss.router, prefix="/api/v1/tiss_advanced", tags=["TISS"])  # advanced TISS
app.include_router(tiss_basic.router, prefix="/api/v1/tiss", tags=["TISS"])  # basic CRUD used by UI
app.include_router(cid10.router, prefix="/api/v1/cid10", tags=["CID-10"])
app.include_router(medical_records_lock.router, prefix="/api/v1/medical_records_lock", tags=["Medical Records"])
app.include_router(medical_records_files.router, prefix="/api/v1/medical_records_files", tags=["Medical Records"])
app.include_router(prescriptions_basic.router, prefix="/api/v1/prescriptions", tags=["Prescriptions"])
# app.include_router(prescriptions_advanced.router, prefix="/api/v1/prescriptions_advanced", tags=["Prescriptions"])
app.include_router(prescription_verification.router, prefix="/api/v1/prescription_verification", tags=["Public"])
app.include_router(password_reset.router, prefix="/api/v1/password_reset", tags=["Authentication"])
app.include_router(reports_advanced.router, prefix="/api/v1/reports_advanced", tags=["Reports"])
app.include_router(websocket.router, prefix="/api/v1/websocket", tags=["WebSocket"])  # WebSocket for real-time notifications
app.include_router(telemedicine.router, prefix="/api/v1/telemedicine", tags=["Telemedicine"])  # Telemedicine with WebRTC
app.include_router(patient_call_system.router, prefix="/api/v1/patient_call", tags=["Patient Call System"])  # Patient calling system with secretary interface

# Re-enable team management router
from app.api.v1 import team_management
app.include_router(team_management.router, prefix="/api/v1/team_management", tags=["Team Management"])  # Team management and user roles

# Re-enable new routers
app.include_router(print.router, prefix="/api/v1/print", tags=["Print Documents"])  # Document printing functionality
app.include_router(consultation_finalization.router, prefix="/api/v1/consultation_finalization", tags=["Consultation Finalization"])  # Consultation finalization and history
app.include_router(user_management.router, prefix="/api/v1/user_management", tags=["User Management"])  # User role management and RBAC

# Re-enable exam database router
from app.api.v1 import exam_database
app.include_router(exam_database.router, prefix="/api/v1/exam_database", tags=["Exam Database"])  # Standardized exam database

# Re-enable insurance pricing router
from app.api.v1 import insurance_pricing
app.include_router(insurance_pricing.router, prefix="/api/v1/insurance_pricing", tags=["Insurance Pricing"])  # Automatic pricing by insurance

# Re-enable US medication API router
from app.api.v1 import us_medication_api
app.include_router(us_medication_api.router, prefix="/api/v1/us_medication", tags=["US Medication API"])  # US pharmaceutical database integration

# Re-enable print API router
from app.api.v1 import print_api
app.include_router(print_api.router, prefix="/api/v1/print_api", tags=["Print"])  # Direct printing functionality

# Re-enable pricing API router
from app.api.v1 import pricing_api
app.include_router(pricing_api.router, prefix="/api/v1/pricing_api", tags=["Pricing"])  # Automatic pricing system

# Re-enable vitals API router
from app.api.v1 import vitals_api
app.include_router(vitals_api.router, prefix="/api/v1/vitals_api", tags=["Vitals"])  # Patient vitals with height field

# Keep emergency_fix router commented out as it was temporary
# app.include_router(emergency_fix.router, prefix="/api/v1/emergency", tags=["Emergency"])  # TEMPORARY FIX - DELETE AFTER USE

# Static files for attachments
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads/attachments")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.app_version,
        "environment": settings.app_env,
        "docs": "/docs" if settings.debug else "Documentation not available in production",
        "deployment_version": "v3.30-fix-appointments-auth-dependency"
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