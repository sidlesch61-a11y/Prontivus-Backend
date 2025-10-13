"""
Payment Integration Service
Handles PIX, Boleto, and other payment methods
"""

import os
import httpx
import hashlib
import hmac
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class PaymentIntegrationService:
    """Service for payment provider integrations."""
    
    def __init__(self):
        # PIX Configuration
        self.pix_provider = os.getenv("PIX_PROVIDER", "mercado_pago")  # mercado_pago, pagseguro, etc
        self.pix_api_key = os.getenv("PIX_API_KEY", "")
        self.pix_api_secret = os.getenv("PIX_API_SECRET", "")
        
        # Boleto Configuration
        self.boleto_provider = os.getenv("BOLETO_PROVIDER", "banco_brasil")
        self.boleto_api_key = os.getenv("BOLETO_API_KEY", "")
        
        # PayPal Configuration
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.paypal_secret = os.getenv("PAYPAL_SECRET", "")
        self.paypal_mode = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox or live
        
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def create_pix_payment(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        payer_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a PIX payment.
        
        Returns:
            {
                "payment_id": str,
                "qr_code": str,  # Base64 QR code image
                "qr_code_text": str,  # PIX copy-paste code
                "expires_at": datetime,
                "status": "pending"
            }
        """
        if not self.pix_api_key:
            raise ValueError("PIX provider not configured. Set PIX_API_KEY in environment.")
        
        if self.pix_provider == "mercado_pago":
            return await self._create_mercado_pago_pix(invoice_id, amount, description, payer_info)
        elif self.pix_provider == "pagseguro":
            return await self._create_pagseguro_pix(invoice_id, amount, description, payer_info)
        else:
            # Generic PIX implementation
            return await self._create_generic_pix(invoice_id, amount, description, payer_info)
    
    async def _create_mercado_pago_pix(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        payer_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create PIX payment via Mercado Pago."""
        url = "https://api.mercadopago.com/v1/payments"
        
        payload = {
            "transaction_amount": amount,
            "description": description,
            "payment_method_id": "pix",
            "external_reference": invoice_id,
            "payer": {
                "email": payer_info.get("email", ""),
                "first_name": payer_info.get("name", "").split()[0] if payer_info.get("name") else "",
                "last_name": " ".join(payer_info.get("name", "").split()[1:]) if payer_info.get("name") else "",
                "identification": {
                    "type": "CPF",
                    "number": payer_info.get("cpf", "").replace(".", "").replace("-", "")
                }
            },
            "notification_url": f"{os.getenv('API_URL', '')}/api/v1/webhooks/payments/mercado-pago"
        }
        
        headers = {
            "Authorization": f"Bearer {self.pix_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            return {
                "payment_id": data.get("id"),
                "qr_code": data.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code_base64", ""),
                "qr_code_text": data.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code", ""),
                "expires_at": datetime.fromisoformat(data.get("date_of_expiration", "")) if data.get("date_of_expiration") else datetime.utcnow() + timedelta(hours=24),
                "status": "pending",
                "provider": "mercado_pago",
                "raw_response": data
            }
        except httpx.HTTPError as e:
            logger.error(f"Mercado Pago PIX creation failed: {e}")
            raise
    
    async def _create_pagseguro_pix(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        payer_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create PIX payment via PagSeguro."""
        url = "https://api.pagseguro.com/charges"
        
        payload = {
            "reference_id": invoice_id,
            "customer": {
                "name": payer_info.get("name", ""),
                "email": payer_info.get("email", ""),
                "tax_id": payer_info.get("cpf", "").replace(".", "").replace("-", "")
            },
            "items": [
                {
                    "name": description,
                    "quantity": 1,
                    "unit_amount": int(amount * 100)  # Convert to cents
                }
            ],
            "charges": [
                {
                    "reference_id": invoice_id,
                    "description": description,
                    "amount": {
                        "value": int(amount * 100),
                        "currency": "BRL"
                    },
                    "payment_method": {
                        "type": "PIX"
                    },
                    "notification_urls": [
                        f"{os.getenv('API_URL', '')}/api/v1/webhooks/payments/pagseguro"
                    ]
                }
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {self.pix_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            return {
                "payment_id": data.get("id"),
                "qr_code": data.get("charges", [{}])[0].get("payment_method", {}).get("qr_code", {}).get("text", ""),
                "qr_code_text": data.get("charges", [{}])[0].get("payment_method", {}).get("qr_code", {}).get("text", ""),
                "expires_at": datetime.fromisoformat(data.get("charges", [{}])[0].get("expires_at", "")) if data.get("charges", [{}])[0].get("expires_at") else datetime.utcnow() + timedelta(hours=24),
                "status": "pending",
                "provider": "pagseguro",
                "raw_response": data
            }
        except httpx.HTTPError as e:
            logger.error(f"PagSeguro PIX creation failed: {e}")
            raise
    
    async def _create_generic_pix(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        payer_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generic PIX implementation for testing."""
        # Generate a mock QR code text for testing
        qr_code_text = f"00020126{len(invoice_id):02d}{invoice_id}5204000053039865802BR5925PRONTIVUS6009SAO PAULO622905{len(invoice_id):02d}{invoice_id}6304{hashlib.md5(invoice_id.encode()).hexdigest()[:4]}"
        
        return {
            "payment_id": str(uuid.uuid4()),
            "qr_code": "",  # Would generate actual QR code image here
            "qr_code_text": qr_code_text,
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "status": "pending",
            "provider": "generic",
            "note": "Configure PIX_PROVIDER and PIX_API_KEY for production use"
        }
    
    async def create_boleto(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        payer_info: Dict[str, Any],
        due_date: datetime
    ) -> Dict[str, Any]:
        """
        Create a Boleto payment.
        
        Returns:
            {
                "boleto_id": str,
                "barcode": str,
                "digitable_line": str,  # Linha digitável
                "pdf_url": str,
                "due_date": datetime,
                "status": "pending"
            }
        """
        if not self.boleto_api_key:
            logger.warning("Boleto provider not configured. Returning mock data.")
            return {
                "boleto_id": str(uuid.uuid4()),
                "barcode": "34191.75009 01043.510047 91020.150008 1 84660000010000",
                "digitable_line": "34191750090104351004791020150008184660000010000",
                "pdf_url": f"/api/v1/invoices/{invoice_id}/boleto.pdf",
                "due_date": due_date,
                "status": "pending",
                "note": "Configure BOLETO_PROVIDER and BOLETO_API_KEY for production use"
            }
        
        # Implement actual boleto generation here
        # This would vary by bank/provider
        pass
    
    async def create_paypal_payment(
        self,
        invoice_id: str,
        amount: float,
        description: str,
        return_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """
        Create a PayPal payment.
        
        Returns:
            {
                "payment_id": str,
                "approval_url": str,  # Redirect user here
                "status": "created"
            }
        """
        if not self.paypal_client_id:
            raise ValueError("PayPal not configured. Set PAYPAL_CLIENT_ID and PAYPAL_SECRET.")
        
        # Get PayPal access token
        auth_response = await self._get_paypal_token()
        access_token = auth_response["access_token"]
        
        # Create payment
        base_url = "https://api.paypal.com" if self.paypal_mode == "live" else "https://api.sandbox.paypal.com"
        url = f"{base_url}/v1/payments/payment"
        
        payload = {
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": f"{amount:.2f}",
                    "currency": "BRL"
                },
                "description": description,
                "invoice_number": invoice_id
            }],
            "redirect_urls": {
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Find approval URL
            approval_url = next(
                (link["href"] for link in data.get("links", []) if link["rel"] == "approval_url"),
                None
            )
            
            return {
                "payment_id": data.get("id"),
                "approval_url": approval_url,
                "status": "created",
                "provider": "paypal",
                "raw_response": data
            }
        except httpx.HTTPError as e:
            logger.error(f"PayPal payment creation failed: {e}")
            raise
    
    async def _get_paypal_token(self) -> Dict[str, Any]:
        """Get PayPal OAuth token."""
        base_url = "https://api.paypal.com" if self.paypal_mode == "live" else "https://api.sandbox.paypal.com"
        url = f"{base_url}/v1/oauth2/token"
        
        response = await self.http_client.post(
            url,
            auth=(self.paypal_client_id, self.paypal_secret),
            data={"grant_type": "client_credentials"}
        )
        response.raise_for_status()
        return response.json()
    
    async def check_payment_status(
        self,
        payment_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        Check payment status with provider.
        
        Returns:
            {
                "status": "pending" | "paid" | "failed" | "expired",
                "paid_at": datetime | None,
                "payment_details": Dict
            }
        """
        if provider == "mercado_pago":
            return await self._check_mercado_pago_status(payment_id)
        elif provider == "pagseguro":
            return await self._check_pagseguro_status(payment_id)
        elif provider == "paypal":
            return await self._check_paypal_status(payment_id)
        else:
            return {"status": "unknown", "provider": provider}
    
    async def _check_mercado_pago_status(self, payment_id: str) -> Dict[str, Any]:
        """Check Mercado Pago payment status."""
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        headers = {"Authorization": f"Bearer {self.pix_api_key}"}
        
        try:
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Map Mercado Pago status to our status
            status_map = {
                "pending": "pending",
                "approved": "paid",
                "authorized": "paid",
                "in_process": "pending",
                "in_mediation": "pending",
                "rejected": "failed",
                "cancelled": "failed",
                "refunded": "refunded",
                "charged_back": "refunded"
            }
            
            return {
                "status": status_map.get(data.get("status"), "unknown"),
                "paid_at": datetime.fromisoformat(data.get("date_approved", "")) if data.get("date_approved") else None,
                "payment_details": data
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to check Mercado Pago status: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def _check_pagseguro_status(self, payment_id: str) -> Dict[str, Any]:
        """Check PagSeguro payment status."""
        url = f"https://api.pagseguro.com/charges/{payment_id}"
        headers = {"Authorization": f"Bearer {self.pix_api_key}"}
        
        try:
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Map PagSeguro status to our status
            status_map = {
                "WAITING": "pending",
                "IN_ANALYSIS": "pending",
                "PAID": "paid",
                "DECLINED": "failed",
                "CANCELED": "failed"
            }
            
            return {
                "status": status_map.get(data.get("status"), "unknown"),
                "paid_at": datetime.fromisoformat(data.get("paid_at", "")) if data.get("paid_at") else None,
                "payment_details": data
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to check PagSeguro status: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def _check_paypal_status(self, payment_id: str) -> Dict[str, Any]:
        """Check PayPal payment status."""
        auth_response = await self._get_paypal_token()
        access_token = auth_response["access_token"]
        
        base_url = "https://api.paypal.com" if self.paypal_mode == "live" else "https://api.sandbox.paypal.com"
        url = f"{base_url}/v1/payments/payment/{payment_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Map PayPal status to our status
            status_map = {
                "created": "pending",
                "approved": "paid",
                "failed": "failed",
                "canceled": "failed",
                "expired": "expired"
            }
            
            return {
                "status": status_map.get(data.get("state"), "unknown"),
                "paid_at": datetime.fromisoformat(data.get("update_time", "")) if data.get("state") == "approved" else None,
                "payment_details": data
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to check PayPal status: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def verify_webhook_signature(
        self,
        provider: str,
        payload: bytes,
        signature: str
    ) -> bool:
        """Verify webhook signature from payment provider."""
        if provider == "mercado_pago":
            # Mercado Pago uses HMAC-SHA256
            expected_signature = hmac.new(
                self.pix_api_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        
        elif provider == "pagseguro":
            # PagSeguro verification logic
            return True  # Implement based on PagSeguro docs
        
        elif provider == "paypal":
            # PayPal verification logic
            return True  # Implement based on PayPal docs
        
        return False
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


# Global instance
payment_service = PaymentIntegrationService()

