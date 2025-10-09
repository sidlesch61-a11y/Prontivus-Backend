"""
Logging configuration for Prontivus backend.
"""

import logging
import sys
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from app.core.config import settings


def configure_logging():
    """Configure application logging."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO if not settings.debug else logging.DEBUG,
        stream=sys.stdout
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    
    # Configure Sentry if DSN is provided
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[
                FastApiIntegration(auto_enabling_instrumentations=True),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=0.1 if settings.is_production else 1.0,
            environment=settings.app_env,
            release=settings.app_version,
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class AuditLogger:
    """Audit logging for compliance and security."""
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_user_action(
        self,
        user_id: str,
        clinic_id: str,
        action: str,
        entity: str,
        entity_id: str = None,
        ip_address: str = None,
        details: Dict[str, Any] = None
    ):
        """Log user action for audit trail."""
        self.logger.info(
            "User action",
            user_id=user_id,
            clinic_id=clinic_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            details=details or {}
        )
    
    def log_security_event(
        self,
        event_type: str,
        user_id: str = None,
        clinic_id: str = None,
        ip_address: str = None,
        details: Dict[str, Any] = None
    ):
        """Log security-related events."""
        self.logger.warning(
            "Security event",
            event_type=event_type,
            user_id=user_id,
            clinic_id=clinic_id,
            ip_address=ip_address,
            details=details or {}
        )
    
    def log_system_event(
        self,
        event_type: str,
        details: Dict[str, Any] = None
    ):
        """Log system-level events."""
        self.logger.info(
            "System event",
            event_type=event_type,
            details=details or {}
        )


# Global audit logger
audit_logger = AuditLogger()


class RequestLogger:
    """Request logging middleware."""
    
    def __init__(self):
        self.logger = get_logger("requests")
    
    async def log_request(self, request, response, process_time: float):
        """Log HTTP request details."""
        self.logger.info(
            "HTTP request",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
        )


# Global request logger
request_logger = RequestLogger()
