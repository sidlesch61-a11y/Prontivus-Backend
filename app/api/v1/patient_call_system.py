"""
Patient Call System API
System for calling patients via secretary with external monitor display
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.database import User, Patient, Appointment
from app.models.consultation_extended import QueueStatusResponse

router = APIRouter(prefix="/patient-call", tags=["Patient Call System"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.secretary_connections: List[WebSocket] = []
        self.monitor_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, connection_type: str = "general"):
        await websocket.accept()
        if connection_type == "secretary":
            self.secretary_connections.append(websocket)
        elif connection_type == "monitor":
            self.monitor_connections.append(websocket)
        else:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, connection_type: str = "general"):
        if connection_type == "secretary":
            if websocket in self.secretary_connections:
                self.secretary_connections.remove(websocket)
        elif connection_type == "monitor":
            if websocket in self.monitor_connections:
                self.monitor_connections.remove(websocket)
        else:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def send_to_secretary(self, message: dict):
        for connection in self.secretary_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

    async def send_to_monitor(self, message: dict):
        for connection in self.monitor_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

@router.get("/queue", response_model=List[QueueStatusResponse])
async def get_call_queue(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get current patient queue for calling system"""
    try:
        # Get waiting patients
        query = select(Patient, Appointment).join(
            Appointment, Patient.id == Appointment.patient_id
        ).where(
            Appointment.status == "scheduled"
        ).order_by(Appointment.appointment_time)
        
        result = await db.execute(query)
        appointments = result.all()
        
        queue = []
        for patient, appointment in appointments:
            queue.append(QueueStatusResponse(
                patient_id=str(patient.id),
                patient_name=patient.name,
                appointment_time=appointment.appointment_time,
                status="waiting",
                priority=1,
                insurance_provider=patient.insurance_provider or "Particular"
            ))
        
        return queue
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching call queue: {str(e)}")

@router.post("/call/{patient_id}")
async def call_patient(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Call a specific patient"""
    try:
        # Get patient details
        patient_query = select(Patient).where(Patient.id == patient_id)
        patient_result = await db.execute(patient_query)
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Get appointment details
        appointment_query = select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.status == "scheduled"
        ).order_by(Appointment.appointment_time.desc()).limit(1)
        
        appointment_result = await db.execute(appointment_query)
        appointment = appointment_result.scalar_one_or_none()
        
        if not appointment:
            raise HTTPException(status_code=404, detail="No scheduled appointment found")
        
        # Create call message
        call_message = {
            "type": "patient_call",
            "patient_id": str(patient.id),
            "patient_name": patient.name,
            "appointment_time": appointment.appointment_time.isoformat(),
            "insurance_provider": patient.insurance_provider or "Particular",
            "called_by": current_user.name,
            "called_at": datetime.utcnow().isoformat(),
            "message": f"Paciente {patient.name} - Dr(a). {appointment.doctor_name or 'Médico'}"
        }
        
        # Send to monitor displays
        await manager.send_to_monitor(call_message)
        
        # Send to secretary
        await manager.send_to_secretary({
            "type": "call_confirmation",
            "message": f"Paciente {patient.name} foi chamado com sucesso",
            "patient_id": str(patient.id)
        })
        
        return {
            "success": True,
            "message": f"Paciente {patient.name} foi chamado",
            "call_data": call_message
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling patient: {str(e)}")

@router.post("/announcement")
async def send_announcement(
    announcement: dict,
    current_user: User = Depends(get_current_user)
):
    """Send announcement to waiting room monitor"""
    try:
        message = {
            "type": "announcement",
            "title": announcement.get("title", "Aviso"),
            "message": announcement.get("message", ""),
            "announced_by": current_user.name,
            "announced_at": datetime.utcnow().isoformat()
        }
        
        # Send to monitor displays
        await manager.send_to_monitor(message)
        
        return {
            "success": True,
            "message": "Anúncio enviado com sucesso"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending announcement: {str(e)}")

@router.websocket("/ws/secretary")
async def websocket_secretary(websocket: WebSocket):
    """WebSocket for secretary interface"""
    await manager.connect(websocket, "secretary")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "call_patient":
                # Handle patient call request
                patient_id = message.get("patient_id")
                if patient_id:
                    # This would trigger the call_patient endpoint logic
                    pass
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "secretary")

@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """WebSocket for waiting room monitor"""
    await manager.connect(websocket, "monitor")
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "monitor")

@router.get("/monitor/status")
async def get_monitor_status():
    """Get status of monitor connections"""
    return {
        "secretary_connections": len(manager.secretary_connections),
        "monitor_connections": len(manager.monitor_connections),
        "total_connections": len(manager.active_connections)
    }
