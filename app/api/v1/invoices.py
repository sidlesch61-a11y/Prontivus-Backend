"""
Invoices API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, cast, String

from app.core.auth import get_current_user, require_billing_read, require_billing_write, require_billing_module
from app.db.session import get_db_session
from app.models import Invoice, Patient, AuditLog
from app.schemas import InvoiceCreate, InvoiceResponse, PaginationParams, PaginatedResponse

router = APIRouter()


@router.get("/list", response_model=PaginatedResponse)
async def list_invoices_with_list(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_billing_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List invoices with filters and pagination."""
    try:
        query = select(Invoice).where(Invoice.clinic_id == current_user.clinic_id)
        
        # Apply filters
        if patient_id:
            query = query.where(Invoice.patient_id == patient_id)
        
        if status:
            query = query.where(cast(Invoice.status, String) == status)
        
        # Get total count
        count_query = select(Invoice).where(Invoice.clinic_id == current_user.clinic_id)
        if patient_id:
            count_query = count_query.where(Invoice.patient_id == patient_id)
        if status:
            count_query = count_query.where(cast(Invoice.status, String) == status)
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(Invoice.created_at.desc())
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        # Get related data
        invoice_responses = []
        for invoice in invoices:
            # Get patient name if patient_id exists
            patient_name = None
            if invoice.patient_id:
                patient_result = await db.execute(
                    select(Patient.name).where(Patient.id == invoice.patient_id)
                )
                patient_name = patient_result.scalar()
            
            invoice_data = InvoiceResponse.model_validate(invoice)
            invoice_data.patient_name = patient_name
            invoice_responses.append(invoice_data)
        
        return PaginatedResponse(
            items=invoice_responses,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        import logging
        logging.error(f"Error in list_invoices: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load invoices: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def list_invoices(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_billing_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List invoices with filters and pagination."""
    try:
        query = select(Invoice).where(Invoice.clinic_id == current_user.clinic_id)
        
        # Apply filters
        if patient_id:
            query = query.where(Invoice.patient_id == patient_id)
        
        if status:
            query = query.where(cast(Invoice.status, String) == status)
        
        # Get total count
        count_query = select(Invoice).where(Invoice.clinic_id == current_user.clinic_id)
        if patient_id:
            count_query = count_query.where(Invoice.patient_id == patient_id)
        if status:
            count_query = count_query.where(cast(Invoice.status, String) == status)
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(Invoice.created_at.desc())
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        # Get related data
        invoice_responses = []
        for invoice in invoices:
            # Get patient name if patient_id exists
            patient_name = None
            if invoice.patient_id:
                patient_result = await db.execute(
                    select(Patient.name).where(Patient.id == invoice.patient_id)
                )
                patient_name = patient_result.scalar()
            
            invoice_data = InvoiceResponse.model_validate(invoice)
            invoice_data.patient_name = patient_name
            invoice_responses.append(invoice_data)
        
        return PaginatedResponse(
            items=invoice_responses,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        import logging
        logging.error(f"Error in list_invoices: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load invoices: {str(e)}"
        )


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user = Depends(require_billing_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new invoice."""
    # Verify patient exists and belongs to clinic
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == invoice_data.patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = patient_result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Create invoice
    invoice = Invoice(
        clinic_id=current_user.clinic_id,
        **invoice_data.dict()
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="invoice_created",
        entity="invoice",
        entity_id=invoice.id,
        details={
            "patient_id": str(invoice.patient_id) if invoice.patient_id else None,
            "amount": float(invoice.amount),
            "method": invoice.method if invoice.method else None
        }
    )
    db.add(audit_log)
    await db.commit()
    
    # Get patient name for response
    patient_name = None
    if invoice.patient_id:
        patient_result = await db.execute(
            select(Patient.name).where(Patient.id == invoice.patient_id)
        )
        patient_name = patient_result.scalar()
    
    invoice_response = InvoiceResponse.model_validate(invoice)
    invoice_response.patient_name = patient_name
    
    return invoice_response


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user = Depends(require_billing_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get invoice by ID."""
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Get patient name
    patient_name = None
    if invoice.patient_id:
        patient_result = await db.execute(
            select(Patient.name).where(Patient.id == invoice.patient_id)
        )
        patient_name = patient_result.scalar()
    
    invoice_response = InvoiceResponse.model_validate(invoice)
    invoice_response.patient_name = patient_name
    
    return invoice_response


@router.post("/{invoice_id}/send-tiss")
async def send_tiss_guide(
    invoice_id: str,
    current_user = Depends(require_billing_module),
    db: AsyncSession = Depends(get_db_session)
):
    """Send invoice to TISS (triggers background job)."""
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice must be paid before sending to TISS"
        )
    
    # TODO: Trigger background job for TISS processing
    # This would typically use Celery or similar task queue
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="tiss_guide_sent",
        entity="invoice",
        entity_id=invoice.id,
        details={"invoice_amount": float(invoice.amount)}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "TISS guide processing started"}


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    update_data: dict,
    current_user = Depends(require_billing_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Update invoice."""
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Update fields
    for field, value in update_data.items():
        if hasattr(invoice, field):
            setattr(invoice, field, value)
    
    await db.commit()
    await db.refresh(invoice)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="invoice_updated",
        entity="invoice",
        entity_id=invoice.id,
        details={"updated_fields": list(update_data.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    # Get patient name
    patient_result = await db.execute(
        select(Patient.name).where(Patient.id == invoice.patient_id)
    )
    patient_name = patient_result.scalar()
    
    invoice_response = InvoiceResponse.model_validate(invoice)
    invoice_response.patient_name = patient_name
    
    return invoice_response


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    current_user = Depends(require_billing_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete invoice."""
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Create audit log before deletion
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="invoice_deleted",
        entity="invoice",
        entity_id=invoice.id,
        details={
            "patient_id": str(invoice.patient_id),
            "amount": float(invoice.amount),
            "status": invoice.status
        }
    )
    db.add(audit_log)
    
    # Delete invoice
    await db.delete(invoice)
    await db.commit()
    
    return {"message": "Invoice deleted successfully"}
