"""
Schemas for consultation finalization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConsultationFinalizeRequest(BaseModel):
    """Request schema for finalizing a consultation."""
    
    anamnesis: str = Field(..., description="Anamnese completa")
    diagnosis: str = Field(..., description="Diagnóstico principal")
    exams: Optional[List[Dict[str, Any]]] = Field(default=[], description="Lista de exames solicitados")
    prescriptions: Optional[List[Dict[str, Any]]] = Field(default=[], description="Lista de prescrições")
    observations: Optional[str] = Field(default="", description="Observações adicionais")
    finalization_notes: Optional[str] = Field(default="", description="Notas de finalização")

class ConsultationFinalizeResponse(BaseModel):
    """Response schema for consultation finalization."""
    
    success: bool
    message: str
    consultation_id: str
    history_record_id: str
    finalized_at: str
    finalized_by: str

class ConsultationHistoryItem(BaseModel):
    """Schema for consultation history timeline item."""
    
    id: str
    date: str
    title: str
    doctor_name: str
    summary: str
    diagnosis: str
    cid_code: str
    type: str
    data: Dict[str, Any]

class ConsultationHistoryResponse(BaseModel):
    """Response schema for consultation history."""
    
    success: bool
    timeline: List[ConsultationHistoryItem]
    pagination: Dict[str, Any]

class PrintDocumentRequest(BaseModel):
    """Request schema for printing documents."""
    
    output_type: str = Field(default="pdf", description="Tipo de saída: pdf ou direct_print")
    document_data: Optional[Dict[str, Any]] = Field(default=None, description="Dados específicos do documento")

class PrintConsolidatedRequest(BaseModel):
    """Request schema for consolidated document printing."""
    
    output_type: str = Field(default="pdf", description="Tipo de saída: pdf ou direct_print")
    document_types: List[str] = Field(default=[], description="Tipos de documentos a incluir")
