"""
Video Censor Telemetry Module

Tracks app usage, errors, and feedback to improve the app.
All tracking is opt-in and data helps improve detection accuracy.
"""

import logging
import platform
import traceback
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# App version - update with each release
APP_VERSION = "1.0.0"


@dataclass
class SessionInfo:
    """Current app session information."""
    session_id: str
    started_at: datetime
    videos_processed: int = 0
    features_used: List[str] = None
    
    def __post_init__(self):
        if self.features_used is None:
            self.features_used = []


class TelemetryClient:
    """
    Client for tracking app telemetry.
    
    Tracks:
    - Session starts and feature usage
    - Processing errors for debugging
    - User feedback on detection accuracy
    """
    
    def __init__(self, enabled: bool = True):
        """Initialize telemetry client."""
        self.enabled = enabled
        self._session: Optional[SessionInfo] = None
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
                logger.debug(f"Telemetry client not available: {e}")
        return self._client
    
    def start_session(self) -> str:
        """Start a new app session. Returns session ID."""
        session_id = str(uuid.uuid4())
        self._session = SessionInfo(
            session_id=session_id,
            started_at=datetime.utcnow()
        )
        
        if not self.enabled or not self.client:
            return session_id
        
        try:
            self.client.table("app_sessions").insert({
                'session_id': session_id,
                'app_version': APP_VERSION,
                'os_version': f"{platform.system()} {platform.release()}",
                'started_at': self._session.started_at.isoformat(),
                'videos_processed': 0,
                'features_used': []
            }).execute()
            logger.debug(f"Started session: {session_id}")
        except Exception as e:
            logger.debug(f"Failed to log session start: {e}")
        
        return session_id
    
    def track_video_processed(self, features: List[str] = None):
        """Track that a video was processed with given features."""
        if self._session:
            self._session.videos_processed += 1
            if features:
                for f in features:
                    if f not in self._session.features_used:
                        self._session.features_used.append(f)
        
        if not self.enabled or not self.client or not self._session:
            return
        
        try:
            self.client.table("app_sessions").update({
                'videos_processed': self._session.videos_processed,
                'features_used': self._session.features_used
            }).eq('session_id', self._session.session_id).execute()
        except Exception as e:
            logger.debug(f"Failed to update session: {e}")
    
    def track_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any] = None,
        include_traceback: bool = True
    ):
        """
        Track an error for debugging.
        
        Args:
            error_type: Category of error (e.g., 'detection', 'render', 'crash')
            error_message: The error message
            context: Additional context (file info, settings, etc.)
            include_traceback: Whether to include stack trace
        """
        if not self.enabled or not self.client:
            return
        
        try:
            data = {
                'session_id': self._session.session_id if self._session else None,
                'error_type': error_type,
                'error_message': error_message[:1000],  # Limit length
                'stack_trace': traceback.format_exc()[:5000] if include_traceback else None,
                'context': context or {},
                'app_version': APP_VERSION,
                'created_at': datetime.utcnow().isoformat()
            }
            self.client.table("error_logs").insert(data).execute()
            logger.debug(f"Tracked error: {error_type}")
        except Exception as e:
            logger.debug(f"Failed to track error: {e}")
    
    def submit_feedback(
        self,
        detection_id: str,
        feedback_type: str,
        segment_start: Optional[float] = None,
        segment_end: Optional[float] = None,
        comment: Optional[str] = None
    ):
        """
        Submit feedback about detection accuracy.
        
        Args:
            detection_id: UUID of the detection record
            feedback_type: 'false_positive', 'false_negative', or 'incorrect_timing'
            segment_start: Start time of the segment in question
            segment_end: End time of the segment
            comment: Optional user comment
        """
        if not self.enabled or not self.client:
            return
        
        try:
            data = {
                'detection_id': detection_id,
                'feedback_type': feedback_type,
                'segment_start': segment_start,
                'segment_end': segment_end,
                'user_comment': comment[:500] if comment else None,
                'created_at': datetime.utcnow().isoformat()
            }
            self.client.table("detection_feedback").insert(data).execute()
            logger.info(f"Submitted feedback: {feedback_type}")
        except Exception as e:
            logger.debug(f"Failed to submit feedback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics (admin only)."""
        if not self.client:
            return {'available': False}
        
        try:
            sessions = self.client.table("app_sessions").select("id", count="exact").execute()
            errors = self.client.table("error_logs").select("id", count="exact").execute()
            feedback = self.client.table("detection_feedback").select("id", count="exact").execute()
            
            return {
                'available': True,
                'total_sessions': sessions.count or 0,
                'total_errors': errors.count or 0,
                'total_feedback': feedback.count or 0
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}


# Global telemetry instance
_telemetry: Optional[TelemetryClient] = None


def get_telemetry(enabled: bool = True) -> TelemetryClient:
    """Get the global telemetry client."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryClient(enabled=enabled)
    return _telemetry


def track_error(error_type: str, error_message: str, context: Dict[str, Any] = None):
    """Convenience function to track an error."""
    get_telemetry().track_error(error_type, error_message, context)
