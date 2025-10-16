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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telemed", tags=["telemedicine"])

@router.post("/sessions", response_model=dict)
async def create_simple_session(
    session_data: dict,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a simple telemedicine session for testing."""
    try:
        # Generate a simple session ID
        session_id = str(uuid.uuid4())
        
        return {
            "session_id": session_id,
            "room_id": f"room_{session_id[:8]}",
            "link_token": f"token_{session_id[:8]}",
            "status": "created",
            "message": "Session created successfully"
        }
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