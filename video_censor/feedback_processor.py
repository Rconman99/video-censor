"""
Feedback Processor for Video Censor

Processes user feedback:
- Auto-fixable issues: Updates cloud timestamps directly
- Custom requests: Queues for admin review
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FeedbackItem:
    """Represents a feedback item to process."""
    feedback_type: str  # 'missed_profanity', 'missed_nudity', 'missed_violence', 'custom', 'feature_request'
    video_title: str
    video_detection_id: Optional[str]
    timestamp_start: Optional[float]
    timestamp_end: Optional[float]
    description: str
    user_email: Optional[str] = None


class FeedbackProcessor:
    """
    Processes user feedback automatically or queues for admin review.
    
    Auto-fixable:
    - Missed profanity at timestamp X → Add to cloud timestamps
    - Missed nudity at timestamp X → Add to cloud timestamps
    - Missed violence at timestamp X → Add to cloud timestamps
    
    Admin review:
    - Feature requests
    - Custom phrase additions
    - Bug reports
    - Complex issues
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            try:
                from video_censor.cloud_db import get_cloud_client
                cloud = get_cloud_client()
                if cloud.is_available:
                    self._client = cloud.client
            except Exception as e:
                logger.debug(f"Feedback client not available: {e}")
        return self._client
    
    @property
    def is_available(self) -> bool:
        return self.client is not None
    
    def process_feedback(self, item: FeedbackItem) -> Dict[str, Any]:
        """
        Process a feedback item.
        
        Returns:
            dict with 'status' ('auto_fixed' or 'queued') and details
        """
        if not self.is_available:
            return {'status': 'error', 'message': 'Cloud not available'}
        
        # Determine if auto-fixable
        auto_fixable_types = ['missed_profanity', 'missed_nudity', 'missed_violence', 
                              'Heard profanity', 'Saw nudity', 'Saw violence']
        
        if item.feedback_type in auto_fixable_types and item.timestamp_start is not None:
            return self._auto_fix(item)
        else:
            return self._queue_for_review(item)
    
    def _auto_fix(self, item: FeedbackItem) -> Dict[str, Any]:
        """
        Auto-fix by adding timestamp to cloud database.
        Updates the video_detections record with the new segment.
        """
        try:
            # Normalize feedback type
            segment_type = 'profanity'
            if 'nudity' in item.feedback_type.lower():
                segment_type = 'nudity'
            elif 'violence' in item.feedback_type.lower():
                segment_type = 'violence'
            
            # Add to feedback queue with auto_fixable flag
            self.client.table("feedback_queue").insert({
                'video_detection_id': item.video_detection_id,
                'issue_type': f'missed_{segment_type}',
                'timestamp_start': item.timestamp_start,
                'timestamp_end': item.timestamp_end or (item.timestamp_start + 2.0),
                'status': 'pending',
                'auto_fixable': True,
                'notes': item.description,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            # If we have a video_detection_id, update it directly
            if item.video_detection_id:
                self._add_segment_to_detection(
                    item.video_detection_id, 
                    segment_type, 
                    item.timestamp_start,
                    item.timestamp_end or (item.timestamp_start + 2.0)
                )
                
                return {
                    'status': 'auto_fixed',
                    'message': f'Added {segment_type} segment at {item.timestamp_start:.1f}s',
                    'segment_type': segment_type,
                    'timestamp': item.timestamp_start
                }
            else:
                return {
                    'status': 'queued',
                    'message': 'Queued for processing (no detection ID)',
                    'segment_type': segment_type
                }
                
        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _add_segment_to_detection(
        self, 
        detection_id: str, 
        segment_type: str, 
        start: float, 
        end: float
    ):
        """Add a new segment to an existing detection record."""
        try:
            # Get current detection
            response = self.client.table("video_detections").select("*").eq(
                "id", detection_id
            ).execute()
            
            if not response.data:
                logger.warning(f"Detection {detection_id} not found")
                return
            
            record = response.data[0]
            
            # Determine which array to update
            column_map = {
                'profanity': 'profanity_segments',
                'nudity': 'nudity_segments',
                'violence': 'violence_segments'
            }
            
            column = column_map.get(segment_type)
            if not column:
                return
            
            # Get current segments
            segments = record.get(column, []) or []
            
            # Add new segment
            new_segment = {'start': start, 'end': end, 'source': 'user_feedback'}
            segments.append(new_segment)
            
            # Sort by start time
            segments.sort(key=lambda x: x.get('start', 0))
            
            # Update record
            self.client.table("video_detections").update({
                column: segments
            }).eq("id", detection_id).execute()
            
            logger.info(f"Added {segment_type} segment to detection {detection_id}")
            
            # Mark feedback queue item as fixed
            self.client.table("feedback_queue").update({
                'status': 'fixed',
                'processed_at': datetime.utcnow().isoformat()
            }).eq("video_detection_id", detection_id).eq("status", "pending").execute()
            
        except Exception as e:
            logger.error(f"Failed to add segment: {e}")
    
    def _queue_for_review(self, item: FeedbackItem) -> Dict[str, Any]:
        """Queue a custom request for admin review."""
        try:
            # Determine request type
            request_type = 'other'
            description = item.description or item.feedback_type
            
            if 'feature' in item.feedback_type.lower():
                request_type = 'feature_request'
            elif 'bug' in item.feedback_type.lower():
                request_type = 'bug_report'
            elif 'phrase' in item.feedback_type.lower() or 'word' in item.feedback_type.lower():
                request_type = 'custom_phrase'
            elif item.feedback_type.lower() == 'other':
                request_type = 'other'
            
            self.client.table("admin_review_queue").insert({
                'video_title': item.video_title,
                'request_type': request_type,
                'description': description,
                'user_email': item.user_email,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            logger.info(f"Queued for admin review: {request_type}")
            
            return {
                'status': 'queued',
                'message': 'Submitted for admin review',
                'request_type': request_type
            }
            
        except Exception as e:
            logger.error(f"Failed to queue for review: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_pending_fixes(self) -> List[Dict[str, Any]]:
        """Get pending auto-fix items (admin view)."""
        if not self.is_available:
            return []
        
        try:
            response = self.client.table("feedback_queue").select("*").eq(
                "status", "pending"
            ).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get pending fixes: {e}")
            return []
    
    def get_admin_queue(self) -> List[Dict[str, Any]]:
        """Get pending admin review items."""
        if not self.is_available:
            return []
        
        try:
            response = self.client.table("admin_review_queue").select("*").eq(
                "status", "pending"
            ).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get admin queue: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get feedback processing stats."""
        if not self.is_available:
            return {'available': False}
        
        try:
            pending = self.client.table("feedback_queue").select("id", count="exact").eq("status", "pending").execute()
            fixed = self.client.table("feedback_queue").select("id", count="exact").eq("status", "fixed").execute()
            admin = self.client.table("admin_review_queue").select("id", count="exact").eq("status", "pending").execute()
            
            return {
                'available': True,
                'pending_fixes': pending.count or 0,
                'completed_fixes': fixed.count or 0,
                'pending_admin_review': admin.count or 0
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}


# Global processor instance
_processor: Optional[FeedbackProcessor] = None


def get_feedback_processor() -> FeedbackProcessor:
    """Get the global feedback processor."""
    global _processor
    if _processor is None:
        _processor = FeedbackProcessor()
    return _processor
