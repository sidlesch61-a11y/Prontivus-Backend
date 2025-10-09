"""
Database models for waiting queue system with atomic consultation finalization.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import uuid

class WaitingQueueStatus(str, Enum):
    """Waiting queue status enumeration."""
    WAITING = "waiting"
    CALLED = "called"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class WaitingQueuePriority(str, Enum):
    """Waiting queue priority enumeration."""
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    VIP = "vip"

class WaitingQueue(SQLModel, table=True):
    """Waiting queue model for patient queue management."""
    
    __tablename__ = "waiting_queue"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointments.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patients.id", index=True)
    doctor_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    
    # Queue management
    position: int = Field(description="Position in queue (1-based)")
    status: WaitingQueueStatus = Field(default=WaitingQueueStatus.WAITING, description="Current status")
    priority: WaitingQueuePriority = Field(default=WaitingQueuePriority.NORMAL, description="Queue priority")
    
    # Timing
    enqueued_at: datetime = Field(default_factory=datetime.utcnow, description="When patient was added to queue")
    called_at: Optional[datetime] = Field(default=None, description="When patient was called")
    consultation_started_at: Optional[datetime] = Field(default=None, description="When consultation started")
    consultation_ended_at: Optional[datetime] = Field(default=None, description="When consultation ended")
    
    # Estimated times
    estimated_wait_time_minutes: Optional[int] = Field(default=None, description="Estimated wait time in minutes")
    estimated_call_time: Optional[datetime] = Field(default=None, description="Estimated time when patient will be called")
    
    # Queue metadata
    queue_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    notes: Optional[str] = Field(default=None, description="Additional notes")
    
    # Concurrency control
    locked_by: Optional[uuid.UUID] = Field(default=None, description="User ID who locked this queue entry")
    locked_at: Optional[datetime] = Field(default=None, description="When this entry was locked")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    appointment: Optional["Appointment"] = Relationship()
    patient: Optional["Patient"] = Relationship()
    doctor: Optional["User"] = Relationship()

class WaitingQueueLog(SQLModel, table=True):
    """Waiting queue log model for audit trail."""
    
    __tablename__ = "waiting_queue_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    queue_id: uuid.UUID = Field(foreign_key="waiting_queue.id", index=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Event details
    event: str = Field(description="Event type (enqueued, called, consultation_started, etc.)")
    user_id: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None, description="User who triggered event")
    user_role: Optional[str] = Field(default=None, description="Role of user who triggered event")
    
    # Event metadata
    meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    message: Optional[str] = Field(default=None, description="Event message")
    
    # Technical details
    ip_address: Optional[str] = Field(default=None, description="IP address of user")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    queue_entry: Optional["WaitingQueue"] = Relationship()
    clinic: Optional["Clinic"] = Relationship()
    user: Optional["User"] = Relationship()

# Pydantic schemas for API
class WaitingQueueEnqueueRequest(SQLModel):
    """Request schema for enqueuing a patient."""
    appointment_id: uuid.UUID = Field(description="Appointment ID")
    patient_id: uuid.UUID = Field(description="Patient ID")
    priority: WaitingQueuePriority = Field(default=WaitingQueuePriority.NORMAL, description="Queue priority")
    estimated_wait_time_minutes: Optional[int] = Field(default=None, description="Estimated wait time")
    notes: Optional[str] = Field(default=None, description="Additional notes")

class WaitingQueueEnqueueResponse(SQLModel):
    """Response schema for enqueuing a patient."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    position: int
    status: WaitingQueueStatus
    priority: WaitingQueuePriority
    enqueued_at: datetime
    estimated_wait_time_minutes: Optional[int] = None
    estimated_call_time: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

class WaitingQueueDequeueRequest(SQLModel):
    """Request schema for dequeuing a patient."""
    reason: Optional[str] = Field(default=None, description="Reason for removal")
    notes: Optional[str] = Field(default=None, description="Additional notes")

class WaitingQueueDequeueResponse(SQLModel):
    """Response schema for dequeuing a patient."""
    queue_id: uuid.UUID
    patient_id: uuid.UUID
    position: int
    status: WaitingQueueStatus
    message: str

class ConsultationFinalizeRequest(SQLModel):
    """Request schema for finalizing consultation."""
    consultation_notes: Optional[str] = Field(default=None, description="Final consultation notes")
    next_appointment_recommended: Optional[bool] = Field(default=False, description="Whether next appointment is recommended")
    follow_up_instructions: Optional[str] = Field(default=None, description="Follow-up instructions")

class ConsultationFinalizeResponse(SQLModel):
    """Response schema for finalizing consultation."""
    consultation_id: uuid.UUID
    appointment_id: uuid.UUID
    status: str
    next_patient: Optional[Dict[str, Any]] = None
    message: str
    finalized_at: datetime

class WaitingQueueListResponse(SQLModel):
    """Response schema for listing waiting queue."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    position: int
    status: WaitingQueueStatus
    priority: WaitingQueuePriority
    enqueued_at: datetime
    called_at: Optional[datetime] = None
    consultation_started_at: Optional[datetime] = None
    consultation_ended_at: Optional[datetime] = None
    estimated_wait_time_minutes: Optional[int] = None
    estimated_call_time: Optional[datetime] = None
    notes: Optional[str] = None
    queue_meta: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    # Patient and appointment details
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    appointment_time: Optional[datetime] = None
    appointment_type: Optional[str] = None

class WaitingQueueLogResponse(SQLModel):
    """Response schema for waiting queue log."""
    id: uuid.UUID
    queue_id: uuid.UUID
    event: str
    user_id: Optional[uuid.UUID] = None
    user_role: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

# WebSocket event schemas
class WebSocketEvent(SQLModel):
    """Base WebSocket event schema."""
    event_type: str = Field(description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(description="Event data")

class PatientCalledEvent(SQLModel):
    """WebSocket event for patient called."""
    event_type: str = Field(default="patient_called")
    queue_id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    position: int
    called_at: datetime
    estimated_consultation_start: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None

class PatientRemovedEvent(SQLModel):
    """WebSocket event for patient removed."""
    event_type: str = Field(default="patient_removed")
    queue_id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    reason: str
    removed_at: datetime
    meta: Optional[Dict[str, Any]] = None

class QueueUpdateEvent(SQLModel):
    """WebSocket event for queue update."""
    event_type: str = Field(default="queue_update")
    clinic_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    total_waiting: int
    total_called: int
    total_in_consultation: int
    updated_at: datetime
    meta: Optional[Dict[str, Any]] = None

# Utility classes
class WaitingQueueManager:
    """Utility class for waiting queue management."""
    
    @staticmethod
    def calculate_position(clinic_id: uuid.UUID, doctor_id: uuid.UUID, priority: WaitingQueuePriority) -> int:
        """Calculate position in queue based on priority."""
        # Priority-based positioning logic
        priority_weights = {
            WaitingQueuePriority.EMERGENCY: 1,
            WaitingQueuePriority.URGENT: 2,
            WaitingQueuePriority.VIP: 3,
            WaitingQueuePriority.NORMAL: 4
        }
        
        # In a real implementation, this would query the database
        # For now, return a placeholder
        return priority_weights.get(priority, 4)
    
    @staticmethod
    def estimate_wait_time(position: int, average_consultation_minutes: int = 20) -> int:
        """Estimate wait time based on position and average consultation duration."""
        return position * average_consultation_minutes
    
    @staticmethod
    def calculate_call_time(wait_time_minutes: int) -> datetime:
        """Calculate estimated call time."""
        return datetime.utcnow() + timedelta(minutes=wait_time_minutes)
    
    @staticmethod
    def is_queue_entry_active(status: WaitingQueueStatus) -> bool:
        """Check if queue entry is active (not completed/cancelled)."""
        return status in [
            WaitingQueueStatus.WAITING,
            WaitingQueueStatus.CALLED,
            WaitingQueueStatus.IN_CONSULTATION
        ]
    
    @staticmethod
    def can_be_called(status: WaitingQueueStatus) -> bool:
        """Check if patient can be called."""
        return status == WaitingQueueStatus.WAITING

class QueueAnalytics:
    """Utility class for queue analytics."""
    
    @staticmethod
    def calculate_queue_metrics(queue_entries: List[WaitingQueue]) -> Dict[str, Any]:
        """Calculate queue metrics."""
        total_entries = len(queue_entries)
        waiting_count = len([q for q in queue_entries if q.status == WaitingQueueStatus.WAITING])
        called_count = len([q for q in queue_entries if q.status == WaitingQueueStatus.CALLED])
        in_consultation_count = len([q for q in queue_entries if q.status == WaitingQueueStatus.IN_CONSULTATION])
        completed_count = len([q for q in queue_entries if q.status == WaitingQueueStatus.COMPLETED])
        
        # Calculate average wait time
        completed_entries = [q for q in queue_entries if q.status == WaitingQueueStatus.COMPLETED and q.consultation_started_at]
        avg_wait_time = 0
        if completed_entries:
            wait_times = [(q.consultation_started_at - q.enqueued_at).total_seconds() / 60 for q in completed_entries]
            avg_wait_time = sum(wait_times) / len(wait_times)
        
        return {
            "total_entries": total_entries,
            "waiting_count": waiting_count,
            "called_count": called_count,
            "in_consultation_count": in_consultation_count,
            "completed_count": completed_count,
            "average_wait_time_minutes": round(avg_wait_time, 2),
            "queue_efficiency": (completed_count / total_entries * 100) if total_entries > 0 else 0
        }
    
    @staticmethod
    def generate_queue_report(clinic_id: uuid.UUID, queue_entries: List[WaitingQueue]) -> Dict[str, Any]:
        """Generate comprehensive queue report."""
        metrics = QueueAnalytics.calculate_queue_metrics(queue_entries)
        
        # Priority distribution
        priority_distribution = {}
        for priority in WaitingQueuePriority:
            count = len([q for q in queue_entries if q.priority == priority])
            priority_distribution[priority.value] = count
        
        # Time-based analysis
        now = datetime.utcnow()
        overdue_entries = [q for q in queue_entries 
                          if q.estimated_call_time and q.estimated_call_time < now 
                          and q.status == WaitingQueueStatus.WAITING]
        
        return {
            "clinic_id": clinic_id,
            "report_timestamp": now.isoformat(),
            "metrics": metrics,
            "priority_distribution": priority_distribution,
            "overdue_count": len(overdue_entries),
            "recommendations": QueueAnalytics.generate_recommendations(metrics, len(overdue_entries))
        }
    
    @staticmethod
    def generate_recommendations(metrics: Dict[str, Any], overdue_count: int) -> List[str]:
        """Generate recommendations based on queue metrics."""
        recommendations = []
        
        if metrics["average_wait_time_minutes"] > 60:
            recommendations.append("Consider increasing doctor capacity or optimizing consultation duration")
        
        if overdue_count > 0:
            recommendations.append(f"Address {overdue_count} overdue patients to improve patient satisfaction")
        
        if metrics["queue_efficiency"] < 80:
            recommendations.append("Review queue management processes to improve efficiency")
        
        if metrics["waiting_count"] > 10:
            recommendations.append("Consider implementing priority-based queue management")
        
        return recommendations
