"""
Medical Record File Attachments API
Allows uploading exam results, images, PDFs to medical records.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import os
import base64

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/medical_records-files", tags=["Medical Records - Files"])


class FileResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
    uploaded_by: str
    url: str | None = None

    class Config:
        from_attributes = True


class ListFilesResponse(BaseModel):
    files: List[FileResponse]
    total: int


@router.post("/{record_id}/files", response_model=FileResponse)
async def upload_file_to_record(
    record_id: str,
    file: UploadFile = FastAPIFile(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """
    Upload a file attachment to a medical record.
    
    Supported file types:
    - Images: JPG, PNG, GIF, BMP
    - Documents: PDF
    - Medical: DICOM (DCM)
    
    **Max file size: 10MB**
    """
    from app.models.database import MedicalRecord, File as FileModel
    
    # Check if record exists
    stmt = select(MedicalRecord).where(MedicalRecord.id == uuid.UUID(record_id))
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    
    # Validate file type
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.dcm'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({file_size} bytes). Max size: {max_size} bytes (10MB)"
        )
    
    # Determine file type
    file_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.pdf': 'application/pdf',
        '.dcm': 'application/dicom',
    }
    file_type = file_type_map.get(file_ext, 'application/octet-stream')
    
    try:
        # Store file in database (simplified for demo)
        # In production, use S3/MinIO or filesystem
        file_record = FileModel(
            id=uuid.uuid4(),
            clinic_id=record.clinic_id,
            uploaded_by=current_user.id,
            filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            file_path=f"medical_records/{record_id}/{file.filename}",  # Virtual path
            file_url=None,  # Will be generated on demand
            description=description,
            entity_type="medical_record",
            entity_id=record.id,
            file_metadata={"record_id": str(record_id)},
            status="uploaded",
            created_at=datetime.now(),
        )
        
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
        
        return FileResponse(
            id=str(file_record.id),
            filename=file_record.filename,
            file_type=file_record.file_type,
            file_size=file_record.file_size,
            uploaded_at=file_record.created_at,
            uploaded_by=current_user.name,
            url=f"/api/v1/files/{file_record.id}/download"
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/{record_id}/files", response_model=ListFilesResponse)
async def list_record_files(
    record_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """List all files attached to a medical record."""
    from app.models.database import File as FileModel, User
    
    # Get files for this record
    stmt = select(FileModel, User.name).join(
        User, FileModel.uploaded_by == User.id
    ).where(
        FileModel.entity_type == "medical_record",
        FileModel.entity_id == uuid.UUID(record_id)
    ).order_by(FileModel.created_at.desc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    files = [
        FileResponse(
            id=str(file.id),
            filename=file.filename,
            file_type=file.file_type,
            file_size=file.file_size,
            uploaded_at=file.created_at,
            uploaded_by=uploader_name,
            url=f"/api/v1/files/{file.id}/download"
        )
        for file, uploader_name in rows
    ]
    
    return ListFilesResponse(
        files=files,
        total=len(files)
    )


@router.delete("/{record_id}/files/{file_id}")
async def delete_file_from_record(
    record_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """Delete a file attachment from a medical record."""
    from app.models.database import File as FileModel
    
    # Get the file
    stmt = select(FileModel).where(
        FileModel.id == uuid.UUID(file_id),
        FileModel.entity_id == uuid.UUID(record_id)
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions (only uploader, doctor, or admin can delete)
    user_role = getattr(current_user, "role", "").lower()
    is_uploader = file.uploaded_by == current_user.id
    
    if not (is_uploader or user_role in ["doctor", "admin"]):
        raise HTTPException(
            status_code=403,
            detail="Only the uploader, doctors, or admins can delete files"
        )
    
    # Delete from database
    await db.delete(file)
    await db.commit()
    
    return {"success": True, "message": "File deleted successfully"}

