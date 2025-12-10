"""
IMDb Parents Guide client.

Scrapes content warnings from IMDb Parents Guide pages using
requests and BeautifulSoup.
"""

import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .models import (
    ContentWarning,
    ContentCategory,
    MovieContentInfo,
    MovieSearchResult,
    Severity
)

logger = logging.getLogger(__name__)

# IMDb URLs
IMDB_SEARCH_URL = "https://www.imdb.com/find"
IMDB_PARENTS_GUIDE_URL = "https://www.imdb.com/title/{imdb_id}/parentalguide"

# User agent to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Map IMDb section IDs to our categories
SECTION_MAPPING = {
    "advisory-nudity": ContentCategory.SEX_NUDITY,
    "advisory-violence": ContentCategory.VIOLENCE_GORE,
    "advisory-profanity": ContentCategory.PROFANITY,
    "advisory-alcohol": ContentCategory.ALCOHOL_DRUGS,
    "advisory-frightening": ContentCategory.FRIGHTENING,
}


class IMDbClient:
    """
    Client for fetching content warnings from IMDb Parents Guide.
    
    Uses web scraping since IMDb doesn't provide a free API for Parents Guide data.
    """
    
    def __init__(self, timeout: int = 10):
        """
        Initialize IMDb client.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def search_movie(self, title: str, year: Optional[int] = None) -> List[MovieSearchResult]:
        """
        Search for a movie on IMDb by title.
        
        Args:
            title: Movie title to search for
            year: Optional release year to narrow results
            
        Returns:
            List of matching MovieSearchResult objects
        """
        try:
            # Build search query
            query = title
            if year:
                query = f"{title} {year}"
            
            params = {
                "q": query,
                "s": "tt",  # Search titles only
                "ttype": "ft",  # Feature films
            }
            
            response = self.session.get(
                IMDB_SEARCH_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return self._parse_search_results(response.text)
            
        except requests.RequestException as e:
            logger.error(f"IMDb search failed: {e}")
            return []
    
    def _parse_search_results(self, html: str) -> List[MovieSearchResult]:
        """Parse search results from IMDb search page."""
        results = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find search result items - IMDb uses various structures
        # Try the newer JSON-LD data first
        script_tags = soup.find_all("script", type="application/ld+json")
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        if item.get("@type") == "ListItem":
                            movie = item.get("item", {})
                            if movie.get("@type") == "Movie":
                                imdb_id = self._extract_imdb_id(movie.get("url", ""))
                                if imdb_id:
                                    results.append(MovieSearchResult(
                                        id=imdb_id,
                                        title=movie.get("name", "Unknown"),
                                        year=None,
                                        source="imdb",
                                        poster_url=movie.get("image")
                                    ))
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Fallback: Parse HTML structure
        if not results:
            # Look for result list items
            result_items = soup.select(".ipc-metadata-list-summary-item")
            for item in result_items[:10]:  # Limit to top 10
                try:
                    link = item.select_one("a[href*='/title/tt']")
                    if link:
                        href = link.get("href", "")
                        imdb_id = self._extract_imdb_id(href)
                        title_text = link.get_text(strip=True)
                        
                        # Try to extract year
                        year_match = None
                        year_span = item.select_one(".ipc-metadata-list-summary-item__li")
                        if year_span:
                            year_text = year_span.get_text(strip=True)
                            if year_text.isdigit() and len(year_text) == 4:
                                year_match = year_text
                        
                        if imdb_id:
                            results.append(MovieSearchResult(
                                id=imdb_id,
                                title=title_text,
                                year=year_match,
                                source="imdb"
                            ))
                except Exception as e:
                    logger.debug(f"Failed to parse search result item: {e}")
                    continue
        
        return results
    
    def _extract_imdb_id(self, url_or_path: str) -> Optional[str]:
        """Extract IMDb ID (tt1234567) from URL or path."""
        match = re.search(r"(tt\d{7,})", url_or_path)
        return match.group(1) if match else None
    
    def get_parents_guide(self, imdb_id: str) -> Optional[MovieContentInfo]:
        """
        Fetch Parents Guide content warnings for a movie.
        
        Args:
            imdb_id: IMDb ID (e.g., "tt0133093")
            
        Returns:
            MovieContentInfo with content warnings, or None if failed
        """
        try:
            url = IMDB_PARENTS_GUIDE_URL.format(imdb_id=imdb_id)
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            return self._parse_parents_guide(imdb_id, response.text)
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch Parents Guide for {imdb_id}: {e}")
            return None
    
    def _parse_parents_guide(self, imdb_id: str, html: str) -> MovieContentInfo:
        """Parse Parents Guide page for content warnings."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title
        title = "Unknown"
        title_elem = soup.select_one("h3[itemprop='name'] a, .ipc-title__text")
        if title_elem:
            title = title_elem.get_text(strip=True)
            # Clean up title (remove "Parents Guide" suffix if present)
            title = re.sub(r"\s*-?\s*Parents Guide.*$", "", title, flags=re.IGNORECASE)
        
        # Extract year
        year = None
        year_elem = soup.select_one(".ipc-inline-list__item a[href*='releaseinfo']")
        if year_elem:
            year_text = year_elem.get_text(strip=True)
            year_match = re.search(r"(\d{4})", year_text)
            if year_match:
                year = year_match.group(1)
        
        # Parse content warnings
        warnings = []
        
        for section_id, category in SECTION_MAPPING.items():
            section = soup.find(id=section_id)
            if section:
                severity, descriptions = self._parse_section(section)
                warnings.append(ContentWarning(
                    category=category,
                    severity=severity,
                    descriptions=descriptions
                ))
            else:
                # Section not found, mark as unknown
                warnings.append(ContentWarning(
                    category=category,
                    severity=Severity.UNKNOWN,
                    descriptions=[]
                ))
        
        return MovieContentInfo(
            title=title,
            year=year,
            imdb_id=imdb_id,
            warnings=warnings
        )
    
    def _parse_section(self, section) -> Tuple[Severity, List[str]]:
        """
        Parse a content section for severity and descriptions.
        
        Args:
            section: BeautifulSoup element for the section
            
        Returns:
            Tuple of (Severity, list of description strings)
        """
        severity = Severity.UNKNOWN
        descriptions = []
        
        # Look for severity indicator
        # IMDb uses different structures, try multiple selectors
        severity_selectors = [
            ".ipc-advisory-severity-indicator__label",
            ".advisory-severity-vote__container span",
            "[data-testid='advisory-severity']"
        ]
        
        for selector in severity_selectors:
            sev_elem = section.select_one(selector)
            if sev_elem:
                sev_text = sev_elem.get_text(strip=True).lower()
                severity = Severity.from_string(sev_text)
                if severity != Severity.UNKNOWN:
                    break
        
        # Look for description items
        desc_selectors = [
            ".ipc-html-content-inner-div",
            ".advisory-list-item p",
            ".ipc-list-card__content"
        ]
        
        for selector in desc_selectors:
            desc_elems = section.select(selector)
            if desc_elems:
                for elem in desc_elems:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 10:  # Filter out short/empty items
                        # Clean up the text
                        text = re.sub(r"\s+", " ", text)
                        descriptions.append(text)
                break
        
        return severity, descriptions[:10]  # Limit to 10 descriptions
    
    def lookup_movie(self, title: str, year: Optional[int] = None) -> Optional[MovieContentInfo]:
        """
        Convenience method to search and fetch Parents Guide in one call.
        
        Args:
            title: Movie title
            year: Optional release year
            
        Returns:
            MovieContentInfo if found, None otherwise
        """
        results = self.search_movie(title, year)
        if not results:
            logger.warning(f"No IMDb results found for: {title}")
            return None
        
        # Use the first result
        best_match = results[0]
        logger.info(f"Found IMDb match: {best_match.title} ({best_match.year}) - {best_match.id}")
        
        return self.get_parents_guide(best_match.id)
