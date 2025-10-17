"""
Simple telemedicine API endpoints for testing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
import logging
from datetime import datetime

from ...core.auth import AuthDependencies
from ...db.session import get_db_session
from ...models.telemedicine import TelemedSessionCreateRequest, TelemedSessionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telemed", tags=["telemedicine"])

@router.post("/sessions", response_model=TelemedSessionResponse)
async def create_simple_session(
    session_data: TelemedSessionCreateRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a simple telemedicine session for testing."""
    try:
        # Generate a simple session ID
        session_id = str(uuid.uuid4())
        
        # For now, return a simple response without database storage
        # In production, you would save to database using the TelemedSession model
        return TelemedSessionResponse(
            session_id=session_id,
            room_id=f"room_{session_id[:8]}",
            link_token=f"token_{session_id[:8]}",
            status="created",
            message="Session created successfully",
            created_at=datetime.now(),
            expires_at=datetime.now().replace(hour=23, minute=59, second=59)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating session: {str(e)}"
        )

@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get session details."""
    try:
        return {
            "session_id": session_id,
            "room_id": f"room_{session_id[:8]}",
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session: {str(e)}"
        )

@router.post("/sessions/{session_id}/consent", response_model=dict)
async def give_consent(
    session_id: str,
    consent_data: dict,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Accept and record consent for a telemedicine session (simplified)."""
    try:
        return {
            "session_id": session_id,
            "consent": {
                "user_id": str(getattr(current_user, "id", "")),
                **consent_data,
            },
            "status": "consent_recorded",
            "message": "Consent recorded successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording consent: {str(e)}",
        )

@router.post("/sessions/{session_id}/end", response_model=dict)
async def end_session(
    session_id: str,
    end_data: dict,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """End a telemedicine session (simplified)."""
    try:
        ended_by = end_data.get("ended_by") or str(getattr(current_user, "id", ""))
        end_reason = end_data.get("end_reason", "normal_completion")
        return {
            "session_id": session_id,
            "ended_by": ended_by,
            "end_reason": end_reason,
            "ended_at": datetime.now().isoformat(),
            "status": "ended",
            "message": "Session ended successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ending session: {str(e)}",
        )