"""
Audit middleware for comprehensive logging of sensitive actions.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..models.security import AuditLog, AuditAction, AuditSeverity, AuditManager
from ..db.session import get_db

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive audit logging."""
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None,
        sensitive_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health", "/metrics", "/docs", "/openapi.json", "/favicon.ico"
        ]
        self.sensitive_paths = sensitive_paths or [
            "/api/v1/users", "/api/v1/roles", "/api/v1/permissions",
            "/api/v1/medical_records", "/api/v1/prescriptions",
            "/api/v1/auth/2fa", "/api/v1/audit-logs"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit events."""
        
        # Skip audit for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract request information
        start_time = datetime.utcnow()
        method = request.method
        path = request.url.path
        
        # Determine if this is a sensitive action
        is_sensitive = any(path.startswith(sensitive_path) for sensitive_path in self.sensitive_paths)
        is_modifying_action = method in ["POST", "PATCH", "PUT", "DELETE"]
        
        # Extract user and clinic information from request state
        user_id = getattr(request.state, "user_id", None)
        clinic_id = getattr(request.state, "clinic_id", None)
        user_role = getattr(request.state, "user_role", None)
        
        # Prepare request body for logging (if applicable)
        request_body = None
        if is_modifying_action and method in ["POST", "PATCH", "PUT"]:
            try:
                body = await request.body()
                if body:
                    request_body = json.loads(body.decode())
            except Exception:
                pass  # Skip if body parsing fails
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Log successful actions
            if is_sensitive and is_modifying_action and status_code < 400:
                await self._log_audit_event(
                    request, response, user_id, clinic_id, user_role,
                    AuditAction.CREATE if method == "POST" else AuditAction.UPDATE if method in ["PATCH", "PUT"] else AuditAction.DELETE,
                    request_body, None, status_code, AuditSeverity.MEDIUM
                )
            
            return response
            
        except HTTPException as e:
            # Log failed actions
            if is_sensitive and is_modifying_action:
                await self._log_audit_event(
                    request, None, user_id, clinic_id, user_role,
                    AuditAction.CREATE if method == "POST" else AuditAction.UPDATE if method in ["PATCH", "PUT"] else AuditAction.DELETE,
                    request_body, None, e.status_code, AuditSeverity.HIGH,
                    f"Action failed: {e.detail}"
                )
            
            raise e
            
        except Exception as e:
            # Log unexpected errors
            if is_sensitive and is_modifying_action:
                await self._log_audit_event(
                    request, None, user_id, clinic_id, user_role,
                    AuditAction.CREATE if method == "POST" else AuditAction.UPDATE if method in ["PATCH", "PUT"] else AuditAction.DELETE,
                    request_body, None, 500, AuditSeverity.CRITICAL,
                    f"Unexpected error: {str(e)}"
                )
            
            raise e
    
    async def _log_audit_event(
        self,
        request: Request,
        response: Optional[Response],
        user_id: Optional[uuid.UUID],
        clinic_id: Optional[uuid.UUID],
        user_role: Optional[str],
        action: AuditAction,
        old_values: Optional[Dict[str, Any]],
        new_values: Optional[Dict[str, Any]],
        status_code: int,
        severity: AuditSeverity,
        error_message: Optional[str] = None
    ):
        """Log audit event to database."""
        
        try:
            # Determine resource type from path
            resource_type = self._extract_resource_type(request.url.path)
            resource_id = self._extract_resource_id(request.url.path)
            
            # Redact sensitive data
            redacted_old_values = AuditManager.redact_sensitive_data(old_values) if old_values else None
            redacted_new_values = AuditManager.redact_sensitive_data(new_values) if new_values else None
            
            # Create audit log entry
            audit_data = {
                "id": str(uuid.uuid4()),
                "clinic_id": str(clinic_id) if clinic_id else None,
                "user_id": str(user_id) if user_id else None,
                "user_role": user_role,
                "action": action.value,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "old_values": redacted_old_values,
                "new_values": redacted_new_values,
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "severity": severity.value,
                "metadata": {
                    "query_params": dict(request.query_params),
                    "error_message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "is_sensitive": AuditManager.is_sensitive_resource(resource_type),
                "created_at": datetime.utcnow()
            }
            
            # Log to database (simplified - in production, use proper DB session)
            logger.info(f"AUDIT: {json.dumps(audit_data)}")
            
        except Exception as e:
            logger.error(f"Error logging audit event: {str(e)}")
    
    def _extract_resource_type(self, path: str) -> str:
        """Extract resource type from URL path."""
        
        # Remove API version prefix
        if path.startswith("/api/v1/"):
            path = path[8:]
        
        # Split path and get first segment
        segments = path.strip("/").split("/")
        if segments:
            return segments[0]
        
        return "unknown"
    
    def _extract_resource_id(self, path: str) -> Optional[uuid.UUID]:
        """Extract resource ID from URL path."""
        
        try:
            # Remove API version prefix
            if path.startswith("/api/v1/"):
                path = path[8:]
            
            # Split path and look for UUID segments
            segments = path.strip("/").split("/")
            for segment in segments:
                try:
                    return uuid.UUID(segment)
                except ValueError:
                    continue
            
            return None
            
        except Exception:
            return None

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # In production, use Redis or similar
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting."""
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        current_time = datetime.utcnow()
        minute_key = current_time.strftime("%Y-%m-%d-%H-%M")
        key = f"{client_ip}:{minute_key}"
        
        if key in self.requests:
            if self.requests[key] >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"}
                )
            self.requests[key] += 1
        else:
            self.requests[key] = 1
        
        # Clean up old entries
        self._cleanup_old_entries(current_time)
        
        return await call_next(request)
    
    def _cleanup_old_entries(self, current_time: datetime):
        """Clean up old rate limit entries."""
        
        current_minute = current_time.strftime("%Y-%m-%d-%H-%M")
        keys_to_remove = [key for key in self.requests.keys() if not key.endswith(current_minute)]
        
        for key in keys_to_remove:
            del self.requests[key]

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details."""
        
        start_time = datetime.utcnow()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Response: {response.status_code} in {duration:.3f}s")
        
        return response

# Utility functions for audit logging
async def log_user_action(
    db_session,
    user_id: uuid.UUID,
    clinic_id: uuid.UUID,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[uuid.UUID],
    request: Request,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
):
    """Log a user action to audit trail."""
    
    try:
        # Determine severity
        severity = AuditManager.determine_severity(action, resource_type)
        
        # Redact sensitive data
        redacted_old_values = AuditManager.redact_sensitive_data(old_values) if old_values else None
        redacted_new_values = AuditManager.redact_sensitive_data(new_values) if new_values else None
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=clinic_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            endpoint=str(request.url.path),
            method=request.method,
            old_values=redacted_old_values,
            new_values=redacted_new_values,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            severity=severity,
            metadata={
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            },
            is_sensitive=AuditManager.is_sensitive_resource(resource_type)
        )
        
        db_session.add(audit_log)
        await db_session.commit()
        
    except Exception as e:
        logger.error(f"Error logging user action: {str(e)}")

async def log_system_event(
    db_session,
    clinic_id: uuid.UUID,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[uuid.UUID],
    message: str,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
    metadata: Optional[Dict[str, Any]] = None
):
    """Log a system event to audit trail."""
    
    try:
        # Create audit log
        audit_log = AuditLog(
            clinic_id=clinic_id,
            user_id=None,  # System event
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            endpoint="system",
            method="SYSTEM",
            old_values=None,
            new_values=None,
            ip_address=None,
            user_agent="system",
            severity=severity,
            metadata={
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            },
            is_sensitive=AuditManager.is_sensitive_resource(resource_type)
        )
        
        db_session.add(audit_log)
        await db_session.commit()
        
    except Exception as e:
        logger.error(f"Error logging system event: {str(e)}")

def get_audit_summary(clinic_id: uuid.UUID, days: int = 30) -> Dict[str, Any]:
    """Get audit summary for a clinic."""
    
    # This would typically query the database
    # For now, return placeholder data
    
    return {
        "clinic_id": str(clinic_id),
        "period_days": days,
        "total_events": 0,
        "events_by_action": {},
        "events_by_severity": {},
        "events_by_user": {},
        "sensitive_events": 0,
        "failed_actions": 0
    }
