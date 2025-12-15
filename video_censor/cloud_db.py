"""
Video Censor Cloud Database Client

Connects to Supabase for crowdsourced timestamp data.
When users process a video, they can optionally upload their detection
results to help others skip re-processing the same content.

FREE TIER SAFEGUARDS:
- Tracks monthly egress (5GB limit)
- Limits uploads to prevent database bloat (500MB limit)
- Auto-disables cloud features when approaching limits
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, date
import os

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = "https://asnazljepcdspoimadqq.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_SaOEm2oWD75d5X3DR7PPYg_y3gBYq7G"

# =============================================================================
# FREE TIER LIMITS (Supabase Free Plan - December 2024)
# =============================================================================
FREE_TIER_LIMITS = {
    "database_mb": 500,           # 500 MB database size
    "egress_gb": 5,               # 5 GB bandwidth/month
    "file_storage_gb": 1,         # 1 GB file storage
    "monthly_active_users": 50000, # 50k MAU (not relevant for our use)
}

# Safety margins - stop before hitting actual limits
SAFETY_THRESHOLDS = {
    "egress_percent": 80,         # Stop at 80% of egress limit (4GB)
    "database_percent": 90,       # Stop uploads at 90% of DB limit (450MB)
    "daily_requests": 1000,       # Max requests per day (self-imposed)
    "daily_uploads": 50,          # Max uploads per day (self-imposed)
}

# Usage tracking file location
def _get_usage_file() -> Path:
    """Get path to usage tracking file."""
    app_data = Path.home() / ".video_censor"
    app_data.mkdir(exist_ok=True)
    return app_data / "cloud_usage.json"


class UsageTracker:
    """Tracks Supabase usage to prevent exceeding free tier limits."""
    
    def __init__(self):
        self.usage_file = _get_usage_file()
        self._load_usage()
    
    def _load_usage(self):
        """Load usage data from file."""
        self._usage = {
            "month": date.today().strftime("%Y-%m"),
            "day": date.today().isoformat(),
            "daily_requests": 0,
            "daily_uploads": 0,
            "monthly_egress_kb": 0,
            "monthly_uploads_kb": 0,
            "total_uploads": 0,
            "disabled_reason": None,
        }
        
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    saved = json.load(f)
                    
                # Reset daily counters if new day
                if saved.get("day") != date.today().isoformat():
                    saved["day"] = date.today().isoformat()
                    saved["daily_requests"] = 0
                    saved["daily_uploads"] = 0
                    
                # Reset monthly counters if new month
                if saved.get("month") != date.today().strftime("%Y-%m"):
                    saved["month"] = date.today().strftime("%Y-%m")
                    saved["monthly_egress_kb"] = 0
                    saved["monthly_uploads_kb"] = 0
                    saved["disabled_reason"] = None  # Re-enable for new month
                    
                self._usage.update(saved)
            except Exception as e:
                logger.warning(f"Failed to load usage data: {e}")
    
    def _save_usage(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self._usage, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save usage data: {e}")
    
    def record_request(self, response_size_bytes: int = 0):
        """Record an API request and estimate egress."""
        self._usage["daily_requests"] += 1
        self._usage["monthly_egress_kb"] += response_size_bytes / 1024
        self._save_usage()
    
    def record_upload(self, data_size_bytes: int):
        """Record a data upload."""
        self._usage["daily_uploads"] += 1
        self._usage["monthly_uploads_kb"] += data_size_bytes / 1024
        self._usage["total_uploads"] += 1
        self._save_usage()
    
    def can_make_request(self) -> tuple[bool, str]:
        """Check if we can make a request without exceeding limits."""
        if self._usage.get("disabled_reason"):
            return False, self._usage["disabled_reason"]
        
        # Check daily request limit
        if self._usage["daily_requests"] >= SAFETY_THRESHOLDS["daily_requests"]:
            reason = f"Daily request limit reached ({SAFETY_THRESHOLDS['daily_requests']})"
            return False, reason
        
        # Check monthly egress (convert to GB for comparison)
        egress_gb = self._usage["monthly_egress_kb"] / (1024 * 1024)
        max_egress = FREE_TIER_LIMITS["egress_gb"] * (SAFETY_THRESHOLDS["egress_percent"] / 100)
        if egress_gb >= max_egress:
            reason = f"Monthly egress limit approaching ({egress_gb:.2f}GB / {FREE_TIER_LIMITS['egress_gb']}GB)"
            self._usage["disabled_reason"] = reason
            self._save_usage()
            return False, reason
        
        return True, ""
    
    def can_upload(self) -> tuple[bool, str]:
        """Check if we can upload data without exceeding limits."""
        can_request, reason = self.can_make_request()
        if not can_request:
            return False, reason
        
        # Check daily upload limit
        if self._usage["daily_uploads"] >= SAFETY_THRESHOLDS["daily_uploads"]:
            return False, f"Daily upload limit reached ({SAFETY_THRESHOLDS['daily_uploads']})"
        
        # Estimate if upload would push database over limit
        uploads_mb = self._usage["monthly_uploads_kb"] / 1024
        max_db = FREE_TIER_LIMITS["database_mb"] * (SAFETY_THRESHOLDS["database_percent"] / 100)
        if uploads_mb >= max_db:
            reason = f"Database size limit approaching ({uploads_mb:.1f}MB / {FREE_TIER_LIMITS['database_mb']}MB)"
            self._usage["disabled_reason"] = reason
            self._save_usage()
            return False, reason
        
        return True, ""
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary for display."""
        egress_gb = self._usage["monthly_egress_kb"] / (1024 * 1024)
        uploads_mb = self._usage["monthly_uploads_kb"] / 1024
        
        return {
            "month": self._usage["month"],
            "daily_requests": self._usage["daily_requests"],
            "daily_requests_limit": SAFETY_THRESHOLDS["daily_requests"],
            "daily_uploads": self._usage["daily_uploads"],
            "daily_uploads_limit": SAFETY_THRESHOLDS["daily_uploads"],
            "monthly_egress_gb": round(egress_gb, 3),
            "monthly_egress_limit_gb": FREE_TIER_LIMITS["egress_gb"],
            "monthly_uploads_mb": round(uploads_mb, 2),
            "database_limit_mb": FREE_TIER_LIMITS["database_mb"],
            "total_uploads": self._usage["total_uploads"],
            "disabled": bool(self._usage.get("disabled_reason")),
            "disabled_reason": self._usage.get("disabled_reason"),
        }
    
    def force_disable(self, reason: str):
        """Manually disable cloud features."""
        self._usage["disabled_reason"] = reason
        self._save_usage()
        logger.warning(f"Cloud features disabled: {reason}")
    
    def force_enable(self):
        """Re-enable cloud features (use with caution)."""
        self._usage["disabled_reason"] = None
        self._save_usage()
        logger.info("Cloud features re-enabled")


# Global usage tracker
_usage_tracker: Optional[UsageTracker] = None

def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker."""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


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
    # Community fields
    contributor_id: Optional[str] = None
    upvotes: int = 0
    downvotes: int = 0
    quality_score: float = 1.0  # Calculated: upvotes - downvotes + trust_score


@dataclass
class Contributor:
    """Anonymous contributor with trust score tracking."""
    id: str
    device_id: str
    trust_score: float = 1.0
    contribution_count: int = 0
    helpful_votes: int = 0
    created_at: Optional[str] = None


class CloudDatabaseClient:
    """Client for the Video Censor cloud database with free tier safeguards."""
    
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_ANON_KEY):
        """Initialize the cloud database client."""
        self.url = url
        self.key = key
        self._client = None
        self._initialized = False
        self._usage_tracker = get_usage_tracker()
        
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
        """Check if cloud database is available and within usage limits."""
        if self.client is None:
            return False
        can_request, reason = self._usage_tracker.can_make_request()
        if not can_request:
            logger.info(f"Cloud database disabled: {reason}")
            return False
        return True
    
    @property
    def usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary."""
        return self._usage_tracker.get_usage_summary()
    
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
        
        Respects free tier usage limits.
        """
        if not self.is_available:
            return None
        
        try:
            # Query by hash first, then verify size/duration
            response = self.client.table("video_detections").select("*").eq(
                "file_hash", fingerprint.file_hash
            ).execute()
            
            # Track usage (estimate response size)
            response_json = json.dumps(response.data) if response.data else ""
            self._usage_tracker.record_request(len(response_json.encode('utf-8')))
            
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
        
        Respects free tier upload limits to prevent database bloat.
        """
        # Check upload limits BEFORE attempting
        can_upload, reason = self._usage_tracker.can_upload()
        if not can_upload:
            logger.warning(f"Upload skipped: {reason}")
            return False
        
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
            
            # Calculate data size for tracking
            data_json = json.dumps(data)
            data_size = len(data_json.encode('utf-8'))
            
            response = self.client.table("video_detections").insert(data).execute()
            
            if response.data:
                # Track the upload
                self._usage_tracker.record_upload(data_size)
                logger.info(f"Uploaded detection results for: {result.title} ({data_size} bytes)")
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

    # =========================================================================
    # COMMUNITY FEATURES
    # =========================================================================
    
    def _get_device_id(self) -> str:
        """Get or generate a unique anonymous device ID."""
        device_file = Path.home() / ".video_censor" / "device_id"
        device_file.parent.mkdir(exist_ok=True)
        
        if device_file.exists():
            return device_file.read_text().strip()
        
        # Generate new device ID
        import uuid
        device_id = str(uuid.uuid4())
        device_file.write_text(device_id)
        return device_id
    
    def get_or_create_contributor(self) -> Optional[Contributor]:
        """
        Get or create an anonymous contributor record.
        Uses device ID for identification without requiring account creation.
        """
        if not self.is_available:
            return None
        
        device_id = self._get_device_id()
        
        try:
            # Check if contributor exists
            response = self.client.table("contributors").select("*").eq(
                "device_id", device_id
            ).execute()
            
            self._usage_tracker.record_request(len(str(response.data).encode('utf-8')))
            
            if response.data:
                record = response.data[0]
                return Contributor(
                    id=record['id'],
                    device_id=record['device_id'],
                    trust_score=record.get('trust_score', 1.0),
                    contribution_count=record.get('contribution_count', 0),
                    helpful_votes=record.get('helpful_votes', 0),
                    created_at=record.get('created_at')
                )
            
            # Create new contributor
            new_contributor = {
                'device_id': device_id,
                'trust_score': 1.0,
                'contribution_count': 0,
                'helpful_votes': 0,
                'created_at': datetime.utcnow().isoformat(),
            }
            
            response = self.client.table("contributors").insert(new_contributor).execute()
            
            if response.data:
                record = response.data[0]
                logger.info(f"Created new contributor: {record['id'][:8]}...")
                return Contributor(
                    id=record['id'],
                    device_id=device_id,
                    trust_score=1.0,
                    contribution_count=0,
                    helpful_votes=0,
                    created_at=record.get('created_at')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get/create contributor: {e}")
            return None
    
    def upload_with_contributor(self, result: DetectionResult) -> bool:
        """
        Upload detection results linked to the current contributor.
        Increments the contributor's contribution count.
        """
        contributor = self.get_or_create_contributor()
        if not contributor:
            # Fall back to anonymous upload
            return self.upload_detection(result)
        
        # Check upload limits
        can_upload, reason = self._usage_tracker.can_upload()
        if not can_upload:
            logger.warning(f"Upload skipped: {reason}")
            return False
        
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
                'contributor_id': contributor.id,
                'upvotes': 0,
                'downvotes': 0,
                'created_at': datetime.utcnow().isoformat(),
            }
            
            data_json = json.dumps(data)
            data_size = len(data_json.encode('utf-8'))
            
            response = self.client.table("video_detections").insert(data).execute()
            
            if response.data:
                self._usage_tracker.record_upload(data_size)
                
                # Increment contributor's count
                self.client.table("contributors").update({
                    'contribution_count': contributor.contribution_count + 1
                }).eq('id', contributor.id).execute()
                
                logger.info(f"Uploaded detection for '{result.title}' by contributor {contributor.id[:8]}...")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to upload with contributor: {e}")
            return False
    
    def vote_on_detection(self, detection_id: str, vote: int) -> bool:
        """
        Vote on a detection's accuracy (+1 upvote, -1 downvote).
        Each device can only vote once per detection.
        
        Args:
            detection_id: The UUID of the detection record
            vote: +1 for upvote, -1 for downvote
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if vote not in (-1, 1):
            logger.error("Vote must be +1 or -1")
            return False
        
        if not self.is_available:
            return False
        
        device_id = self._get_device_id()
        
        try:
            # Try to insert vote (unique constraint will prevent duplicates)
            vote_data = {
                'detection_id': detection_id,
                'device_id': device_id,
                'vote': vote,
                'created_at': datetime.utcnow().isoformat(),
            }
            
            response = self.client.table("video_votes").upsert(
                vote_data, 
                on_conflict="detection_id,device_id"
            ).execute()
            
            if response.data:
                # Update detection's vote counts
                detection_response = self.client.table("video_detections").select(
                    "upvotes, downvotes, contributor_id"
                ).eq('id', detection_id).execute()
                
                if detection_response.data:
                    current = detection_response.data[0]
                    new_upvotes = current.get('upvotes', 0) + (1 if vote == 1 else 0)
                    new_downvotes = current.get('downvotes', 0) + (1 if vote == -1 else 0)
                    
                    self.client.table("video_detections").update({
                        'upvotes': new_upvotes,
                        'downvotes': new_downvotes,
                    }).eq('id', detection_id).execute()
                    
                    # Update contributor's helpful votes if upvoted
                    if vote == 1 and current.get('contributor_id'):
                        self.client.table("contributors").update({
                            'helpful_votes': current.get('helpful_votes', 0) + 1
                        }).eq('id', current['contributor_id']).execute()
                
                logger.info(f"Recorded {'upvote' if vote == 1 else 'downvote'} for detection {detection_id[:8]}...")
                return True
            
            return False
            
        except Exception as e:
            # Unique constraint violation means already voted
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                logger.info("Already voted on this detection")
            else:
                logger.error(f"Failed to vote: {e}")
            return False
    
    def get_top_detection(
        self, 
        fingerprint: VideoFingerprint,
        min_quality_score: float = 0.5
    ) -> Optional[DetectionResult]:
        """
        Get the highest-quality community detection for a video.
        Quality is determined by: upvotes - downvotes + contributor trust score.
        
        Args:
            fingerprint: Video fingerprint to match
            min_quality_score: Minimum quality score to accept
        
        Returns:
            Best matching DetectionResult or None
        """
        if not self.is_available:
            return None
        
        try:
            # Query matches, ordered by quality metrics
            response = self.client.table("video_detections").select(
                "*, contributors(trust_score)"
            ).eq(
                "file_hash", fingerprint.file_hash
            ).execute()
            
            self._usage_tracker.record_request(len(str(response.data).encode('utf-8')))
            
            if not response.data:
                return None
            
            best_match = None
            best_score = min_quality_score - 1  # Start below threshold
            
            for record in response.data:
                # Verify it's the same video
                if (abs(record.get('file_size', 0) - fingerprint.file_size) >= 1000 or
                    abs(record.get('duration_seconds', 0) - fingerprint.duration_seconds) >= 1.0):
                    continue
                
                # Calculate quality score
                upvotes = record.get('upvotes', 0)
                downvotes = record.get('downvotes', 0)
                contributor_trust = 1.0
                if record.get('contributors') and isinstance(record['contributors'], dict):
                    contributor_trust = record['contributors'].get('trust_score', 1.0)
                
                quality_score = upvotes - downvotes + contributor_trust
                
                if quality_score > best_score:
                    best_score = quality_score
                    best_match = record
            
            if best_match and best_score >= min_quality_score:
                logger.info(f"Found community detection: '{best_match.get('title')}' (score: {best_score:.1f})")
                return DetectionResult(
                    fingerprint=fingerprint,
                    title=best_match.get('title'),
                    nudity_segments=best_match.get('nudity_segments', []),
                    profanity_segments=best_match.get('profanity_segments', []),
                    sexual_content_segments=best_match.get('sexual_content_segments', []),
                    violence_segments=best_match.get('violence_segments', []),
                    settings_used=best_match.get('settings_used', {}),
                    processing_time_seconds=best_match.get('processing_time_seconds', 0),
                    app_version=best_match.get('app_version', '1.0.0'),
                    contributor_id=best_match.get('contributor_id'),
                    upvotes=best_match.get('upvotes', 0),
                    downvotes=best_match.get('downvotes', 0),
                    quality_score=best_score
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get top detection: {e}")
            return None
    
    def get_contributor_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get the current user's contribution statistics.
        
        Returns:
            Dict with contribution_count, helpful_votes, trust_score, etc.
        """
        contributor = self.get_or_create_contributor()
        if not contributor:
            return None
        
        return {
            'contributor_id': contributor.id[:8] + '...',
            'trust_score': contributor.trust_score,
            'contribution_count': contributor.contribution_count,
            'helpful_votes': contributor.helpful_votes,
            'member_since': contributor.created_at,
        }


# Global client instance
_cloud_client: Optional[CloudDatabaseClient] = None


def get_cloud_client() -> CloudDatabaseClient:
    """Get the global cloud database client."""
    global _cloud_client
    if _cloud_client is None:
        _cloud_client = CloudDatabaseClient()
    return _cloud_client
