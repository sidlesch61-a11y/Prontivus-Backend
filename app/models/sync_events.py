"""
Database models for offline sync events and idempotency.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid

class SyncEventType(str, Enum):
    """Sync event type enumeration."""
    CREATE_PATIENT = "create_patient"
    UPDATE_PATIENT = "update_patient"
    DELETE_PATIENT = "delete_patient"
    CREATE_APPOINTMENT = "create_appointment"
    UPDATE_APPOINTMENT = "update_appointment"
    DELETE_APPOINTMENT = "delete_appointment"
    CREATE_MEDICAL_RECORD = "create_medical_record"
    UPDATE_MEDICAL_RECORD = "update_medical_record"
    DELETE_MEDICAL_RECORD = "delete_medical_record"
    CREATE_PRESCRIPTION = "create_prescription"
    UPDATE_PRESCRIPTION = "update_prescription"
    DELETE_PRESCRIPTION = "delete_prescription"
    CREATE_INVOICE = "create_invoice"
    UPDATE_INVOICE = "update_invoice"
    DELETE_INVOICE = "delete_invoice"
    CREATE_FILE = "create_file"
    UPDATE_FILE = "update_file"
    DELETE_FILE = "delete_file"

class SyncEventStatus(str, Enum):
    """Sync event status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"

class ClientSyncEvent(SQLModel, table=True):
    """Client sync event model for offline synchronization."""
    
    __tablename__ = "client_sync_events"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Client identification
    client_event_id: str = Field(description="Unique client-side event ID", index=True)
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key for webhook-like flows", index=True)
    
    # Event details
    event_type: SyncEventType = Field(description="Type of sync event")
    payload: Dict[str, Any] = Field(description="Event payload data", sa_column_kwargs={"type_": "JSONB"})
    client_timestamp: datetime = Field(description="Client-side timestamp")
    
    # Processing status
    status: SyncEventStatus = Field(default=SyncEventStatus.PENDING, description="Processing status")
    processed: bool = Field(default=False, description="Whether event has been processed")
    server_entity_id: Optional[uuid.UUID] = Field(default=None, description="Server-side entity ID after processing")
    
    # Processing metadata
    processing_attempts: int = Field(default=0, description="Number of processing attempts")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    processing_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(default=None, description="When event was processed")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()

class SyncBatch(SQLModel, table=True):
    """Sync batch model for tracking batch processing."""
    
    __tablename__ = "sync_batches"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Batch identification
    batch_id: str = Field(description="Unique batch identifier", index=True)
    client_batch_id: Optional[str] = Field(default=None, description="Client-side batch ID")
    
    # Batch details
    total_events: int = Field(description="Total number of events in batch")
    processed_events: int = Field(default=0, description="Number of successfully processed events")
    failed_events: int = Field(default=0, description="Number of failed events")
    skipped_events: int = Field(default=0, description="Number of skipped events")
    
    # Processing status
    status: SyncEventStatus = Field(default=SyncEventStatus.PENDING, description="Batch processing status")
    processing_started_at: Optional[datetime] = Field(default=None, description="When batch processing started")
    processing_completed_at: Optional[datetime] = Field(default=None, description="When batch processing completed")
    
    # Error handling
    has_errors: bool = Field(default=False, description="Whether batch has any errors")
    error_summary: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()

class SyncConflict(SQLModel, table=True):
    """Sync conflict model for handling data conflicts."""
    
    __tablename__ = "sync_conflicts"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    sync_event_id: uuid.UUID = Field(foreign_key="client_sync_events.id", index=True)
    
    # Conflict details
    conflict_type: str = Field(description="Type of conflict (version, constraint, business_rule)")
    entity_type: str = Field(description="Type of entity with conflict")
    entity_id: uuid.UUID = Field(description="ID of entity with conflict")
    
    # Conflict data
    client_data: Dict[str, Any] = Field(description="Client-side data", sa_column_kwargs={"type_": "JSONB"})
    server_data: Dict[str, Any] = Field(description="Server-side data", sa_column_kwargs={"type_": "JSONB"})
    conflict_details: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Resolution
    resolution: Optional[str] = Field(default=None, description="Conflict resolution (client_wins, server_wins, manual)")
    resolved_by: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None, description="User who resolved conflict")
    resolved_at: Optional[datetime] = Field(default=None, description="When conflict was resolved")
    resolution_notes: Optional[str] = Field(default=None, description="Notes about resolution")
    
    # Status
    status: str = Field(default="pending", description="Conflict status (pending, resolved, ignored)")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    sync_event: Optional["ClientSyncEvent"] = Relationship()
    resolved_by_user: Optional["User"] = Relationship()

# Pydantic schemas for API
class SyncEventRequest(SQLModel):
    """Request schema for sync event."""
    client_event_id: str = Field(description="Unique client-side event ID")
    type: SyncEventType = Field(description="Type of sync event")
    payload: Dict[str, Any] = Field(description="Event payload data")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key")
    client_timestamp: datetime = Field(description="Client-side timestamp")

class SyncEventsRequest(SQLModel):
    """Request schema for batch sync events."""
    events: List[SyncEventRequest] = Field(description="List of sync events")
    batch_id: Optional[str] = Field(default=None, description="Client-side batch ID")

class SyncEventResult(SQLModel):
    """Result schema for sync event processing."""
    client_event_id: str = Field(description="Client-side event ID")
    status: str = Field(description="Processing status")
    server_id: Optional[uuid.UUID] = Field(default=None, description="Server-side entity ID")
    error_msg: Optional[str] = Field(default=None, description="Error message if failed")
    processing_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Processing metadata")

class SyncEventsResponse(SQLModel):
    """Response schema for batch sync events."""
    batch_id: str = Field(description="Server-side batch ID")
    results: List[SyncEventResult] = Field(description="Processing results for each event")
    summary: Dict[str, Any] = Field(description="Batch processing summary")

class SyncConflictResponse(SQLModel):
    """Response schema for sync conflicts."""
    id: uuid.UUID
    conflict_type: str
    entity_type: str
    entity_id: uuid.UUID
    client_data: Dict[str, Any]
    server_data: Dict[str, Any]
    conflict_details: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime

# Utility classes
class SyncEventProcessor:
    """Utility class for processing sync events."""
    
    @staticmethod
    def validate_event_payload(event_type: SyncEventType, payload: Dict[str, Any]) -> bool:
        """Validate event payload based on event type."""
        
        required_fields = {
            SyncEventType.CREATE_PATIENT: ["name", "email"],
            SyncEventType.UPDATE_PATIENT: ["id", "name"],
            SyncEventType.DELETE_PATIENT: ["id"],
            SyncEventType.CREATE_APPOINTMENT: ["patient_id", "doctor_id", "start_time"],
            SyncEventType.UPDATE_APPOINTMENT: ["id", "start_time"],
            SyncEventType.DELETE_APPOINTMENT: ["id"],
            SyncEventType.CREATE_MEDICAL_RECORD: ["patient_id", "doctor_id"],
            SyncEventType.UPDATE_MEDICAL_RECORD: ["id"],
            SyncEventType.DELETE_MEDICAL_RECORD: ["id"],
            SyncEventType.CREATE_PRESCRIPTION: ["patient_id", "medication_name"],
            SyncEventType.UPDATE_PRESCRIPTION: ["id", "medication_name"],
            SyncEventType.DELETE_PRESCRIPTION: ["id"],
            SyncEventType.CREATE_INVOICE: ["patient_id", "amount"],
            SyncEventType.UPDATE_INVOICE: ["id", "amount"],
            SyncEventType.DELETE_INVOICE: ["id"],
            SyncEventType.CREATE_FILE: ["patient_id", "filename"],
            SyncEventType.UPDATE_FILE: ["id", "filename"],
            SyncEventType.DELETE_FILE: ["id"],
        }
        
        required = required_fields.get(event_type, [])
        return all(field in payload for field in required)
    
    @staticmethod
    def extract_entity_id(payload: Dict[str, Any]) -> Optional[uuid.UUID]:
        """Extract entity ID from payload."""
        
        # Try different common ID field names
        id_fields = ["id", "entity_id", "record_id", "appointment_id", "patient_id"]
        
        for field in id_fields:
            if field in payload:
                try:
                    return uuid.UUID(payload[field])
                except (ValueError, TypeError):
                    continue
        
        return None
    
    @staticmethod
    def generate_idempotency_key(event_type: SyncEventType, payload: Dict[str, Any]) -> str:
        """Generate idempotency key for event."""
        
        import hashlib
        
        # Create a deterministic key based on event type and key payload fields
        key_fields = []
        
        if event_type in [SyncEventType.CREATE_PATIENT, SyncEventType.UPDATE_PATIENT]:
            key_fields = ["name", "email", "cpf"]
        elif event_type in [SyncEventType.CREATE_APPOINTMENT, SyncEventType.UPDATE_APPOINTMENT]:
            key_fields = ["patient_id", "doctor_id", "start_time"]
        elif event_type in [SyncEventType.CREATE_MEDICAL_RECORD, SyncEventType.UPDATE_MEDICAL_RECORD]:
            key_fields = ["patient_id", "doctor_id", "record_type"]
        else:
            # Fallback to using all payload fields
            key_fields = list(payload.keys())
        
        # Create hash of key fields
        key_data = {}
        for field in key_fields:
            if field in payload:
                key_data[field] = payload[field]
        
        key_string = f"{event_type.value}:{str(sorted(key_data.items()))}"
        return hashlib.sha256(key_string.encode()).hexdigest()

class SyncConflictResolver:
    """Utility class for resolving sync conflicts."""
    
    @staticmethod
    def detect_conflict(
        client_data: Dict[str, Any],
        server_data: Dict[str, Any],
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """Detect conflicts between client and server data."""
        
        conflicts = []
        
        # Check for version conflicts
        if "version" in client_data and "version" in server_data:
            if client_data["version"] != server_data["version"]:
                conflicts.append({
                    "type": "version_conflict",
                    "field": "version",
                    "client_value": client_data["version"],
                    "server_value": server_data["version"]
                })
        
        # Check for timestamp conflicts
        if "updated_at" in client_data and "updated_at" in server_data:
            client_ts = client_data["updated_at"]
            server_ts = server_data["updated_at"]
            
            if isinstance(client_ts, str):
                client_ts = datetime.fromisoformat(client_ts.replace('Z', '+00:00'))
            if isinstance(server_ts, str):
                server_ts = datetime.fromisoformat(server_ts.replace('Z', '+00:00'))
            
            if abs((client_ts - server_ts).total_seconds()) > 1:  # 1 second tolerance
                conflicts.append({
                    "type": "timestamp_conflict",
                    "field": "updated_at",
                    "client_value": client_data["updated_at"],
                    "server_value": server_data["updated_at"]
                })
        
        # Check for data conflicts in critical fields
        critical_fields = ["name", "email", "status", "amount"]
        for field in critical_fields:
            if field in client_data and field in server_data:
                if client_data[field] != server_data[field]:
                    conflicts.append({
                        "type": "data_conflict",
                        "field": field,
                        "client_value": client_data[field],
                        "server_value": server_data[field]
                    })
        
        if conflicts:
            return {
                "conflict_type": "data_conflict",
                "conflicts": conflicts,
                "severity": "high" if len(conflicts) > 2 else "medium"
            }
        
        return None
    
    @staticmethod
    def resolve_conflict(
        conflict: Dict[str, Any],
        resolution: str,
        resolved_by: uuid.UUID
    ) -> Dict[str, Any]:
        """Resolve a sync conflict."""
        
        resolution_data = {
            "resolution": resolution,
            "resolved_by": str(resolved_by),
            "resolved_at": datetime.utcnow().isoformat(),
            "conflict_details": conflict
        }
        
        return resolution_data

class SyncEventValidator:
    """Utility class for validating sync events."""
    
    @staticmethod
    def validate_patient_data(payload: Dict[str, Any]) -> List[str]:
        """Validate patient data."""
        
        errors = []
        
        # Required fields
        if not payload.get("name"):
            errors.append("Name is required")
        
        if not payload.get("email"):
            errors.append("Email is required")
        
        # Email format validation
        email = payload.get("email", "")
        if email and "@" not in email:
            errors.append("Invalid email format")
        
        # CPF validation (simplified)
        cpf = payload.get("cpf", "")
        if cpf and len(cpf.replace(".", "").replace("-", "")) != 11:
            errors.append("Invalid CPF format")
        
        return errors
    
    @staticmethod
    def validate_appointment_data(payload: Dict[str, Any]) -> List[str]:
        """Validate appointment data."""
        
        errors = []
        
        # Required fields
        if not payload.get("patient_id"):
            errors.append("Patient ID is required")
        
        if not payload.get("doctor_id"):
            errors.append("Doctor ID is required")
        
        if not payload.get("start_time"):
            errors.append("Start time is required")
        
        # Time validation
        start_time = payload.get("start_time")
        if start_time:
            try:
                if isinstance(start_time, str):
                    datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid start time format")
        
        return errors
    
    @staticmethod
    def validate_medical_record_data(payload: Dict[str, Any]) -> List[str]:
        """Validate medical record data."""
        
        errors = []
        
        # Required fields
        if not payload.get("patient_id"):
            errors.append("Patient ID is required")
        
        if not payload.get("doctor_id"):
            errors.append("Doctor ID is required")
        
        return errors
