"""
TISS service for business logic and provider management.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import uuid

import httpx

from ..models.tiss import (
    TISSProvider, TISSJob, TISSLog, TISSEthicalLock,
    TISSTestConnectionResponse, TISSJobStatus, TISSLogLevel,
    TISSEthicalLockType
)
from ..core.security import security

logger = logging.getLogger(__name__)

class TISSEthicalLockCheck:
    """Result of ethical lock check."""
    
    def __init__(self, has_lock: bool = False, lock_type: Optional[TISSEthicalLockType] = None, reason: str = ""):
        self.has_lock = has_lock
        self.lock_type = lock_type
        self.reason = reason

class TISSService:
    """Service for TISS operations and business logic."""
    
    def __init__(self):
        pass
    
    async def test_connection(
        self, 
        endpoint_url: str, 
        username: str, 
        password: str, 
        timeout: int = 30
    ) -> TISSTestConnectionResponse:
        """Test TISS provider connection."""
        
        start_time = datetime.utcnow()
        
        try:
            # Create test payload
            test_payload = {
                "teste_conexao": True,
                "usuario": username,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Make test request
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint_url,
                    json=test_payload,
                    auth=(username, password),
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Prontivus-TISS/1.0"
                    }
                )
                
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                if response.status_code == 200:
                    return TISSTestConnectionResponse(
                        success=True,
                        message="Connection test successful",
                        response_time_ms=int(response_time),
                        status_code=response.status_code,
                        response_data=response.json() if response.content else None
                    )
                else:
                    return TISSTestConnectionResponse(
                        success=False,
                        message=f"Connection test failed: HTTP {response.status_code}",
                        response_time_ms=int(response_time),
                        status_code=response.status_code,
                        response_data=response.text if response.content else None
                    )
                    
        except httpx.TimeoutException:
            return TISSTestConnectionResponse(
                success=False,
                message="Connection test timed out",
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
        except httpx.ConnectError:
            return TISSTestConnectionResponse(
                success=False,
                message="Connection test failed: Unable to connect to endpoint"
            )
        except Exception as e:
            return TISSTestConnectionResponse(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )
    
    async def check_ethical_locks(
        self,
        clinic_id: uuid.UUID,
        invoice_id: Optional[uuid.UUID] = None,
        procedure_code: Optional[str] = None,
        job_type: Optional[str] = None
    ) -> TISSEthicalLockCheck:
        """Check for ethical locks before creating a job."""
        
        # This would be implemented with actual database queries
        # For now, we'll simulate the checks
        
        if invoice_id:
            # Check for duplicate invoice
            duplicate_check = await self._check_duplicate_invoice(clinic_id, invoice_id)
            if duplicate_check:
                return TISSEthicalLockCheck(
                    has_lock=True,
                    lock_type=TISSEthicalLockType.DUPLICATE_INVOICE,
                    reason=f"Duplicate invoice submission detected: {invoice_id}"
                )
        
        if procedure_code:
            # Check for CID collision
            cid_collision = await self._check_cid_collision(clinic_id, procedure_code)
            if cid_collision:
                return TISSEthicalLockCheck(
                    has_lock=True,
                    lock_type=TISSEthicalLockType.CID_COLLISION,
                    reason=f"CID collision detected for procedure: {procedure_code}"
                )
        
        # Check for procedure collision within date range
        if procedure_code and job_type == "procedure":
            procedure_collision = await self._check_procedure_collision(clinic_id, procedure_code)
            if procedure_collision:
                return TISSEthicalLockCheck(
                    has_lock=True,
                    lock_type=TISSEthicalLockType.PROCEDURE_COLLISION,
                    reason=f"Procedure collision detected: {procedure_code}"
                )
        
        return TISSEthicalLockCheck(has_lock=False)
    
    async def _check_duplicate_invoice(
        self, 
        clinic_id: uuid.UUID, 
        invoice_id: uuid.UUID
    ) -> bool:
        """Check for duplicate invoice submission."""
        # This would query the database for existing jobs with the same invoice_id
        # where status != 'rejected'
        # For now, return False (no duplicate)
        return False
    
    async def _check_cid_collision(
        self, 
        clinic_id: uuid.UUID, 
        procedure_code: str
    ) -> bool:
        """Check for CID collision (same patient, same procedure)."""
        # This would check if the same patient has a recent identical procedure
        # with the same TUSS code within a date range
        # For now, return False (no collision)
        return False
    
    async def _check_procedure_collision(
        self, 
        clinic_id: uuid.UUID, 
        procedure_code: str
    ) -> bool:
        """Check for procedure collision within date range."""
        # This would check for procedure collisions within a specific date range
        # For now, return False (no collision)
        return False
    
    async def send_tiss_payload(
        self,
        provider: TISSProvider,
        job: TISSJob,
        payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Send TISS payload to provider."""
        
        try:
            # Decrypt password
            password = security.decrypt_field(provider.password_encrypted)
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Prontivus-TISS/1.0",
                "X-Clinic-ID": str(job.clinic_id),
                "X-Job-ID": str(job.id)
            }
            
            # Add certificate if available
            if provider.certificate_path:
                headers["X-Certificate-Path"] = provider.certificate_path
            
            # Make request
            async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
                response = await client.post(
                    provider.endpoint_url,
                    json=payload,
                    auth=(provider.username, password),
                    headers=headers
                )
                
                if response.status_code in [200, 201, 202]:
                    # Success
                    response_data = response.json() if response.content else None
                    return True, None, response_data
                else:
                    # Error
                    error_message = f"HTTP {response.status_code}: {response.text}"
                    return False, error_message, None
                    
        except httpx.TimeoutException:
            return False, "Request timed out", None
        except httpx.ConnectError:
            return False, "Unable to connect to provider endpoint", None
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", None
    
    def calculate_next_retry(self, attempt: int, base_delay: int = 60) -> datetime:
        """Calculate next retry time with exponential backoff."""
        import math
        delay_seconds = base_delay * (2 ** attempt)
        return datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    def should_retry(self, attempt: int, max_attempts: int) -> bool:
        """Check if job should be retried."""
        return attempt < max_attempts
    
    def create_tiss_payload(
        self,
        job: TISSJob,
        invoice_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create TISS payload from job data."""
        
        # Base payload structure
        payload = {
            "cabecalho": {
                "identificacao_transacao": {
                    "tipo_transacao": "ENVIO_LOTE_GUIAS",
                    "sequencial_transacao": str(job.id),
                    "data_registro_transacao": datetime.utcnow().strftime("%Y%m%d"),
                    "hora_registro_transacao": datetime.utcnow().strftime("%H%M%S")
                },
                "origem": {
                    "identificacao_origem": {
                        "codigo_origem": "PRONTIVUS",
                        "nome_origem": "Prontivus Medical System"
                    }
                },
                "destino": {
                    "identificacao_destino": {
                        "codigo_destino": job.provider.code if job.provider else "UNKNOWN",
                        "nome_destino": job.provider.name if job.provider else "Unknown Provider"
                    }
                }
            },
            "dados_contratado": {
                "dados_identificacao_contratado": {
                    "codigo_na_operadora": "001",
                    "nome_contratado": "Prontivus Clinic",
                    "tipo_contratado": "CLINICA"
                }
            },
            "guias_tiss": []
        }
        
        # Add job-specific data
        if job.job_type == "invoice" and invoice_data:
            payload["guias_tiss"].append({
                "tipo_guia": "CONSULTA_MEDICA",
                "dados_guia": {
                    "numero_guia_prestador": str(job.invoice_id),
                    "numero_guia_operadora": "",
                    "dados_beneficiario": invoice_data.get("patient_data", {}),
                    "dados_contratado_executante": invoice_data.get("provider_data", {}),
                    "dados_atendimento": invoice_data.get("appointment_data", {}),
                    "procedimentos_realizados": invoice_data.get("procedures", [])
                }
            })
        elif job.job_type == "sadt":
            payload["guias_tiss"].append({
                "tipo_guia": "SADT",
                "dados_guia": {
                    "numero_guia_prestador": str(job.id),
                    "procedimento_codigo": job.procedure_code,
                    "dados_procedimento": job.payload
                }
            })
        
        return payload
    
    def parse_tiss_response(
        self,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse TISS response and extract relevant information."""
        
        parsed_response = {
            "status": "unknown",
            "message": "",
            "guia_numero": None,
            "protocolo": None,
            "erros": [],
            "avisos": []
        }
        
        try:
            # Parse response structure
            if "protocolo" in response_data:
                parsed_response["protocolo"] = response_data["protocolo"]
            
            if "situacao_guia" in response_data:
                situacao = response_data["situacao_guia"]
                parsed_response["status"] = situacao.get("situacao", "unknown")
                parsed_response["message"] = situacao.get("descricao", "")
            
            if "numero_guia_operadora" in response_data:
                parsed_response["guia_numero"] = response_data["numero_guia_operadora"]
            
            # Parse errors and warnings
            if "erros" in response_data:
                parsed_response["erros"] = response_data["erros"]
            
            if "avisos" in response_data:
                parsed_response["avisos"] = response_data["avisos"]
                
        except Exception as e:
            logger.error(f"Error parsing TISS response: {str(e)}")
            parsed_response["message"] = f"Error parsing response: {str(e)}"
        
        return parsed_response
    
    def validate_tiss_payload(self, payload: Dict[str, Any]) -> List[str]:
        """Validate TISS payload structure."""
        
        errors = []
        
        # Check required fields
        if "cabecalho" not in payload:
            errors.append("Missing required field: cabecalho")
        
        if "dados_contratado" not in payload:
            errors.append("Missing required field: dados_contratado")
        
        if "guias_tiss" not in payload:
            errors.append("Missing required field: guias_tiss")
        
        # Validate header structure
        if "cabecalho" in payload:
            cabecalho = payload["cabecalho"]
            if "identificacao_transacao" not in cabecalho:
                errors.append("Missing required field: cabecalho.identificacao_transacao")
            
            if "origem" not in cabecalho:
                errors.append("Missing required field: cabecalho.origem")
            
            if "destino" not in cabecalho:
                errors.append("Missing required field: cabecalho.destino")
        
        # Validate guias
        if "guias_tiss" in payload:
            guias = payload["guias_tiss"]
            if not isinstance(guias, list) or len(guias) == 0:
                errors.append("guias_tiss must be a non-empty list")
        
        return errors
    
    def create_audit_log(
        self,
        clinic_id: uuid.UUID,
        provider_id: Optional[uuid.UUID],
        job_id: Optional[uuid.UUID],
        level: TISSLogLevel,
        message: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        response_status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None
    ) -> TISSLog:
        """Create audit log entry."""
        
        return TISSLog(
            clinic_id=clinic_id,
            provider_id=provider_id,
            job_id=job_id,
            level=level,
            message=message,
            details=details,
            request_data=request_data,
            response_data=response_data,
            response_status_code=response_status_code,
            response_time_ms=response_time_ms,
            operation=operation
        )
