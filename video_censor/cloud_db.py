"""
Video Censor Cloud Database Client

Connects to Supabase for crowdsourced timestamp data.
When users process a video, they can optionally upload their detection
results to help others skip re-processing the same content.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = "https://asnazljepcdspoimadqq.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_SaOEm2oWD75d5X3DR7PPYg_y3gBYq7G"


@dataclass
class VideoFingerprint:
    """Unique identifier for a video file."""
    file_hash: str  # First 10MB hash for quick matching
    file_size: int  # Total file size in bytes
    duration_seconds: float  # Video duration


@dataclass
class DetectionResult:
    """Detection results for a single video."""
    fingerprint: VideoFingerprint
    title: Optional[str]
    nudity_segments: List[Dict[str, Any]]  # [{start, end, confidence, labels}]
    profanity_segments: List[Dict[str, Any]]  # [{start, end, word}]
    sexual_content_segments: List[Dict[str, Any]]  # [{start, end, score}]
    violence_segments: List[Dict[str, Any]]  # [{start, end, intensity}]
    settings_used: Dict[str, Any]  # Detection thresholds
    processing_time_seconds: float
    app_version: str = "1.0.0"


class CloudDatabaseClient:
    """Client for the Video Censor cloud database."""
    
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_ANON_KEY):
        """Initialize the cloud database client."""
        self.url = url
        self.key = key
        self._client = None
        self._initialized = False
        
    @property
    def client(self):
        """Lazy-load the Supabase client."""
        if self._client is None:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
                self._initialized = True
                logger.info("Connected to Video Censor cloud database")
            except ImportError:
                logger.warning("Supabase library not installed. Run: pip install supabase")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to cloud database: {e}")
                return None
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if cloud database is available."""
        return self.client is not None
    
    def compute_fingerprint(self, video_path: str, duration: float) -> Optional[VideoFingerprint]:
        """
        Compute a fingerprint for a video file.
        Uses first 10MB hash + file size + duration for matching.
        """
        try:
            path = Path(video_path)
            file_size = path.stat().st_size
            
            # Hash first 10MB for speed
            hasher = hashlib.sha256()
            with open(path, 'rb') as f:
                chunk = f.read(10 * 1024 * 1024)  # 10MB
                hasher.update(chunk)
            
            return VideoFingerprint(
                file_hash=hasher.hexdigest(),
                file_size=file_size,
                duration_seconds=duration
            )
        except Exception as e:
            logger.error(f"Failed to compute fingerprint: {e}")
            return None
    
    def lookup_video(self, fingerprint: VideoFingerprint) -> Optional[DetectionResult]:
        """
        Look up existing detection results for a video.
        Returns cached results if found, None otherwise.
        """
        if not self.is_available:
            return None
        
        try:
            # Query by hash first, then verify size/duration
            response = self.client.table("video_detections").select("*").eq(
                "file_hash", fingerprint.file_hash
            ).execute()
            
            if response.data:
                for record in response.data:
                    # Verify it's the same video (size and duration should match)
                    if (abs(record.get('file_size', 0) - fingerprint.file_size) < 1000 and
                        abs(record.get('duration_seconds', 0) - fingerprint.duration_seconds) < 1.0):
                        
                        logger.info(f"Found cached detection for: {record.get('title', 'Unknown')}")
                        
                        return DetectionResult(
                            fingerprint=fingerprint,
                            title=record.get('title'),
                            nudity_segments=record.get('nudity_segments', []),
                            profanity_segments=record.get('profanity_segments', []),
                            sexual_content_segments=record.get('sexual_content_segments', []),
                            violence_segments=record.get('violence_segments', []),
                            settings_used=record.get('settings_used', {}),
                            processing_time_seconds=record.get('processing_time_seconds', 0),
                            app_version=record.get('app_version', '1.0.0')
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Cloud lookup failed: {e}")
            return None
    
    def upload_detection(self, result: DetectionResult) -> bool:
        """
        Upload detection results to help other users.
        Returns True if successful.
        """
        if not self.is_available:
            return False
        
        try:
            data = {
                'file_hash': result.fingerprint.file_hash,
                'file_size': result.fingerprint.file_size,
                'duration_seconds': result.fingerprint.duration_seconds,
                'title': result.title,
                'nudity_segments': result.nudity_segments,
                'profanity_segments': result.profanity_segments,
                'sexual_content_segments': result.sexual_content_segments,
                'violence_segments': result.violence_segments,
                'settings_used': result.settings_used,
                'processing_time_seconds': result.processing_time_seconds,
                'app_version': result.app_version,
                'created_at': datetime.utcnow().isoformat(),
            }
            
            response = self.client.table("video_detections").insert(data).execute()
            
            if response.data:
                logger.info(f"Uploaded detection results for: {result.title}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to upload detection: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cloud database."""
        if not self.is_available:
            return {'available': False}
        
        try:
            response = self.client.table("video_detections").select("id", count="exact").execute()
            return {
                'available': True,
                'total_videos': response.count or 0,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'available': False, 'error': str(e)}

    def search_videos(self, query: str) -> List[Dict[str, Any]]:
        """Search for videos by title."""
        if not self.is_available:
            return []
        
        try:
            response = self.client.table("video_detections").select(
                "id, title, created_at, file_size, duration_seconds, "
                "nudity_segments, profanity_segments, sexual_content_segments, violence_segments"
            ).ilike("title", f"%{query}%").order("created_at", desc=True).limit(20).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []


# Global client instance
_cloud_client: Optional[CloudDatabaseClient] = None


def get_cloud_client() -> CloudDatabaseClient:
    """Get the global cloud database client."""
    global _cloud_client
    if _cloud_client is None:
        _cloud_client = CloudDatabaseClient()
    return _cloud_client
