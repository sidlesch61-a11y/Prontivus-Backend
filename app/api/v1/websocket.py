"""
WebSocket endpoints for real-time notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
from typing import Optional
import uuid

from app.db.session import get_db_session
from app.core.security import security
from app.models.database import User
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections
active_connections: dict[str, WebSocket] = {}


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """Verify token and get user."""
    try:
        payload = security.verify_token(token, "access")
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        return user
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time notifications."""
    
    # Get database session
    db_gen = get_db_session()
    db = await anext(db_gen)
    
    try:
        # Verify token and get user
        user = await get_user_from_token(token, db)
        
        if not user:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        
        # Accept connection
        await websocket.accept()
        
        # Store connection
        user_key = str(user.id)
        active_connections[user_key] = websocket
        
        logger.info(f"WebSocket connected: user={user.email}")
        
        # Send initial connection success message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "WebSocket connection established",
            "user_id": str(user.id),
            "user_name": user.name,
        })
        
        # Keep connection alive and handle incoming messages
        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_text()
                
                # Parse message
                try:
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    # Handle ping/pong for keepalive
                    if message_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    
                    # Handle other message types as needed
                    elif message_type == "subscribe":
                        # Client wants to subscribe to specific notification types
                        await websocket.send_json({
                            "type": "subscribed",
                            "channels": message.get("channels", [])
                        })
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from {user.email}")
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: user={user.email}")
        
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    
    finally:
        # Clean up connection
        if user:
            user_key = str(user.id)
            if user_key in active_connections:
                del active_connections[user_key]
        
        # Close database session
        try:
            await db.close()
        except:
            pass


async def broadcast_notification(user_id: str, notification: dict):
    """Broadcast a notification to a specific user."""
    if user_id in active_connections:
        try:
            websocket = active_connections[user_id]
            await websocket.send_json(notification)
            logger.info(f"Notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
            # Remove dead connection
            del active_connections[user_id]


async def broadcast_to_clinic(clinic_id: str, notification: dict):
    """Broadcast a notification to all users in a clinic."""
    # This would require tracking which users belong to which clinic
    # For now, we'll just log it
    logger.info(f"Broadcasting to clinic {clinic_id}: {notification}")

