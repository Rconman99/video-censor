"""
Unit tests for content lookup module.

Tests IMDb Parents Guide scraping and DoesTheDogDie API client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from video_censor.content_lookup import (
    IMDbClient,
    DoesTheDogDieClient,
    MovieContentInfo,
    MovieSearchResult,
    ContentWarning,
    TriggerWarning,
    Severity,
    ContentCategory
)


class TestModels:
    """Test data model classes."""
    
    def test_severity_from_string(self):
        """Test severity parsing from strings."""
        assert Severity.from_string("none") == Severity.NONE
        assert Severity.from_string("MILD") == Severity.MILD
        assert Severity.from_string("Moderate") == Severity.MODERATE
        assert Severity.from_string("severe") == Severity.SEVERE
        assert Severity.from_string("unknown_value") == Severity.UNKNOWN
    
    def test_severity_color(self):
        """Test severity color properties."""
        assert Severity.NONE.color == "#4ade80"  # Green
        assert Severity.SEVERE.color == "#ef4444"  # Red
    
    def test_content_warning_to_dict(self):
        """Test ContentWarning serialization."""
        warning = ContentWarning(
            category=ContentCategory.SEX_NUDITY,
            severity=Severity.MODERATE,
            descriptions=["Some description"],
            vote_count=100
        )
        data = warning.to_dict()
        
        assert data["category"] == "sex_nudity"
        assert data["severity"] == "moderate"
        assert data["descriptions"] == ["Some description"]
    
    def test_trigger_warning_confidence(self):
        """Test trigger warning confidence calculation."""
        trigger = TriggerWarning(
            topic="a dog dies",
            is_present=True,
            yes_votes=90,
            no_votes=10
        )
        assert trigger.confidence == 0.9
        
        trigger_no = TriggerWarning(
            topic="something happens",
            is_present=False,
            yes_votes=20,
            no_votes=80
        )
        assert trigger_no.confidence == 0.8
    
    def test_movie_content_info_max_severity(self):
        """Test finding max severity across warnings."""
        info = MovieContentInfo(
            title="Test Movie",
            warnings=[
                ContentWarning(ContentCategory.PROFANITY, Severity.MILD),
                ContentWarning(ContentCategory.VIOLENCE_GORE, Severity.SEVERE),
                ContentWarning(ContentCategory.SEX_NUDITY, Severity.MODERATE),
            ]
        )
        assert info.max_severity == Severity.SEVERE
    
    def test_movie_content_info_summary(self):
        """Test summary generation."""
        info = MovieContentInfo(
            title="Test Movie",
            warnings=[
                ContentWarning(ContentCategory.PROFANITY, Severity.MILD),
                ContentWarning(ContentCategory.SEX_NUDITY, Severity.NONE),
            ]
        )
        summary = info.summary()
        assert "Profanity" in summary
        assert "Mild" in summary
        # NONE severity should not appear
        assert "Sex" not in summary or "None" not in summary


class TestIMDbClient:
    """Test IMDb client scraping."""
    
    def test_extract_imdb_id(self):
        """Test IMDb ID extraction from URLs."""
        client = IMDbClient()
        
        assert client._extract_imdb_id("/title/tt1234567/") == "tt1234567"
        assert client._extract_imdb_id("https://www.imdb.com/title/tt9876543/parentalguide") == "tt9876543"
        assert client._extract_imdb_id("no-id-here") is None
    
    @patch('video_censor.content_lookup.imdb_client.requests.Session')
    def test_search_movie_error_handling(self, mock_session_class):
        """Test error handling in search."""
        import requests
        
        mock_session = Mock()
        mock_session.headers = {}
        mock_session.get.side_effect = requests.RequestException("Network error")
        mock_session_class.return_value = mock_session
        
        # Create client - it will use the mocked Session
        client = IMDbClient()
        
        results = client.search_movie("Test Movie")
        assert results == []


class TestDoesTheDogDieClient:
    """Test DoesTheDogDie API client."""
    
    def test_is_configured(self):
        """Test API key configuration check."""
        client_with_key = DoesTheDogDieClient("test_api_key")
        assert client_with_key.is_configured is True
        
        client_no_key = DoesTheDogDieClient("")
        assert client_no_key.is_configured is False
    
    @patch('video_censor.content_lookup.dtdd_client.requests.Session')
    def test_search_movie_success(self, mock_session_class):
        """Test successful movie search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": 12345,
                    "name": "Test Movie",
                    "releaseYear": "2020",
                    "itemType": {"name": "Movie"},
                    "posterImage": "test.jpg"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.headers = {}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = DoesTheDogDieClient("test_key")
        client.session = mock_session
        
        results = client.search_movie("Test Movie")
        
        assert len(results) == 1
        assert results[0].title == "Test Movie"
        assert results[0].id == "12345"
        assert results[0].source == "dtdd"
    
    @patch('video_censor.content_lookup.dtdd_client.requests.Session')
    def test_get_triggers(self, mock_session_class):
        """Test trigger fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "topicItemStats": [
                {
                    "topic": {"name": "a dog dies", "isSpoiler": False},
                    "yesSum": 50,
                    "noSum": 5,
                    "comments": [{"comment": "Yes the dog dies"}]
                },
                {
                    "topic": {"name": "there is nudity", "isSpoiler": False},
                    "yesSum": 10,
                    "noSum": 40
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.headers = {}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = DoesTheDogDieClient("test_key")
        client.session = mock_session
        
        triggers = client.get_triggers(12345)
        
        assert len(triggers) == 2
        assert triggers[0].topic == "a dog dies"
        assert triggers[0].is_present is True
        assert triggers[0].yes_votes == 50
        assert triggers[1].is_present is False
    
    def test_search_without_api_key(self):
        """Test that search returns empty without API key."""
        client = DoesTheDogDieClient("")
        
        results = client.search_movie("Test Movie")
        assert results == []

        
class TestMovieContentInfoSerialization:
    """Test serialization and deserialization."""
    
    def test_round_trip(self):
        """Test to_dict and from_dict preserve data."""
        original = MovieContentInfo(
            title="The Matrix",
            year="1999",
            imdb_id="tt0133093",
            dtdd_id=10752,
            warnings=[
                ContentWarning(
                    category=ContentCategory.VIOLENCE_GORE,
                    severity=Severity.SEVERE,
                    descriptions=["Lots of action violence"]
                )
            ],
            triggers=[
                TriggerWarning(
                    topic="someone dies",
                    is_present=True,
                    yes_votes=100,
                    no_votes=5,
                    comment="Multiple characters die"
                )
            ]
        )
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = MovieContentInfo.from_dict(data)
        
        assert restored.title == original.title
        assert restored.year == original.year
        assert restored.imdb_id == original.imdb_id
        assert len(restored.warnings) == 1
        assert restored.warnings[0].severity == Severity.SEVERE
        assert len(restored.triggers) == 1
        assert restored.triggers[0].topic == "someone dies"
