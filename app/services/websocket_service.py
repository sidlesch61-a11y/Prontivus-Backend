"""
WebSocket service for real-time waiting queue notifications.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
import uuid
from fastapi import WebSocket

from ..models.waiting_queue import (
    PatientCalledEvent, PatientRemovedEvent, QueueUpdateEvent,
    WaitingQueue, WaitingQueueStatus
)

logger = logging.getLogger(__name__)

class WebSocketService:
    """Service for managing WebSocket connections and broadcasting events."""
    
    def __init__(self):
        # Store active connections by clinic_id and doctor_id
        self.connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, clinic_id: uuid.UUID, doctor_id: Optional[uuid.UUID] = None):
        """Connect a WebSocket client."""
        
        try:
            await websocket.accept()
            
            # Store connection
            clinic_key = str(clinic_id)
            doctor_key = str(doctor_id) if doctor_id else "all"
            
            if clinic_key not in self.connections:
                self.connections[clinic_key] = {}
            
            if doctor_key not in self.connections[clinic_key]:
                self.connections[clinic_key][doctor_key] = set()
            
            self.connections[clinic_key][doctor_key].add(websocket)
            
            # Store metadata
            self.connection_metadata[websocket] = {
                "clinic_id": clinic_id,
                "doctor_id": doctor_id,
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow()
            }
            
            logger.info(f"WebSocket connected: clinic={clinic_id}, doctor={doctor_id}")
            
            # Send initial queue status
            await self.send_queue_status(websocket, clinic_id, doctor_id)
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            raise
    
    def disconnect(self, websocket: WebSocket, clinic_id: uuid.UUID, doctor_id: Optional[uuid.UUID] = None):
        """Disconnect a WebSocket client."""
        
        try:
            clinic_key = str(clinic_id)
            doctor_key = str(doctor_id) if doctor_id else "all"
            
            if clinic_key in self.connections and doctor_key in self.connections[clinic_key]:
                self.connections[clinic_key][doctor_key].discard(websocket)
                
                # Clean up empty sets
                if not self.connections[clinic_key][doctor_key]:
                    del self.connections[clinic_key][doctor_key]
                
                if not self.connections[clinic_key]:
                    del self.connections[clinic_key]
            
            # Remove metadata
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected: clinic={clinic_id}, doctor={doctor_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")
    
    async def broadcast_patient_called(self, patient_data: Dict[str, Any]):
        """Broadcast patient called event."""
        
        try:
            clinic_id = patient_data.get("clinic_id")
            doctor_id = patient_data.get("doctor_id")
            
            if not clinic_id:
                logger.warning("No clinic_id in patient_called event")
                return
            
            event = PatientCalledEvent(
                queue_id=uuid.UUID(patient_data["queue_id"]),
                appointment_id=uuid.UUID(patient_data["appointment_id"]),
                patient_id=uuid.UUID(patient_data["patient_id"]),
                patient_name=patient_data["patient_name"],
                doctor_id=uuid.UUID(patient_data["doctor_id"]),
                doctor_name=patient_data["doctor_name"],
                position=patient_data["position"],
                called_at=datetime.fromisoformat(patient_data["called_at"]),
                estimated_consultation_start=datetime.fromisoformat(patient_data["estimated_consultation_start"]) if patient_data.get("estimated_consultation_start") else None,
                meta=patient_data.get("meta", {})
            )
            
            await self._broadcast_to_clinic(
                clinic_id,
                event.dict(),
                doctor_id=doctor_id
            )
            
            logger.info(f"Broadcasted patient_called event: {patient_data['patient_name']}")
            
        except Exception as e:
            logger.error(f"Error broadcasting patient_called event: {str(e)}")
    
    async def broadcast_patient_removed(self, queue_entry: WaitingQueue, reason: str):
        """Broadcast patient removed event."""
        
        try:
            event = PatientRemovedEvent(
                queue_id=queue_entry.id,
                appointment_id=queue_entry.appointment_id,
                patient_id=queue_entry.patient_id,
                patient_name="Unknown",  # Would need to fetch from database
                reason=reason,
                removed_at=datetime.utcnow(),
                meta={"position": queue_entry.position, "priority": queue_entry.priority.value}
            )
            
            await self._broadcast_to_clinic(
                queue_entry.clinic_id,
                event.dict(),
                doctor_id=queue_entry.doctor_id
            )
            
            logger.info(f"Broadcasted patient_removed event: {queue_entry.id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting patient_removed event: {str(e)}")
    
    async def broadcast_queue_update(self, clinic_id: uuid.UUID, doctor_id: Optional[uuid.UUID] = None):
        """Broadcast queue update event."""
        
        try:
            # This would typically fetch current queue stats from database
            # For now, we'll create a basic event
            
            event = QueueUpdateEvent(
                clinic_id=clinic_id,
                doctor_id=doctor_id,
                total_waiting=0,  # Would be calculated from database
                total_called=0,
                total_in_consultation=0,
                updated_at=datetime.utcnow(),
                meta={"source": "queue_update"}
            )
            
            await self._broadcast_to_clinic(
                clinic_id,
                event.dict(),
                doctor_id=doctor_id
            )
            
            logger.info(f"Broadcasted queue_update event: clinic={clinic_id}, doctor={doctor_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting queue_update event: {str(e)}")
    
    async def _broadcast_to_clinic(
        self,
        clinic_id: uuid.UUID,
        event_data: Dict[str, Any],
        doctor_id: Optional[uuid.UUID] = None
    ):
        """Broadcast event to all connections for a clinic."""
        
        clinic_key = str(clinic_id)
        
        if clinic_key not in self.connections:
            return
        
        # Determine which connections to send to
        connections_to_notify = set()
        
        if doctor_id:
            # Send to specific doctor and general clinic connections
            doctor_key = str(doctor_id)
            if doctor_key in self.connections[clinic_key]:
                connections_to_notify.update(self.connections[clinic_key][doctor_key])
        
        # Always send to general clinic connections
        if "all" in self.connections[clinic_key]:
            connections_to_notify.update(self.connections[clinic_key]["all"])
        
        # Send to all relevant connections
        disconnected_connections = set()
        
        for websocket in connections_to_notify:
            try:
                await websocket.send_text(json.dumps(event_data))
                
                # Update last activity
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_activity"] = datetime.utcnow()
                
            except Exception as e:
                logger.warning(f"Error sending to WebSocket: {str(e)}")
                disconnected_connections.add(websocket)
        
        # Clean up disconnected connections
        for websocket in disconnected_connections:
            self._cleanup_disconnected_connection(websocket)
    
    def _cleanup_disconnected_connection(self, websocket: WebSocket):
        """Clean up a disconnected WebSocket connection."""
        
        if websocket not in self.connection_metadata:
            return
        
        metadata = self.connection_metadata[websocket]
        clinic_id = metadata["clinic_id"]
        doctor_id = metadata["doctor_id"]
        
        self.disconnect(websocket, clinic_id, doctor_id)
    
    async def send_queue_status(self, websocket: WebSocket, clinic_id: uuid.UUID, doctor_id: Optional[uuid.UUID] = None):
        """Send current queue status to a newly connected client."""
        
        try:
            # This would typically fetch current queue data from database
            # For now, we'll send a basic status message
            
            status_data = {
                "event_type": "queue_status",
                "clinic_id": str(clinic_id),
                "doctor_id": str(doctor_id) if doctor_id else None,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "total_waiting": 0,
                    "total_called": 0,
                    "total_in_consultation": 0,
                    "current_position": None,
                    "estimated_wait_time": None
                }
            }
            
            await websocket.send_text(json.dumps(status_data))
            
        except Exception as e:
            logger.error(f"Error sending queue status: {str(e)}")
    
    async def send_personal_notification(
        self,
        websocket: WebSocket,
        notification_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send a personal notification to a specific WebSocket connection."""
        
        try:
            notification = {
                "event_type": "personal_notification",
                "notification_type": notification_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data or {}
            }
            
            await websocket.send_text(json.dumps(notification))
            
        except Exception as e:
            logger.error(f"Error sending personal notification: {str(e)}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about active WebSocket connections."""
        
        total_connections = 0
        clinic_stats = {}
        
        for clinic_key, doctor_connections in self.connections.items():
            clinic_total = sum(len(connections) for connections in doctor_connections.values())
            clinic_stats[clinic_key] = {
                "total_connections": clinic_total,
                "doctor_connections": {
                    doctor_key: len(connections) 
                    for doctor_key, connections in doctor_connections.items()
                }
            }
            total_connections += clinic_total
        
        return {
            "total_connections": total_connections,
            "clinic_stats": clinic_stats,
            "connection_metadata_count": len(self.connection_metadata)
        }
    
    async def cleanup_inactive_connections(self, max_inactive_minutes: int = 30):
        """Clean up inactive WebSocket connections."""
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=max_inactive_minutes)
            inactive_connections = []
            
            for websocket, metadata in self.connection_metadata.items():
                if metadata["last_activity"] < cutoff_time:
                    inactive_connections.append(websocket)
            
            for websocket in inactive_connections:
                metadata = self.connection_metadata[websocket]
                self.disconnect(
                    websocket,
                    metadata["clinic_id"],
                    metadata["doctor_id"]
                )
            
            if inactive_connections:
                logger.info(f"Cleaned up {len(inactive_connections)} inactive WebSocket connections")
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive connections: {str(e)}")
    
    async def broadcast_system_message(self, clinic_id: uuid.UUID, message: str, message_type: str = "info"):
        """Broadcast a system message to all connections in a clinic."""
        
        try:
            system_message = {
                "event_type": "system_message",
                "message_type": message_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "clinic_id": str(clinic_id)
            }
            
            await self._broadcast_to_clinic(clinic_id, system_message)
            
            logger.info(f"Broadcasted system message to clinic {clinic_id}: {message}")
            
        except Exception as e:
            logger.error(f"Error broadcasting system message: {str(e)}")

# Global WebSocket service instance
websocket_service = WebSocketService()
