"""
Files API endpoints for S3/MinIO integration.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from botocore.exceptions import ClientError
import boto3
from botocore.client import Config

from app.core.auth import get_current_user, require_medical_records_write
from app.core.config import settings
from app.db.session import get_db_session
from app.models import MedicalRecord, AuditLog
from app.schemas import FilePresignRequest, FilePresignResponse, FileCompleteRequest, FileResponse

router = APIRouter()

# S3/MinIO client
s3_client = boto3.client(
    's3',
    endpoint_url=settings.s3_endpoint,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
    config=Config(signature_version='s3v4')
)


@router.post("/presign", response_model=FilePresignResponse)
async def presign_upload(
    request: FilePresignRequest,
    current_user = Depends(require_medical_records_write)
):
    """Generate presigned URL for file upload."""
    # Generate unique file ID
    file_id = uuid.uuid4()
    
    # Create S3 key
    s3_key = f"exams/{current_user.clinic_id}/{file_id}/{request.filename}"
    
    try:
        # Generate presigned URL for upload
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.s3_bucket,
                'Key': s3_key,
                'ContentType': request.content_type
            },
            ExpiresIn=3600  # 1 hour
        )
        
        return FilePresignResponse(
            upload_url=presigned_url,
            file_id=file_id,
            expires_in=3600
        )
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}"
        )


@router.post("/complete", response_model=FileResponse)
async def complete_upload(
    request: FileCompleteRequest,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Complete file upload and register in database."""
    # Verify medical record exists and belongs to clinic
    if request.record_id:
        record_result = await db.execute(
            select(MedicalRecord).where(
                MedicalRecord.id == request.record_id,
                MedicalRecord.clinic_id == current_user.clinic_id
            )
        )
        record = record_result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medical record not found"
            )
    
    # Create S3 key
    s3_key = f"exams/{current_user.clinic_id}/{request.file_id}/"
    
    # Get file info from S3
    try:
        response = s3_client.list_objects_v2(
            Bucket=settings.s3_bucket,
            Prefix=s3_key
        )
        
        if not response.get('Contents'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage"
            )
        
        file_obj = response['Contents'][0]
        file_url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{file_obj['Key']}"
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify file upload: {str(e)}"
        )
    
    # Create exam record
    exam = Exam(
        clinic_id=current_user.clinic_id,
        record_id=request.record_id,
        uploaded_by=current_user.id,
        file_url=file_url,
        type=request.exam_type,
        metadata={
            **request.metadata,
            "file_size": file_obj['Size'],
            "last_modified": file_obj['LastModified'].isoformat()
        }
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="file_uploaded",
        entity="exam",
        entity_id=exam.id,
        details={
            "file_type": request.exam_type,
            "file_size": file_obj['Size'],
            "record_id": str(request.record_id) if request.record_id else None
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return FileResponse.from_orm(exam)


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate presigned URL for file download."""
    # Get exam record
    result = await db.execute(
        select(Exam).where(
            Exam.id == file_id,
            Exam.clinic_id == current_user.clinic_id
        )
    )
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Extract S3 key from file URL
    s3_key = exam.file_url.replace(f"{settings.s3_endpoint}/{settings.s3_bucket}/", "")
    
    try:
        # Generate presigned URL for download
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.s3_bucket,
                'Key': s3_key
            },
            ExpiresIn=3600  # 1 hour
        )
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="file_downloaded",
            entity="exam",
            entity_id=exam.id,
            details={"file_type": exam.type}
        )
        db.add(audit_log)
        await db.commit()
        
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": presigned_url}
        )
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file_info(
    file_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get file information."""
    result = await db.execute(
        select(Exam).where(
            Exam.id == file_id,
            Exam.clinic_id == current_user.clinic_id
        )
    )
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse.from_orm(exam)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete file from storage and database."""
    # Get exam record
    result = await db.execute(
        select(Exam).where(
            Exam.id == file_id,
            Exam.clinic_id == current_user.clinic_id
        )
    )
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Extract S3 key from file URL
    s3_key = exam.file_url.replace(f"{settings.s3_endpoint}/{settings.s3_bucket}/", "")
    
    try:
        # Delete from S3
        s3_client.delete_object(
            Bucket=settings.s3_bucket,
            Key=s3_key
        )
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="file_deleted",
            entity="exam",
            entity_id=exam.id,
            details={"file_type": exam.type}
        )
        db.add(audit_log)
        
        # Delete from database
        await db.delete(exam)
        await db.commit()
        
        return {"message": "File deleted successfully"}
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
