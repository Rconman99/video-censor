"""
Content Lookup Module

Provides clients for fetching movie content warnings from external databases:
- IMDb Parents Guide (via web scraping)
- DoesTheDogDie.com (via API)
"""

from .models import (
    ContentWarning,
    MovieContentInfo,
    TriggerWarning,
    MovieSearchResult,
    Severity,
    ContentCategory
)
from .imdb_client import IMDbClient
from .dtdd_client import DoesTheDogDieClient

__all__ = [
    'ContentWarning',
    'MovieContentInfo', 
    'TriggerWarning',
    'MovieSearchResult',
    'Severity',
    'ContentCategory',
    'IMDbClient',
    'DoesTheDogDieClient'
]

