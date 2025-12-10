"""
DoesTheDogDie API client.

Fetches trigger warnings from DoesTheDogDie.com via their public API.
Requires an API key from https://www.doesthedogdie.com/profile
"""

import logging
from typing import List, Optional

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


class DoesTheDogDieClient:
    """
    Client for DoesTheDogDie.com API.
    
    Requires an API key from your profile page at:
    https://www.doesthedogdie.com/profile
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
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key and self.api_key.strip())
    
    def search_movie(self, title: str) -> List[MovieSearchResult]:
        """
        Search for a movie by title.
        
        Args:
            title: Movie title to search for
            
        Returns:
            List of MovieSearchResult objects
        """
        if not self.is_configured:
            logger.warning("DoesTheDogDie API key not configured")
            return []
        
        try:
            response = self.session.get(
                f"{API_BASE}/dddsearch",
                params={"q": title},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
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
            
        except requests.RequestException as e:
            logger.error(f"DoesTheDogDie search failed: {e}")
            return []
        except ValueError as e:
            logger.error(f"Failed to parse DoesTheDogDie response: {e}")
            return []
    
    def search_by_imdb(self, imdb_id: str) -> Optional[MovieSearchResult]:
        """
        Search for a movie by IMDb ID.
        
        Args:
            imdb_id: IMDb ID (e.g., "tt0133093")
            
        Returns:
            MovieSearchResult if found, None otherwise
        """
        if not self.is_configured:
            logger.warning("DoesTheDogDie API key not configured")
            return None
        
        try:
            response = self.session.get(
                f"{API_BASE}/dddsearch",
                params={"imdb": imdb_id},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
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
            
        except requests.RequestException as e:
            logger.error(f"DoesTheDogDie IMDb search failed: {e}")
            return None
    
    def get_triggers(self, media_id: int) -> List[TriggerWarning]:
        """
        Fetch trigger warnings for a movie.
        
        Args:
            media_id: DoesTheDogDie media ID
            
        Returns:
            List of TriggerWarning objects
        """
        if not self.is_configured:
            logger.warning("DoesTheDogDie API key not configured")
            return []
        
        try:
            response = self.session.get(
                f"{API_BASE}/media/{media_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
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
            
        except requests.RequestException as e:
            logger.error(f"DoesTheDogDie get_triggers failed: {e}")
            return []
        except ValueError as e:
            logger.error(f"Failed to parse DoesTheDogDie triggers: {e}")
            return []
    
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
