"""
Unified Notification Service
Supports Email (SendGrid, AWS SES) and SMS (Twilio, AWS SNS)
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================================
# BASE NOTIFICATION PROVIDER INTERFACE
# ============================================================================

class NotificationProvider(ABC):
    """Abstract base class for notification providers"""
    
    @abstractmethod
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send a notification"""
        pass


# ============================================================================
# EMAIL PROVIDERS
# ============================================================================

class SendGridEmailProvider(NotificationProvider):
    """SendGrid email provider"""
    
    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email
        self.enabled = bool(api_key)
        
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send email via SendGrid"""
        if not self.enabled:
            logger.warning("SendGrid not configured, email not sent")
            return {"success": False, "error": "SendGrid API key not configured"}
        
        try:
            # Import SendGrid library
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
            except ImportError:
                logger.error("sendgrid library not installed. Install with: pip install sendgrid")
                return {"success": False, "error": "sendgrid library not installed"}
            
            # Create email message
            html_content = kwargs.get("html_content", message)
            
            email = Mail(
                from_email=self.from_email,
                to_emails=recipient,
                subject=subject,
                html_content=html_content
            )
            
            # Send email
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(email)
            
            logger.info(f"Email sent successfully via SendGrid to {recipient}")
            return {
                "success": True,
                "provider": "sendgrid",
                "status_code": response.status_code,
                "message_id": response.headers.get("X-Message-Id")
            }
            
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {str(e)}")
            return {"success": False, "error": str(e)}


class AWSEmailProvider(NotificationProvider):
    """AWS SES email provider"""
    
    def __init__(self, region: str, from_email: str):
        self.region = region
        self.from_email = from_email
        self.enabled = bool(region)
        
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send email via AWS SES"""
        if not self.enabled:
            logger.warning("AWS SES not configured, email not sent")
            return {"success": False, "error": "AWS SES not configured"}
        
        try:
            # Import boto3
            try:
                import boto3
                from botocore.exceptions import ClientError
            except ImportError:
                logger.error("boto3 library not installed. Install with: pip install boto3")
                return {"success": False, "error": "boto3 library not installed"}
            
            # Create SES client
            ses_client = boto3.client('ses', region_name=self.region)
            
            # Send email
            html_content = kwargs.get("html_content", f"<html><body>{message}</body></html>")
            
            response = ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_content},
                        'Text': {'Data': message}
                    }
                }
            )
            
            logger.info(f"Email sent successfully via AWS SES to {recipient}")
            return {
                "success": True,
                "provider": "aws_ses",
                "message_id": response['MessageId']
            }
            
        except Exception as e:
            logger.error(f"Failed to send email via AWS SES: {str(e)}")
            return {"success": False, "error": str(e)}


# ============================================================================
# SMS PROVIDERS
# ============================================================================

class TwilioSMSProvider(NotificationProvider):
    """Twilio SMS provider"""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.enabled = bool(account_sid and auth_token)
        
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        if not self.enabled:
            logger.warning("Twilio not configured, SMS not sent")
            return {"success": False, "error": "Twilio credentials not configured"}
        
        try:
            # Import Twilio library
            try:
                from twilio.rest import Client
            except ImportError:
                logger.error("twilio library not installed. Install with: pip install twilio")
                return {"success": False, "error": "twilio library not installed"}
            
            # Create Twilio client
            client = Client(self.account_sid, self.auth_token)
            
            # Send SMS
            twilio_message = client.messages.create(
                body=message,
                from_=self.from_number,
                to=recipient
            )
            
            logger.info(f"SMS sent successfully via Twilio to {recipient}")
            return {
                "success": True,
                "provider": "twilio",
                "message_id": twilio_message.sid,
                "status": twilio_message.status
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio: {str(e)}")
            return {"success": False, "error": str(e)}


class AWSSMSProvider(NotificationProvider):
    """AWS SNS SMS provider"""
    
    def __init__(self, region: str):
        self.region = region
        self.enabled = bool(region)
        
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send SMS via AWS SNS"""
        if not self.enabled:
            logger.warning("AWS SNS not configured, SMS not sent")
            return {"success": False, "error": "AWS SNS not configured"}
        
        try:
            # Import boto3
            try:
                import boto3
            except ImportError:
                logger.error("boto3 library not installed. Install with: pip install boto3")
                return {"success": False, "error": "boto3 library not installed"}
            
            # Create SNS client
            sns_client = boto3.client('sns', region_name=self.region)
            
            # Send SMS
            response = sns_client.publish(
                PhoneNumber=recipient,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': 'Prontivus'
                    },
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            logger.info(f"SMS sent successfully via AWS SNS to {recipient}")
            return {
                "success": True,
                "provider": "aws_sns",
                "message_id": response['MessageId']
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS via AWS SNS: {str(e)}")
            return {"success": False, "error": str(e)}


# ============================================================================
# MOCK PROVIDER (FOR TESTING)
# ============================================================================

class MockNotificationProvider(NotificationProvider):
    """Mock notification provider for testing (logs only)"""
    
    async def send(self, recipient: str, subject: str, message: str, **kwargs) -> Dict[str, Any]:
        """Mock send - just logs the notification"""
        logger.info(f"[MOCK] Notification to {recipient}: {subject} - {message[:50]}...")
        return {
            "success": True,
            "provider": "mock",
            "message_id": f"mock-{datetime.now().timestamp()}"
        }


# ============================================================================
# UNIFIED NOTIFICATION SERVICE
# ============================================================================

class NotificationService:
    """
    Unified notification service that manages multiple providers.
    
    Usage:
        service = NotificationService.from_env()
        await service.send_email("user@example.com", "Hello", "Welcome!")
        await service.send_sms("+5511999999999", "Reminder", "Your appointment is tomorrow")
    """
    
    def __init__(
        self,
        email_provider: Optional[NotificationProvider] = None,
        sms_provider: Optional[NotificationProvider] = None
    ):
        self.email_provider = email_provider or MockNotificationProvider()
        self.sms_provider = sms_provider or MockNotificationProvider()
    
    @classmethod
    def from_env(cls):
        """Create NotificationService from environment variables"""
        
        # Email provider selection
        email_provider_type = os.getenv("EMAIL_PROVIDER", "mock")  # sendgrid, aws_ses, mock
        
        if email_provider_type == "sendgrid":
            email_provider = SendGridEmailProvider(
                api_key=os.getenv("SENDGRID_API_KEY", ""),
                from_email=os.getenv("EMAIL_FROM", "noreply@prontivus.com")
            )
        elif email_provider_type == "aws_ses":
            email_provider = AWSEmailProvider(
                region=os.getenv("AWS_REGION", "us-east-1"),
                from_email=os.getenv("EMAIL_FROM", "noreply@prontivus.com")
            )
        else:
            email_provider = MockNotificationProvider()
        
        # SMS provider selection
        sms_provider_type = os.getenv("SMS_PROVIDER", "mock")  # twilio, aws_sns, mock
        
        if sms_provider_type == "twilio":
            sms_provider = TwilioSMSProvider(
                account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                from_number=os.getenv("TWILIO_FROM_NUMBER", "")
            )
        elif sms_provider_type == "aws_sns":
            sms_provider = AWSSMSProvider(
                region=os.getenv("AWS_REGION", "us-east-1")
            )
        else:
            sms_provider = MockNotificationProvider()
        
        return cls(email_provider=email_provider, sms_provider=sms_provider)
    
    async def send_email(
        self,
        to: str,
        subject: str,
        message: str,
        html_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send email notification"""
        return await self.email_provider.send(
            recipient=to,
            subject=subject,
            message=message,
            html_content=html_content
        )
    
    async def send_sms(
        self,
        to: str,
        message: str,
        subject: str = ""
    ) -> Dict[str, Any]:
        """Send SMS notification"""
        return await self.sms_provider.send(
            recipient=to,
            subject=subject,
            message=message
        )
    
    async def send_appointment_reminder(
        self,
        patient_email: Optional[str],
        patient_phone: Optional[str],
        patient_name: str,
        doctor_name: str,
        appointment_datetime: datetime,
        clinic_name: str
    ) -> Dict[str, Any]:
        """Send appointment reminder via email and/or SMS"""
        
        # Format datetime in Brazilian format
        formatted_date = appointment_datetime.strftime("%d/%m/%Y")
        formatted_time = appointment_datetime.strftime("%H:%M")
        
        results = {"email": None, "sms": None}
        
        # Email reminder
        if patient_email:
            subject = f"Lembrete: Consulta com {doctor_name} amanhã"
            message = f"""
            Olá {patient_name},
            
            Este é um lembrete de sua consulta marcada para amanhã:
            
            📅 Data: {formatted_date}
            🕐 Horário: {formatted_time}
            👨‍⚕️ Médico: {doctor_name}
            🏥 Local: {clinic_name}
            
            Por favor, chegue com 15 minutos de antecedência.
            
            Atenciosamente,
            Equipe {clinic_name}
            """
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2>Lembrete de Consulta</h2>
                <p>Olá {patient_name},</p>
                <p>Este é um lembrete de sua consulta marcada para <strong>amanhã</strong>:</p>
                <ul>
                    <li><strong>📅 Data:</strong> {formatted_date}</li>
                    <li><strong>🕐 Horário:</strong> {formatted_time}</li>
                    <li><strong>👨‍⚕️ Médico:</strong> {doctor_name}</li>
                    <li><strong>🏥 Local:</strong> {clinic_name}</li>
                </ul>
                <p>Por favor, chegue com 15 minutos de antecedência.</p>
                <p>Atenciosamente,<br><strong>Equipe {clinic_name}</strong></p>
            </body>
            </html>
            """
            
            results["email"] = await self.send_email(
                to=patient_email,
                subject=subject,
                message=message,
                html_content=html_content
            )
        
        # SMS reminder
        if patient_phone:
            sms_message = f"Lembrete: Consulta com Dr(a) {doctor_name} amanhã às {formatted_time}. Local: {clinic_name}. Por favor, chegue 15min antes."
            
            results["sms"] = await self.send_sms(
                to=patient_phone,
                message=sms_message
            )
        
        return results
    
    async def send_appointment_request_notification(
        self,
        patient_email: Optional[str],
        patient_phone: Optional[str],
        patient_name: str,
        action: str,  # "approved" or "rejected"
        appointment_datetime: Optional[datetime] = None,
        doctor_name: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        clinic_name: str = "Clínica"
    ) -> Dict[str, Any]:
        """Send notification about appointment request approval/rejection"""
        
        results = {"email": None, "sms": None}
        
        if action == "approved" and appointment_datetime and doctor_name:
            formatted_date = appointment_datetime.strftime("%d/%m/%Y")
            formatted_time = appointment_datetime.strftime("%H:%M")
            
            # Email
            if patient_email:
                subject = "Solicitação de Consulta Aprovada ✅"
                message = f"""
                Olá {patient_name},
                
                Sua solicitação de consulta foi APROVADA!
                
                📅 Data: {formatted_date}
                🕐 Horário: {formatted_time}
                👨‍⚕️ Médico: {doctor_name}
                🏥 Local: {clinic_name}
                
                Por favor, chegue com 15 minutos de antecedência.
                
                Atenciosamente,
                Equipe {clinic_name}
                """
                
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #10b981;">✅ Solicitação de Consulta Aprovada</h2>
                    <p>Olá {patient_name},</p>
                    <p>Sua solicitação de consulta foi <strong style="color: #10b981;">APROVADA</strong>!</p>
                    <ul>
                        <li><strong>📅 Data:</strong> {formatted_date}</li>
                        <li><strong>🕐 Horário:</strong> {formatted_time}</li>
                        <li><strong>👨‍⚕️ Médico:</strong> {doctor_name}</li>
                        <li><strong>🏥 Local:</strong> {clinic_name}</li>
                    </ul>
                    <p>Por favor, chegue com 15 minutos de antecedência.</p>
                    <p>Atenciosamente,<br><strong>Equipe {clinic_name}</strong></p>
                </body>
                </html>
                """
                
                results["email"] = await self.send_email(
                    to=patient_email,
                    subject=subject,
                    message=message,
                    html_content=html_content
                )
            
            # SMS
            if patient_phone:
                sms_message = f"✅ Consulta aprovada! {formatted_date} às {formatted_time} com Dr(a) {doctor_name}. Local: {clinic_name}"
                results["sms"] = await self.send_sms(to=patient_phone, message=sms_message)
        
        elif action == "rejected" and rejection_reason:
            # Email
            if patient_email:
                subject = "Solicitação de Consulta Não Aprovada"
                message = f"""
                Olá {patient_name},
                
                Infelizmente, sua solicitação de consulta não pôde ser aprovada.
                
                Motivo: {rejection_reason}
                
                Por favor, entre em contato conosco para reagendar.
                
                Atenciosamente,
                Equipe {clinic_name}
                """
                
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #ef4444;">Solicitação de Consulta Não Aprovada</h2>
                    <p>Olá {patient_name},</p>
                    <p>Infelizmente, sua solicitação de consulta não pôde ser aprovada.</p>
                    <p><strong>Motivo:</strong> {rejection_reason}</p>
                    <p>Por favor, entre em contato conosco para reagendar.</p>
                    <p>Atenciosamente,<br><strong>Equipe {clinic_name}</strong></p>
                </body>
                </html>
                """
                
                results["email"] = await self.send_email(
                    to=patient_email,
                    subject=subject,
                    message=message,
                    html_content=html_content
                )
            
            # SMS
            if patient_phone:
                sms_message = f"Sua solicitação de consulta não foi aprovada. Motivo: {rejection_reason}. Contate {clinic_name}."
                results["sms"] = await self.send_sms(to=patient_phone, message=sms_message)
        
        return results


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create global notification service instance
notification_service = NotificationService.from_env()

