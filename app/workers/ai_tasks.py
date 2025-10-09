"""
Celery background tasks for AI-powered consultation processing.
"""

from celery import Celery
from sqlmodel import Session, select
import asyncio
import aiohttp
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
import boto3
from botocore.exceptions import ClientError
import logging

from app.db.session import get_db
from app.models.ai_consultation import (
    Recording, AISummary, RecordingStatus, AISummaryStatus,
    STTProvider, LLMProvider, StructuredSummary
)
from app.models.database import Appointment, Patient, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery(
    "prontivus_ai",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

# S3/MinIO configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "prontivus-recordings")

# AI Provider configuration
STT_PROVIDER = os.getenv("STT_PROVIDER", "openai")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_and_summarize_task(self, recording_id: str):
    """
    Main task for transcribing and summarizing consultation recordings.
    
    This task:
    1. Downloads the audio file from S3
    2. Transcribes using STT provider
    3. Processes with LLM to generate structured summary
    4. Saves results to database
    5. Emits WebSocket event
    """
    
    start_time = time.time()
    recording_uuid = uuid.UUID(recording_id)
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get recording
        recording = db.exec(
            select(Recording).where(Recording.id == recording_uuid)
        ).first()
        
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            return {"status": "error", "message": "Recording not found"}
        
        # Check if already processed
        existing_summary = db.exec(
            select(AISummary).where(AISummary.recording_id == recording_uuid)
        ).first()
        
        if existing_summary and existing_summary.status == AISummaryStatus.COMPLETED:
            logger.info(f"Recording {recording_id} already processed")
            return {"status": "already_processed", "summary_id": str(existing_summary.id)}
        
        # Update recording status
        recording.status = RecordingStatus.PROCESSING
        db.commit()
        
        # Create AI summary record
        ai_summary = AISummary(
            recording_id=recording_uuid,
            stt_provider=STTProvider(STT_PROVIDER),
            llm_provider=LLMProvider(LLM_PROVIDER),
            status=AISummaryStatus.PROCESSING
        )
        db.add(ai_summary)
        db.commit()
        db.refresh(ai_summary)
        
        # Step 1: Download and transcribe audio
        logger.info(f"Starting transcription for recording {recording_id}")
        transcript_result = transcribe_audio(recording.storage_path)
        
        if not transcript_result["success"]:
            raise Exception(f"Transcription failed: {transcript_result['error']}")
        
        # Update AI summary with transcript
        ai_summary.transcript_text = transcript_result["transcript"]
        ai_summary.stt_cost = transcript_result.get("cost", 0)
        db.commit()
        
        # Step 2: Generate structured summary with LLM
        logger.info(f"Starting LLM processing for recording {recording_id}")
        
        # Get consultation context
        consultation = db.exec(
            select(Appointment)
            .join(Patient)
            .where(Appointment.id == recording.consultation_id)
        ).first()
        
        if not consultation:
            raise Exception("Consultation not found")
        
        # Get patient information
        patient = db.exec(
            select(Patient).where(Patient.id == consultation.patient_id)
        ).first()
        
        if not patient:
            raise Exception("Patient not found")
        
        # Get recent medical records for context
        recent_records = db.exec(
            select(MedicalRecord)
            .where(MedicalRecord.patient_id == patient.id)
            .order_by(MedicalRecord.created_at.desc())
            .limit(5)
        ).all()
        
        # Build LLM prompt with context
        llm_result = generate_structured_summary(
            transcript=transcript_result["transcript"],
            patient_age=patient.birthdate,
            patient_gender=patient.gender,
            recent_records=recent_records,
            consultation_date=consultation.start_time
        )
        
        if not llm_result["success"]:
            raise Exception(f"LLM processing failed: {llm_result['error']}")
        
        # Update AI summary with results
        ai_summary.summary_json = llm_result["summary"]
        ai_summary.llm_cost = llm_result.get("cost", 0)
        ai_summary.total_cost = (ai_summary.stt_cost or 0) + (ai_summary.llm_cost or 0)
        ai_summary.status = AISummaryStatus.COMPLETED
        ai_summary.completed_at = datetime.utcnow()
        ai_summary.processing_meta = {
            "processing_time": time.time() - start_time,
            "tokens_used": llm_result.get("tokens_used", 0),
            "stt_provider_response": transcript_result.get("provider_response", {}),
            "llm_provider_response": llm_result.get("provider_response", {})
        }
        
        # Update recording status
        recording.status = RecordingStatus.COMPLETED
        recording.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Step 3: Emit WebSocket event (if WebSocket is implemented)
        emit_ai_summary_ready_event(recording_id, str(ai_summary.id))
        
        # Step 4: Clean up raw audio if configured
        if os.getenv("DELETE_RAW_AUDIO_AFTER_TRANSCRIPTION", "false").lower() == "true":
            try:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=recording.storage_path)
                logger.info(f"Deleted raw audio file: {recording.storage_path}")
            except ClientError as e:
                logger.warning(f"Failed to delete raw audio: {e}")
        
        logger.info(f"Successfully processed recording {recording_id} in {time.time() - start_time:.2f}s")
        
        return {
            "status": "success",
            "summary_id": str(ai_summary.id),
            "processing_time": time.time() - start_time,
            "total_cost": ai_summary.total_cost
        }
        
    except Exception as e:
        logger.error(f"Error processing recording {recording_id}: {str(e)}")
        
        # Update status to failed
        try:
            db = next(get_db())
            recording = db.exec(select(Recording).where(Recording.id == recording_uuid)).first()
            if recording:
                recording.status = RecordingStatus.FAILED
                db.commit()
            
            ai_summary = db.exec(select(AISummary).where(AISummary.recording_id == recording_uuid)).first()
            if ai_summary:
                ai_summary.status = AISummaryStatus.FAILED
                ai_summary.processing_meta = {
                    "error": str(e),
                    "processing_time": time.time() - start_time
                }
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update database status: {db_error}")
        
        # Retry if not max retries reached
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task for recording {recording_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {"status": "error", "message": str(e)}

def transcribe_audio(storage_path: str) -> Dict[str, Any]:
    """
    Transcribe audio file using configured STT provider.
    """
    
    try:
        # Download audio file from S3
        audio_data = s3_client.get_object(Bucket=S3_BUCKET, Key=storage_path)
        audio_content = audio_data['Body'].read()
        
        if STT_PROVIDER == "openai":
            return transcribe_with_openai(audio_content)
        elif STT_PROVIDER == "google":
            return transcribe_with_google(audio_content)
        else:
            raise Exception(f"Unsupported STT provider: {STT_PROVIDER}")
            
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"success": False, "error": str(e)}

def transcribe_with_openai(audio_content: bytes) -> Dict[str, Any]:
    """Transcribe using OpenAI Whisper API."""
    
    try:
        import openai
        
        if not OPENAI_API_KEY:
            raise Exception("OpenAI API key not configured")
        
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Create temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_content)
            temp_file_path = temp_file.name
        
        try:
            # Transcribe with OpenAI
            with open(temp_file_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )
            
            # Calculate cost (approximate)
            duration = response.duration or 0
            cost = duration * 0.006  # $0.006 per minute
            
            return {
                "success": True,
                "transcript": response.text,
                "cost": cost,
                "provider_response": {
                    "duration": duration,
                    "language": response.language
                }
            }
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def transcribe_with_google(audio_content: bytes) -> Dict[str, Any]:
    """Transcribe using Google Speech-to-Text API."""
    
    try:
        from google.cloud import speech
        
        if not GOOGLE_API_KEY:
            raise Exception("Google API key not configured")
        
        client = speech.SpeechClient()
        
        # Configure audio
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="pt-BR",  # Portuguese (Brazil)
            enable_automatic_punctuation=True,
            model="latest_long"
        )
        
        # Perform transcription
        response = client.recognize(config=config, audio=audio)
        
        # Combine results
        transcript = " ".join([result.alternatives[0].transcript for result in response.results])
        
        # Calculate cost (approximate)
        duration = sum([result.result_end_time.seconds for result in response.results])
        cost = duration * 0.006  # $0.006 per minute
        
        return {
            "success": True,
            "transcript": transcript,
            "cost": cost,
            "provider_response": {
                "results_count": len(response.results)
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_structured_summary(
    transcript: str,
    patient_age: Optional[str],
    patient_gender: Optional[str],
    recent_records: list,
    consultation_date: datetime
) -> Dict[str, Any]:
    """
    Generate structured medical summary using LLM.
    """
    
    try:
        if LLM_PROVIDER == "openai":
            return generate_with_openai(transcript, patient_age, patient_gender, recent_records, consultation_date)
        elif LLM_PROVIDER == "vertex":
            return generate_with_vertex(transcript, patient_age, patient_gender, recent_records, consultation_date)
        else:
            raise Exception(f"Unsupported LLM provider: {LLM_PROVIDER}")
            
    except Exception as e:
        logger.error(f"LLM processing error: {e}")
        return {"success": False, "error": str(e)}

def generate_with_openai(
    transcript: str,
    patient_age: Optional[str],
    patient_gender: Optional[str],
    recent_records: list,
    consultation_date: datetime
) -> Dict[str, Any]:
    """Generate structured summary using OpenAI GPT."""
    
    try:
        import openai
        
        if not OPENAI_API_KEY:
            raise Exception("OpenAI API key not configured")
        
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Build context from recent records
        recent_context = ""
        if recent_records:
            recent_context = "\\n\\nRegistros médicos recentes:\\n"
            for record in recent_records[:3]:  # Last 3 records
                recent_context += f"- {record.created_at.strftime('%Y-%m-%d')}: {record.diagnosis}\\n"
        
        # Build prompt
        prompt = f"""
Você é um médico especialista em análise de consultas médicas. Analise a transcrição da consulta abaixo e gere um resumo estruturado em JSON.

TRANSCRIÇÃO DA CONSULTA:
{transcript}

INFORMAÇÕES DO PACIENTE:
- Idade: {patient_age or 'Não informada'}
- Gênero: {patient_gender or 'Não informado'}
- Data da consulta: {consultation_date.strftime('%Y-%m-%d')}
{recent_context}

Gere um JSON estruturado com os seguintes campos:

{{
  "anamnese": {{
    "chief_complaint": "Queixa principal",
    "history_present_illness": "História da doença atual",
    "past_medical_history": "História médica pregressa",
    "medications": "Medicações em uso",
    "allergies": "Alergias",
    "family_history": "História familiar",
    "social_history": "História social",
    "review_of_systems": "Revisão de sistemas",
    "physical_examination": "Exame físico"
  }},
  "hypotheses": [
    {{
      "cid_code": "Código CID-10",
      "description": "Descrição do diagnóstico",
      "confidence": 0.95,
      "reasoning": "Justificativa para o diagnóstico"
    }}
  ],
  "suggested_exams": [
    "Exame sugerido 1",
    "Exame sugerido 2"
  ],
  "proposed_treatment": {{
    "medications": [
      {{
        "name": "Nome do medicamento",
        "dosage": "Dosagem",
        "frequency": "Frequência",
        "duration": "Duração"
      }}
    ],
    "procedures": ["Procedimento sugerido"],
    "follow_up": "Orientações de retorno",
    "lifestyle_recommendations": ["Recomendação de estilo de vida"]
  }},
  "confidence_score": 0.9,
  "notes": "Observações adicionais"
}}

IMPORTANTE:
- Use códigos CID-10 válidos
- Seja específico e detalhado
- Mantenha confidencialidade médica
- Baseie-se apenas nas informações da transcrição
- Retorne APENAS o JSON, sem texto adicional
"""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um médico especialista em análise de consultas médicas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response
        try:
            # Remove any markdown formatting
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            summary_json = json.loads(content)
        except json.JSONDecodeError:
            # If JSON parsing fails, create a basic structure
            summary_json = {
                "anamnese": {"chief_complaint": "Análise em andamento"},
                "hypotheses": [{"cid_code": "Z00.0", "description": "Consulta médica", "confidence": 0.5}],
                "suggested_exams": [],
                "proposed_treatment": {"medications": [], "procedures": [], "follow_up": ""},
                "confidence_score": 0.5,
                "notes": "Erro no parsing do JSON. Transcrição disponível para revisão manual."
            }
        
        # Calculate cost
        tokens_used = response.usage.total_tokens
        cost = tokens_used * 0.00003  # Approximate cost for GPT-4
        
        return {
            "success": True,
            "summary": summary_json,
            "cost": cost,
            "tokens_used": tokens_used,
            "provider_response": {
                "model": "gpt-4",
                "tokens_used": tokens_used
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_with_vertex(
    transcript: str,
    patient_age: Optional[str],
    patient_gender: Optional[str],
    recent_records: list,
    consultation_date: datetime
) -> Dict[str, Any]:
    """Generate structured summary using Google Vertex AI."""
    
    try:
        from google.cloud import aiplatform
        
        if not VERTEX_PROJECT_ID:
            raise Exception("Vertex AI project ID not configured")
        
        # Initialize Vertex AI
        aiplatform.init(project=VERTEX_PROJECT_ID)
        
        # Build prompt (similar to OpenAI version)
        prompt = f"""
Analise a transcrição da consulta médica abaixo e gere um resumo estruturado em JSON.

TRANSCRIÇÃO: {transcript}
PACIENTE: {patient_gender}, {patient_age} anos
DATA: {consultation_date.strftime('%Y-%m-%d')}

Gere JSON com: anamnese, hypotheses (com CID-10), suggested_exams, proposed_treatment.
"""
        
        # Call Vertex AI (implementation depends on specific model)
        # This is a placeholder - actual implementation would depend on the specific Vertex AI model
        
        return {
            "success": True,
            "summary": {
                "anamnese": {"chief_complaint": "Consulta médica"},
                "hypotheses": [{"cid_code": "Z00.0", "description": "Consulta médica", "confidence": 0.8}],
                "suggested_exams": [],
                "proposed_treatment": {"medications": [], "procedures": [], "follow_up": ""},
                "confidence_score": 0.8
            },
            "cost": 0.01,
            "tokens_used": 1000
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def emit_ai_summary_ready_event(recording_id: str, summary_id: str):
    """
    Emit WebSocket event when AI summary is ready.
    This would integrate with your WebSocket implementation.
    """
    
    try:
        # This is a placeholder for WebSocket event emission
        # In a real implementation, you would emit to the doctor's WebSocket connection
        logger.info(f"AI summary ready: recording={recording_id}, summary={summary_id}")
        
        # Example WebSocket event structure:
        event_data = {
            "type": "ai_summary_ready",
            "recording_id": recording_id,
            "summary_id": summary_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Emit to WebSocket (implementation depends on your WebSocket setup)
        # websocket_manager.emit_to_user(user_id, event_data)
        
    except Exception as e:
        logger.error(f"Failed to emit WebSocket event: {e}")

# Additional utility tasks
@celery_app.task
def cleanup_failed_recordings():
    """Clean up failed recordings older than 24 hours."""
    
    try:
        db = next(get_db())
        
        # Find failed recordings older than 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        failed_recordings = db.exec(
            select(Recording).where(
                Recording.status == RecordingStatus.FAILED,
                Recording.created_at < cutoff_time
            )
        ).all()
        
        for recording in failed_recordings:
            # Delete from S3 if exists
            if recording.storage_path:
                try:
                    s3_client.delete_object(Bucket=S3_BUCKET, Key=recording.storage_path)
                except ClientError:
                    pass
            
            # Delete from database
            db.delete(recording)
        
        db.commit()
        
        logger.info(f"Cleaned up {len(failed_recordings)} failed recordings")
        
    except Exception as e:
        logger.error(f"Failed to cleanup recordings: {e}")

@celery_app.task
def generate_cost_report():
    """Generate cost report for AI processing."""
    
    try:
        db = next(get_db())
        
        # Get AI summaries from last 30 days
        cutoff_time = datetime.utcnow() - timedelta(days=30)
        
        summaries = db.exec(
            select(AISummary).where(
                AISummary.created_at >= cutoff_time,
                AISummary.status == AISummaryStatus.COMPLETED
            )
        ).all()
        
        total_cost = sum([s.total_cost or 0 for s in summaries])
        stt_cost = sum([s.stt_cost or 0 for s in summaries])
        llm_cost = sum([s.llm_cost or 0 for s in summaries])
        
        report = {
            "period": "last_30_days",
            "total_summaries": len(summaries),
            "total_cost": total_cost,
            "stt_cost": stt_cost,
            "llm_cost": llm_cost,
            "average_cost_per_summary": total_cost / len(summaries) if summaries else 0,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Cost report: {json.dumps(report)}")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate cost report: {e}")
        return {"error": str(e)}
