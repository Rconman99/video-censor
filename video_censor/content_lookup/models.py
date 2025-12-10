"""
Data models for content lookup services.

Provides dataclasses for representing movie content warnings
from IMDb Parents Guide and DoesTheDogDie.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime


class Severity(Enum):
    """Content severity rating (IMDb style)."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """Parse severity from string."""
        value_lower = value.lower().strip()
        for sev in cls:
            if sev.value == value_lower:
                return sev
        return cls.UNKNOWN
    
    @property
    def color(self) -> str:
        """Get display color for severity."""
        return {
            Severity.NONE: "#4ade80",      # Green
            Severity.MILD: "#facc15",      # Yellow
            Severity.MODERATE: "#fb923c",  # Orange
            Severity.SEVERE: "#ef4444",    # Red
            Severity.UNKNOWN: "#9ca3af"    # Gray
        }.get(self, "#9ca3af")


class ContentCategory(Enum):
    """Categories of content warnings."""
    SEX_NUDITY = "sex_nudity"
    VIOLENCE_GORE = "violence_gore"
    PROFANITY = "profanity"
    ALCOHOL_DRUGS = "alcohol_drugs"
    FRIGHTENING = "frightening"


@dataclass
class ContentWarning:
    """
    Individual content warning for a category.
    
    Attributes:
        category: The content category (sex, violence, etc.)
        severity: Severity rating (none to severe)
        descriptions: List of text descriptions of specific content
        vote_count: Number of user votes (if available)
    """
    category: ContentCategory
    severity: Severity
    descriptions: List[str] = field(default_factory=list)
    vote_count: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "descriptions": self.descriptions,
            "vote_count": self.vote_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContentWarning":
        """Create from dictionary."""
        return cls(
            category=ContentCategory(data.get("category", "sex_nudity")),
            severity=Severity.from_string(data.get("severity", "unknown")),
            descriptions=data.get("descriptions", []),
            vote_count=data.get("vote_count", 0)
        )


@dataclass
class TriggerWarning:
    """
    Trigger warning from DoesTheDogDie.
    
    Attributes:
        topic: The trigger topic (e.g., "a dog dies", "someone is sexually assaulted")
        is_present: Whether this trigger is present in the movie
        yes_votes: Number of "yes" votes
        no_votes: Number of "no" votes
        comment: Top-voted user comment explaining the trigger
        is_spoiler: Whether this warning contains spoilers
    """
    topic: str
    is_present: bool
    yes_votes: int = 0
    no_votes: int = 0
    comment: str = ""
    is_spoiler: bool = False
    
    @property
    def confidence(self) -> float:
        """Calculate confidence based on vote ratio."""
        total = self.yes_votes + self.no_votes
        if total == 0:
            return 0.0
        return self.yes_votes / total if self.is_present else self.no_votes / total
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "topic": self.topic,
            "is_present": self.is_present,
            "yes_votes": self.yes_votes,
            "no_votes": self.no_votes,
            "comment": self.comment,
            "is_spoiler": self.is_spoiler,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TriggerWarning":
        """Create from dictionary."""
        return cls(
            topic=data.get("topic", ""),
            is_present=data.get("is_present", False),
            yes_votes=data.get("yes_votes", 0),
            no_votes=data.get("no_votes", 0),
            comment=data.get("comment", ""),
            is_spoiler=data.get("is_spoiler", False)
        )


@dataclass
class MovieSearchResult:
    """
    Search result for a movie lookup.
    
    Attributes:
        id: Unique identifier (IMDb ID or DTDD media ID)
        title: Movie title
        year: Release year
        source: Data source ("imdb" or "dtdd")
        poster_url: Optional poster image URL
    """
    id: str
    title: str
    year: Optional[str] = None
    source: str = "imdb"
    poster_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "source": self.source,
            "poster_url": self.poster_url
        }


@dataclass
class MovieContentInfo:
    """
    Full content information for a movie.
    
    Attributes:
        title: Movie title
        year: Release year
        imdb_id: IMDb ID (if available)
        dtdd_id: DoesTheDogDie media ID (if available)
        warnings: List of content warnings from IMDb Parents Guide
        triggers: List of trigger warnings from DoesTheDogDie
        fetched_at: When the data was fetched
    """
    title: str
    year: Optional[str] = None
    imdb_id: Optional[str] = None
    dtdd_id: Optional[int] = None
    warnings: List[ContentWarning] = field(default_factory=list)
    triggers: List[TriggerWarning] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()
    
    def get_severity(self, category: ContentCategory) -> Severity:
        """Get severity for a specific category."""
        for warning in self.warnings:
            if warning.category == category:
                return warning.severity
        return Severity.UNKNOWN
    
    def has_trigger(self, topic_keyword: str) -> bool:
        """Check if movie has a specific trigger (by keyword)."""
        keyword_lower = topic_keyword.lower()
        for trigger in self.triggers:
            if keyword_lower in trigger.topic.lower() and trigger.is_present:
                return True
        return False
    
    @property
    def max_severity(self) -> Severity:
        """Get the highest severity across all categories."""
        severity_order = [Severity.NONE, Severity.MILD, Severity.MODERATE, Severity.SEVERE]
        max_sev = Severity.NONE
        for warning in self.warnings:
            if warning.severity in severity_order:
                if severity_order.index(warning.severity) > severity_order.index(max_sev):
                    max_sev = warning.severity
        return max_sev
    
    def summary(self) -> str:
        """Generate a brief summary of content warnings."""
        parts = []
        for warning in self.warnings:
            if warning.severity != Severity.NONE:
                cat_name = warning.category.value.replace("_", " ").title()
                parts.append(f"{cat_name}: {warning.severity.value.title()}")
        return " | ".join(parts) if parts else "No significant content warnings"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization/caching."""
        return {
            "title": self.title,
            "year": self.year,
            "imdb_id": self.imdb_id,
            "dtdd_id": self.dtdd_id,
            "warnings": [w.to_dict() for w in self.warnings],
            "triggers": [t.to_dict() for t in self.triggers],
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MovieContentInfo":
        """Create from dictionary (e.g., from cache)."""
        fetched_at = None
        if data.get("fetched_at"):
            try:
                fetched_at = datetime.fromisoformat(data["fetched_at"])
            except ValueError:
                pass
        
        return cls(
            title=data.get("title", "Unknown"),
            year=data.get("year"),
            imdb_id=data.get("imdb_id"),
            dtdd_id=data.get("dtdd_id"),
            warnings=[ContentWarning.from_dict(w) for w in data.get("warnings", [])],
            triggers=[TriggerWarning.from_dict(t) for t in data.get("triggers", [])],
            fetched_at=fetched_at
        )
