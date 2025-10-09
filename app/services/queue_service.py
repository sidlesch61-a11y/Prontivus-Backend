"""
Queue service for waiting queue business logic and management.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
from sqlmodel import Session, select, and_, func

from ..models.waiting_queue import (
    WaitingQueue, WaitingQueueLog,
    WaitingQueueStatus, WaitingQueuePriority,
    WaitingQueueManager, QueueAnalytics
)

logger = logging.getLogger(__name__)

class QueueService:
    """Service for waiting queue business logic and management."""
    
    def __init__(self):
        self.average_consultation_minutes = 20
        self.max_wait_time_minutes = 120
    
    async def calculate_queue_position(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID,
        priority: WaitingQueuePriority
    ) -> int:
        """Calculate position in queue based on priority and existing entries."""
        
        try:
            # Get current queue entries for the doctor
            current_entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            
            # Calculate position based on priority
            if priority == WaitingQueuePriority.EMERGENCY:
                # Emergency patients go to front
                return 1
            elif priority == WaitingQueuePriority.URGENT:
                # Urgent patients go after emergency but before normal
                emergency_count = len([e for e in current_entries if e.priority == WaitingQueuePriority.EMERGENCY])
                return emergency_count + 1
            elif priority == WaitingQueuePriority.VIP:
                # VIP patients go after emergency and urgent
                emergency_count = len([e for e in current_entries if e.priority == WaitingQueuePriority.EMERGENCY])
                urgent_count = len([e for e in current_entries if e.priority == WaitingQueuePriority.URGENT])
                return emergency_count + urgent_count + 1
            else:
                # Normal patients go to end
                return len(current_entries) + 1
            
        except Exception as e:
            logger.error(f"Error calculating queue position: {str(e)}")
            return 1
    
    async def get_active_queue_entries(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID
    ) -> List[WaitingQueue]:
        """Get active queue entries for a doctor."""
        
        try:
            # This would typically query the database
            # For now, return empty list as placeholder
            return []
            
        except Exception as e:
            logger.error(f"Error getting active queue entries: {str(e)}")
            return []
    
    async def recalculate_positions(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID
    ):
        """Recalculate positions for all active queue entries."""
        
        try:
            # Get all active entries ordered by priority and enqueued_at
            entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            
            # Sort by priority and enqueued_at
            priority_order = {
                WaitingQueuePriority.EMERGENCY: 1,
                WaitingQueuePriority.URGENT: 2,
                WaitingQueuePriority.VIP: 3,
                WaitingQueuePriority.NORMAL: 4
            }
            
            entries.sort(key=lambda x: (priority_order[x.priority], x.enqueued_at))
            
            # Update positions
            for i, entry in enumerate(entries, 1):
                if entry.position != i:
                    entry.position = i
                    entry.updated_at = datetime.utcnow()
                    # In real implementation, would update database
            
            logger.info(f"Recalculated positions for {len(entries)} queue entries")
            
        except Exception as e:
            logger.error(f"Error recalculating positions: {str(e)}")
    
    async def estimate_wait_time(
        self,
        position: int,
        average_consultation_minutes: Optional[int] = None
    ) -> int:
        """Estimate wait time based on position and average consultation duration."""
        
        if average_consultation_minutes is None:
            average_consultation_minutes = self.average_consultation_minutes
        
        estimated_minutes = position * average_consultation_minutes
        
        # Cap at maximum wait time
        return min(estimated_minutes, self.max_wait_time_minutes)
    
    async def calculate_call_time(self, wait_time_minutes: int) -> datetime:
        """Calculate estimated call time."""
        
        return datetime.utcnow() + timedelta(minutes=wait_time_minutes)
    
    async def get_next_patient(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID
    ) -> Optional[WaitingQueue]:
        """Get the next patient to be called."""
        
        try:
            # Get waiting patients ordered by position
            entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            waiting_entries = [e for e in entries if e.status == WaitingQueueStatus.WAITING]
            
            if not waiting_entries:
                return None
            
            # Sort by position and return first
            waiting_entries.sort(key=lambda x: x.position)
            return waiting_entries[0]
            
        except Exception as e:
            logger.error(f"Error getting next patient: {str(e)}")
            return None
    
    async def call_next_patient(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID
    ) -> Optional[WaitingQueue]:
        """Call the next patient in queue."""
        
        try:
            next_patient = await self.get_next_patient(clinic_id, doctor_id)
            
            if not next_patient:
                return None
            
            # Update status to called
            next_patient.status = WaitingQueueStatus.CALLED
            next_patient.called_at = datetime.utcnow()
            next_patient.updated_at = datetime.utcnow()
            
            # In real implementation, would update database
            
            logger.info(f"Called next patient: {next_patient.id}")
            return next_patient
            
        except Exception as e:
            logger.error(f"Error calling next patient: {str(e)}")
            return None
    
    async def start_consultation(
        self,
        queue_entry_id: uuid.UUID
    ) -> bool:
        """Start consultation for a called patient."""
        
        try:
            # Get queue entry
            queue_entry = await self.get_queue_entry(queue_entry_id)
            
            if not queue_entry:
                return False
            
            if queue_entry.status != WaitingQueueStatus.CALLED:
                logger.warning(f"Cannot start consultation for patient with status: {queue_entry.status}")
                return False
            
            # Update status
            queue_entry.status = WaitingQueueStatus.IN_CONSULTATION
            queue_entry.consultation_started_at = datetime.utcnow()
            queue_entry.updated_at = datetime.utcnow()
            
            # In real implementation, would update database
            
            logger.info(f"Started consultation for patient: {queue_entry.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting consultation: {str(e)}")
            return False
    
    async def complete_consultation(
        self,
        queue_entry_id: uuid.UUID
    ) -> bool:
        """Complete consultation for a patient."""
        
        try:
            # Get queue entry
            queue_entry = await self.get_queue_entry(queue_entry_id)
            
            if not queue_entry:
                return False
            
            if queue_entry.status != WaitingQueueStatus.IN_CONSULTATION:
                logger.warning(f"Cannot complete consultation for patient with status: {queue_entry.status}")
                return False
            
            # Update status
            queue_entry.status = WaitingQueueStatus.COMPLETED
            queue_entry.consultation_ended_at = datetime.utcnow()
            queue_entry.updated_at = datetime.utcnow()
            
            # In real implementation, would update database
            
            logger.info(f"Completed consultation for patient: {queue_entry.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing consultation: {str(e)}")
            return False
    
    async def get_queue_entry(self, queue_entry_id: uuid.UUID) -> Optional[WaitingQueue]:
        """Get a specific queue entry."""
        
        try:
            # This would typically query the database
            # For now, return None as placeholder
            return None
            
        except Exception as e:
            logger.error(f"Error getting queue entry: {str(e)}")
            return None
    
    async def get_queue_statistics(
        self,
        clinic_id: uuid.UUID,
        doctor_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Get queue statistics."""
        
        try:
            entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            
            stats = {
                "total_patients": len(entries),
                "waiting": len([e for e in entries if e.status == WaitingQueueStatus.WAITING]),
                "called": len([e for e in entries if e.status == WaitingQueueStatus.CALLED]),
                "in_consultation": len([e for e in entries if e.status == WaitingQueueStatus.IN_CONSULTATION]),
                "completed": len([e for e in entries if e.status == WaitingQueueStatus.COMPLETED]),
                "cancelled": len([e for e in entries if e.status == WaitingQueueStatus.CANCELLED]),
                "average_wait_time": 0,
                "estimated_next_call": None
            }
            
            # Calculate average wait time for completed consultations
            completed_entries = [e for e in entries if e.status == WaitingQueueStatus.COMPLETED and e.consultation_started_at]
            if completed_entries:
                wait_times = [(e.consultation_started_at - e.enqueued_at).total_seconds() / 60 for e in completed_entries]
                stats["average_wait_time"] = sum(wait_times) / len(wait_times)
            
            # Estimate next call time
            waiting_entries = [e for e in entries if e.status == WaitingQueueStatus.WAITING]
            if waiting_entries:
                next_patient = min(waiting_entries, key=lambda x: x.position)
                estimated_wait = await self.estimate_wait_time(next_patient.position)
                stats["estimated_next_call"] = (datetime.utcnow() + timedelta(minutes=estimated_wait)).isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue statistics: {str(e)}")
            return {}
    
    async def validate_queue_entry(
        self,
        appointment_id: uuid.UUID,
        patient_id: uuid.UUID,
        clinic_id: uuid.UUID
    ) -> Tuple[bool, str]:
        """Validate if a patient can be added to the queue."""
        
        try:
            # Check if patient is already in queue
            existing_entries = await self.get_active_queue_entries(clinic_id, None)
            for entry in existing_entries:
                if entry.appointment_id == appointment_id or entry.patient_id == patient_id:
                    return False, "Patient is already in the waiting queue"
            
            # Additional validation logic would go here
            # e.g., check appointment time, patient status, etc.
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Error validating queue entry: {str(e)}")
            return False, f"Validation error: {str(e)}"
    
    async def optimize_queue_order(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID
    ) -> List[WaitingQueue]:
        """Optimize queue order based on various factors."""
        
        try:
            entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            waiting_entries = [e for e in entries if e.status == WaitingQueueStatus.WAITING]
            
            # Sort by priority, then by enqueued_at
            priority_order = {
                WaitingQueuePriority.EMERGENCY: 1,
                WaitingQueuePriority.URGENT: 2,
                WaitingQueuePriority.VIP: 3,
                WaitingQueuePriority.NORMAL: 4
            }
            
            waiting_entries.sort(key=lambda x: (priority_order[x.priority], x.enqueued_at))
            
            # Update positions
            for i, entry in enumerate(waiting_entries, 1):
                if entry.position != i:
                    entry.position = i
                    entry.updated_at = datetime.utcnow()
            
            logger.info(f"Optimized queue order for {len(waiting_entries)} patients")
            return waiting_entries
            
        except Exception as e:
            logger.error(f"Error optimizing queue order: {str(e)}")
            return []
    
    async def get_queue_analytics(
        self,
        clinic_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive queue analytics."""
        
        try:
            # This would typically query the database for historical data
            # For now, return basic analytics
            
            analytics = {
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                },
                "metrics": {
                    "total_patients": 0,
                    "average_wait_time": 0,
                    "queue_efficiency": 0,
                    "patient_satisfaction": 0
                },
                "trends": {
                    "hourly_distribution": {},
                    "daily_distribution": {},
                    "priority_distribution": {}
                },
                "recommendations": []
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting queue analytics: {str(e)}")
            return {}
    
    async def cleanup_old_entries(self, days_old: int = 7):
        """Clean up old completed queue entries."""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # This would typically query and delete old entries from database
            # For now, just log the action
            
            logger.info(f"Cleaned up queue entries older than {days_old} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up old entries: {str(e)}")
    
    async def send_queue_notifications(
        self,
        clinic_id: uuid.UUID,
        doctor_id: Optional[uuid.UUID] = None,
        notification_type: str = "queue_update"
    ):
        """Send queue notifications to relevant parties."""
        
        try:
            # This would integrate with notification service
            # For now, just log the action
            
            logger.info(f"Sent {notification_type} notification for clinic {clinic_id}, doctor {doctor_id}")
            
        except Exception as e:
            logger.error(f"Error sending queue notifications: {str(e)}")
    
    async def handle_queue_overflow(
        self,
        clinic_id: uuid.UUID,
        doctor_id: uuid.UUID,
        max_queue_size: int = 20
    ) -> bool:
        """Handle queue overflow situations."""
        
        try:
            entries = await self.get_active_queue_entries(clinic_id, doctor_id)
            waiting_count = len([e for e in entries if e.status == WaitingQueueStatus.WAITING])
            
            if waiting_count >= max_queue_size:
                # Implement overflow handling logic
                # e.g., notify management, suggest alternative doctors, etc.
                
                logger.warning(f"Queue overflow detected: {waiting_count} patients waiting")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling queue overflow: {str(e)}")
            return False
