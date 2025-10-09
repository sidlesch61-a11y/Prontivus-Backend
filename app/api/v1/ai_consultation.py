"""
API endpoints for AI-powered consultation recording and summarization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from typing import Dict, Any, Optional
import uuid
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime, timedelta
import json

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.ai_consultation import (
    Recording, AISummary, RecordingStatus, AISummaryStatus,
    RecordingStartRequest, RecordingStartResponse,
    RecordingCompleteRequest, RecordingCompleteResponse,
    AISummaryResponse, AIAcceptRequest, AIAcceptResponse
)
from app.models.database import User, Appointment, MedicalRecord
from app.workers.tasks import transcribe_and_summarize_task

router = APIRouter(prefix="/api/v1/consultations", tags=["AI Consultation"])
security = HTTPBearer()

# S3/MinIO configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "prontivus-recordings")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION
)

def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

def get_user_agent(request: Request) -> str:
    """Get user agent string."""
    return request.headers.get("User-Agent", "Unknown")

@router.post("/{consultation_id}/record/start", response_model=RecordingStartResponse)
async def start_recording(
    consultation_id: uuid.UUID,
    request_data: RecordingStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start recording a consultation.
    
    Creates a recording record and returns a presigned URL for file upload.
    Requires explicit consent from the user.
    """
    
    # Check if consultation exists and user has access
    consultation = db.exec(
        select(Appointment).where(
            Appointment.id == consultation_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    ).first()
    
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found"
        )
    
    # Check if user can record (doctor or admin)
    if current_user.role not in ["doctor", "admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and administrators can start recordings"
        )
    
    # Require explicit consent
    if not request_data.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required to start recording"
        )
    
    # Create consent metadata
    consent_meta = {
        "consent_given": True,
        "consent_timestamp": datetime.utcnow().isoformat(),
        "user_ip": get_client_ip(request),
        "user_agent": get_user_agent(request),
        "user_id": str(current_user.id),
        "consultation_id": str(consultation_id)
    }
    
    # Create recording record
    recording = Recording(
        consultation_id=consultation_id,
        started_by=current_user.id,
        consent_given=True,
        consent_meta=consent_meta,
        record_meta=request_data.record_meta,
        status=RecordingStatus.PENDING
    )
    
    db.add(recording)
    db.commit()
    db.refresh(recording)
    
    # Generate presigned URL for file upload
    try:
        file_key = f"consultations/{consultation_id}/recordings/{recording.id}.wav"
        
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': file_key,
                'ContentType': 'audio/wav'
            },
            ExpiresIn=3600  # 1 hour
        )
        
        # Update recording with storage path
        recording.storage_path = file_key
        db.commit()
        
        return RecordingStartResponse(
            recording_id=recording.id,
            upload_url=presigned_url,
            expires_in=3600
        )
        
    except ClientError as e:
        # Clean up recording if S3 fails
        db.delete(recording)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )

@router.post("/{consultation_id}/record/complete", response_model=RecordingCompleteResponse)
async def complete_recording(
    consultation_id: uuid.UUID,
    request_data: RecordingCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete recording upload and start AI processing.
    
    Marks the recording as uploaded and enqueues the transcription and summarization task.
    """
    
    # Get recording
    recording = db.exec(
        select(Recording).where(
            Recording.id == request_data.recording_id,
            Recording.consultation_id == consultation_id,
            Recording.started_by == current_user.id
        )
    ).first()
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    if recording.status != RecordingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recording is not in pending status: {recording.status}"
        )
    
    # Update recording status
    recording.status = RecordingStatus.UPLOADED
    recording.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Enqueue AI processing task
    try:
        transcribe_and_summarize_task.delay(str(recording.id))
        
        return RecordingCompleteResponse(
            recording_id=recording.id,
            status=recording.status,
            message="Recording uploaded successfully. AI processing started."
        )
        
    except Exception as e:
        # Rollback status if task enqueue fails
        recording.status = RecordingStatus.FAILED
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start AI processing: {str(e)}"
        )

@router.get("/{consultation_id}/ai-summaries/{summary_id}", response_model=AISummaryResponse)
async def get_ai_summary(
    consultation_id: uuid.UUID,
    summary_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI-generated summary for a consultation recording.
    """
    
    # Get AI summary with recording
    ai_summary = db.exec(
        select(AISummary)
        .join(Recording)
        .where(
            AISummary.id == summary_id,
            Recording.consultation_id == consultation_id,
            Recording.started_by == current_user.id
        )
    ).first()
    
    if not ai_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI summary not found"
        )
    
    return AISummaryResponse(
        id=ai_summary.id,
        recording_id=ai_summary.recording_id,
        status=ai_summary.status,
        transcript_text=ai_summary.transcript_text,
        summary_json=ai_summary.summary_json,
        stt_provider=ai_summary.stt_provider,
        llm_provider=ai_summary.llm_provider,
        total_cost=ai_summary.total_cost,
        created_at=ai_summary.created_at,
        updated_at=ai_summary.updated_at,
        completed_at=ai_summary.completed_at
    )

@router.post("/{consultation_id}/ai-accept", response_model=AIAcceptResponse)
async def accept_ai_summary(
    consultation_id: uuid.UUID,
    request_data: AIAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accept AI-generated summary and create medical record.
    
    Creates a medical record from the AI summary (draft -> final) if approved.
    """
    
    # Get AI summary with recording
    ai_summary = db.exec(
        select(AISummary)
        .join(Recording)
        .where(
            AISummary.id == request_data.summary_id,
            Recording.consultation_id == consultation_id,
            Recording.started_by == current_user.id
        )
    ).first()
    
    if not ai_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI summary not found"
        )
    
    if ai_summary.status != AISummaryStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AI summary is not completed: {ai_summary.status}"
        )
    
    # Get consultation
    consultation = db.exec(
        select(Appointment).where(Appointment.id == consultation_id)
    ).first()
    
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found"
        )
    
    # Create medical record from AI summary
    try:
        # Extract data from AI summary
        summary_data = ai_summary.summary_json or {}
        edited_data = request_data.edited_payload
        
        # Create medical record
        medical_record = MedicalRecord(
            appointment_id=consultation_id,
            clinic_id=current_user.clinic_id,
            doctor_id=current_user.id,
            patient_id=consultation.patient_id,
            record_type="encounter",
            anamnesis=edited_data.get("anamnese", {}).get("chief_complaint", ""),
            physical_exam=edited_data.get("anamnese", {}).get("physical_examination", ""),
            diagnosis=edited_data.get("hypotheses", [{}])[0].get("description", "") if edited_data.get("hypotheses") else "",
            icd_code=edited_data.get("hypotheses", [{}])[0].get("cid_code", "") if edited_data.get("hypotheses") else "",
            treatment_plan=edited_data.get("proposed_treatment", {}).get("treatment_plan", "")
        )
        
        db.add(medical_record)
        db.commit()
        db.refresh(medical_record)
        
        # Create audit log
        audit_log = {
            "action": "ai_summary_accepted",
            "entity": "medical_records",
            "entity_id": str(medical_record.id),
            "ai_summary_id": str(ai_summary.id),
            "recording_id": str(ai_summary.recording_id),
            "cost": ai_summary.total_cost,
            "edited": edited_data != summary_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log audit (you might want to create an audit_logs table)
        print(f"AUDIT: {json.dumps(audit_log)}")
        
        return AIAcceptResponse(
            summary_id=ai_summary.id,
            medical_record_id=medical_record.id,
            status="accepted",
            message="AI summary accepted and medical record created successfully."
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create medical record: {str(e)}"
        )

@router.get("/{consultation_id}/recordings")
async def list_recordings(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all recordings for a consultation.
    """
    
    # Check if consultation exists and user has access
    consultation = db.exec(
        select(Appointment).where(
            Appointment.id == consultation_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    ).first()
    
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found"
        )
    
    # Get recordings
    recordings = db.exec(
        select(Recording)
        .where(Recording.consultation_id == consultation_id)
        .order_by(Recording.created_at.desc())
    ).all()
    
    return {
        "consultation_id": consultation_id,
        "recordings": [
            {
                "id": recording.id,
                "status": recording.status,
                "consent_given": recording.consent_given,
                "file_size": recording.file_size,
                "created_at": recording.created_at,
                "ai_summaries_count": len(recording.ai_summaries)
            }
            for recording in recordings
        ]
    }
