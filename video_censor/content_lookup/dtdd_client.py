"""
DoesTheDogDie API client.

Fetches trigger warnings from DoesTheDogDie.com via their public API.
Requires an API key from https://www.doesthedogdie.com/profile

FREE API SAFEGUARDS:
- Tracks daily request count (self-imposed limit)
- Rate limiting to prevent abuse
- Auto-disables if limits exceeded
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests

from .models import (
    TriggerWarning,
    MovieContentInfo,
    MovieSearchResult
)

logger = logging.getLogger(__name__)

# API base URL
API_BASE = "https://www.doesthedogdie.com"

# Topics relevant to our video censor app
# These map to content categories we care about
RELEVANT_TOPICS = {
    # Nudity/Sexual content
    "nudity": ["nudity", "naked", "topless", "genitals"],
    "sexual": ["sex", "rape", "sexual assault", "sexual violence", "intimate"],
    # Violence
    "violence": ["blood", "gore", "torture", "murder", "death", "killed", "violence"],
    # Profanity (less common on DTDD but may exist)
    "language": ["slur", "racial"],
    # Other concerning content
    "drugs": ["drug", "overdose", "addiction"],
    "self_harm": ["suicide", "self-harm", "cutting"],
    "child_abuse": ["child abuse", "pedophil"],
}

# =============================================================================
# FREE API SAFEGUARDS
# =============================================================================
DTDD_LIMITS = {
    "daily_requests": 100,      # Self-imposed daily limit (be a good API citizen)
    "requests_per_movie": 3,    # Max requests per movie lookup (search + triggers)
}


def _get_dtdd_usage_file() -> Path:
    """Get path to DTDD usage tracking file."""
    app_data = Path.home() / ".video_censor"
    app_data.mkdir(exist_ok=True)
    return app_data / "dtdd_usage.json"


class DTDDUsageTracker:
    """Tracks DoesTheDogDie API usage to be a good API citizen."""
    
    def __init__(self):
        self.usage_file = _get_dtdd_usage_file()
        self._load_usage()
    
    def _load_usage(self):
        """Load usage data from file."""
        self._usage = {
            "day": date.today().isoformat(),
            "daily_requests": 0,
            "total_requests": 0,
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
                    saved["disabled_reason"] = None  # Re-enable for new day
                
                self._usage.update(saved)
            except Exception as e:
                logger.warning(f"Failed to load DTDD usage data: {e}")
    
    def _save_usage(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self._usage, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save DTDD usage data: {e}")
    
    def record_request(self):
        """Record an API request."""
        self._usage["daily_requests"] += 1
        self._usage["total_requests"] += 1
        self._save_usage()
    
    def can_make_request(self) -> tuple[bool, str]:
        """Check if we can make a request."""
        if self._usage.get("disabled_reason"):
            return False, self._usage["disabled_reason"]
        
        if self._usage["daily_requests"] >= DTDD_LIMITS["daily_requests"]:
            reason = f"Daily limit reached ({DTDD_LIMITS['daily_requests']} requests)"
            self._usage["disabled_reason"] = reason
            self._save_usage()
            return False, reason
        
        return True, ""
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary."""
        return {
            "day": self._usage["day"],
            "daily_requests": self._usage["daily_requests"],
            "daily_limit": DTDD_LIMITS["daily_requests"],
            "total_requests": self._usage["total_requests"],
            "disabled": bool(self._usage.get("disabled_reason")),
            "disabled_reason": self._usage.get("disabled_reason"),
        }
    
    def force_enable(self):
        """Re-enable API (use with caution)."""
        self._usage["disabled_reason"] = None
        self._save_usage()


# Global tracker instance
_dtdd_tracker: Optional[DTDDUsageTracker] = None

def get_dtdd_tracker() -> DTDDUsageTracker:
    """Get the global DTDD usage tracker."""
    global _dtdd_tracker
    if _dtdd_tracker is None:
        _dtdd_tracker = DTDDUsageTracker()
    return _dtdd_tracker


class DoesTheDogDieClient:
    """
    Client for DoesTheDogDie.com API with usage safeguards.
    
    Requires an API key from your profile page at:
    https://www.doesthedogdie.com/profile
    
    Includes rate limiting to be a good API citizen.
    """
    
    def __init__(self, api_key: str, timeout: int = 10):
        """
        Initialize DoesTheDogDie client.
        
        Args:
            api_key: API key from DoesTheDogDie profile
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "X-API-KEY": api_key
        })
        self._usage_tracker = get_dtdd_tracker()
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key and self.api_key.strip())
    
    @property
    def is_available(self) -> bool:
        """Check if API is available (configured and within limits)."""
        if not self.is_configured:
            return False
        can_request, reason = self._usage_tracker.can_make_request()
        if not can_request:
            logger.info(f"DoesTheDogDie API disabled: {reason}")
            return False
        return True
    
    @property
    def usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary."""
        return self._usage_tracker.get_usage_summary()
    
    def _make_request(self, url: str, params: dict = None) -> Optional[dict]:
        """Make a rate-limited API request."""
        can_request, reason = self._usage_tracker.can_make_request()
        if not can_request:
            logger.warning(f"DTDD request blocked: {reason}")
            return None
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            self._usage_tracker.record_request()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"DTDD API request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse DTDD response: {e}")
            return None
    
    def search_movie(self, title: str) -> List[MovieSearchResult]:
        """
        Search for a movie by title (rate-limited).
        
        Args:
            title: Movie title to search for
            
        Returns:
            List of MovieSearchResult objects
        """
        if not self.is_available:
            return []
        
        data = self._make_request(f"{API_BASE}/dddsearch", params={"q": title})
        if not data:
            return []
        
        results = []
        for item in data.get("items", []):
            # Filter to movies only
            item_type = item.get("itemType", {})
            if item_type.get("name", "").lower() != "movie":
                continue
            
            poster_url = None
            if item.get("posterImage"):
                poster_url = f"http://image.tmdb.org/t/p/w200/{item['posterImage']}"
            
            results.append(MovieSearchResult(
                id=str(item.get("id", "")),
                title=item.get("name", "Unknown"),
                year=item.get("releaseYear"),
                source="dtdd",
                poster_url=poster_url
            ))
        
        return results[:10]  # Limit to top 10
    
    def search_by_imdb(self, imdb_id: str) -> Optional[MovieSearchResult]:
        """
        Search for a movie by IMDb ID (rate-limited).
        
        Args:
            imdb_id: IMDb ID (e.g., "tt0133093")
            
        Returns:
            MovieSearchResult if found, None otherwise
        """
        if not self.is_available:
            return None
        
        data = self._make_request(f"{API_BASE}/dddsearch", params={"imdb": imdb_id})
        if not data:
            return None
        
        items = data.get("items", [])
        if items:
            item = items[0]
            poster_url = None
            if item.get("posterImage"):
                poster_url = f"http://image.tmdb.org/t/p/w200/{item['posterImage']}"
            
            return MovieSearchResult(
                id=str(item.get("id", "")),
                title=item.get("name", "Unknown"),
                year=item.get("releaseYear"),
                source="dtdd",
                poster_url=poster_url
            )
        
        return None
    
    def get_triggers(self, media_id: int) -> List[TriggerWarning]:
        """
        Fetch trigger warnings for a movie (rate-limited).
        
        Args:
            media_id: DoesTheDogDie media ID
            
        Returns:
            List of TriggerWarning objects
        """
        if not self.is_available:
            return []
        
        data = self._make_request(f"{API_BASE}/media/{media_id}")
        if not data:
            return []
        
        triggers = []
        for stat in data.get("topicItemStats", []):
            topic = stat.get("topic", {})
            topic_name = topic.get("name", "")
            if not topic_name:
                topic_name = topic.get("doesName", "Unknown")
            
            yes_votes = stat.get("yesSum", 0)
            no_votes = stat.get("noSum", 0)
            
            # Determine if trigger is present (majority vote)
            is_present = yes_votes > no_votes
            
            # Get top comment
            comment = ""
            comments = stat.get("comments", [])
            if comments:
                comment = comments[0].get("comment", "")
            elif stat.get("comment"):
                comment = stat.get("comment", "")
            
            # Check if spoiler
            is_spoiler = topic.get("isSpoiler", False)
            
            triggers.append(TriggerWarning(
                topic=topic_name,
                is_present=is_present,
                yes_votes=yes_votes,
                no_votes=no_votes,
                comment=comment,
                is_spoiler=is_spoiler
            ))
        
        return triggers
    
    def get_relevant_triggers(self, media_id: int) -> List[TriggerWarning]:
        """
        Fetch only triggers relevant to video censoring.
        
        Filters triggers to those matching our content categories
        (nudity, sexual content, violence, language).
        
        Args:
            media_id: DoesTheDogDie media ID
            
        Returns:
            List of relevant TriggerWarning objects
        """
        all_triggers = self.get_triggers(media_id)
        
        relevant = []
        for trigger in all_triggers:
            topic_lower = trigger.topic.lower()
            
            # Check if trigger matches any of our categories
            is_relevant = False
            for category, keywords in RELEVANT_TOPICS.items():
                for keyword in keywords:
                    if keyword in topic_lower:
                        is_relevant = True
                        break
                if is_relevant:
                    break
            
            if is_relevant:
                relevant.append(trigger)
        
        # Sort by vote count (most voted first)
        relevant.sort(key=lambda t: t.yes_votes + t.no_votes, reverse=True)
        
        return relevant
    
    def lookup_movie(self, title: str, imdb_id: Optional[str] = None) -> Optional[MovieContentInfo]:
        """
        Convenience method to search and fetch triggers in one call.
        
        Args:
            title: Movie title
            imdb_id: Optional IMDb ID for more accurate matching
            
        Returns:
            MovieContentInfo with triggers if found, None otherwise
        """
        if not self.is_configured:
            return None
        
        # Try IMDb ID first if provided
        result = None
        if imdb_id:
            result = self.search_by_imdb(imdb_id)
        
        # Fall back to title search
        if not result:
            results = self.search_movie(title)
            if results:
                result = results[0]
        
        if not result:
            logger.warning(f"No DoesTheDogDie results for: {title}")
            return None
        
        logger.info(f"Found DTDD match: {result.title} ({result.year}) - ID {result.id}")
        
        # Fetch triggers
        triggers = self.get_relevant_triggers(int(result.id))
        
        return MovieContentInfo(
            title=result.title,
            year=result.year,
            dtdd_id=int(result.id),
            triggers=triggers
        )
