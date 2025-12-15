"""
Tests for Community Timestamps feature in cloud_db.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from video_censor.cloud_db import (
    CloudDatabaseClient,
    VideoFingerprint,
    DetectionResult,
    Contributor,
)


class TestCommunityFeatures:
    """Tests for community timestamp features."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with mocked Supabase."""
        client = CloudDatabaseClient()
        client._client = Mock()
        client._initialized = True
        return client
    
    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample video fingerprint."""
        return VideoFingerprint(
            file_hash="abc123def456",
            file_size=1024000,
            duration_seconds=120.5
        )
    
    @pytest.fixture
    def sample_detection(self, sample_fingerprint):
        """Create a sample detection result."""
        return DetectionResult(
            fingerprint=sample_fingerprint,
            title="Test Movie",
            nudity_segments=[{"start": 10.0, "end": 15.0}],
            profanity_segments=[{"start": 5.0, "end": 6.0, "word": "test"}],
            sexual_content_segments=[],
            violence_segments=[],
            settings_used={"threshold": 0.6},
            processing_time_seconds=30.5,
            app_version="2.0.0"
        )
    
    def test_get_device_id_creates_new(self, client):
        """Test that device ID is created if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            device_file = Path(tmpdir) / "device_id"
            
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                # Create .video_censor directory
                (Path(tmpdir) / ".video_censor").mkdir()
                
                device_id = client._get_device_id()
                
                # Should be a valid UUID format
                assert len(device_id) == 36
                assert device_id.count('-') == 4
    
    def test_contributor_dataclass(self):
        """Test Contributor dataclass."""
        contributor = Contributor(
            id="test-uuid",
            device_id="device-uuid",
            trust_score=1.5,
            contribution_count=10,
            helpful_votes=5
        )
        
        assert contributor.id == "test-uuid"
        assert contributor.trust_score == 1.5
        assert contributor.contribution_count == 10
    
    def test_detection_result_with_community_fields(self, sample_fingerprint):
        """Test DetectionResult with community fields."""
        detection = DetectionResult(
            fingerprint=sample_fingerprint,
            title="Test",
            nudity_segments=[],
            profanity_segments=[],
            sexual_content_segments=[],
            violence_segments=[],
            settings_used={},
            processing_time_seconds=10,
            contributor_id="contributor-123",
            upvotes=5,
            downvotes=1,
            quality_score=5.5
        )
        
        assert detection.contributor_id == "contributor-123"
        assert detection.upvotes == 5
        assert detection.quality_score == 5.5
    
    def test_vote_validation(self, client):
        """Test that vote must be +1 or -1."""
        # Invalid votes should return False
        assert client.vote_on_detection("test-id", 0) is False
        assert client.vote_on_detection("test-id", 2) is False
        assert client.vote_on_detection("test-id", -2) is False
    
    def test_get_contributor_stats_structure(self, client):
        """Test get_contributor_stats returns expected structure."""
        # Mock the contributor lookup
        mock_response = Mock()
        mock_response.data = [{
            'id': 'test-id-12345678',
            'device_id': 'device-123',
            'trust_score': 1.5,
            'contribution_count': 10,
            'helpful_votes': 5,
            'created_at': '2024-01-01T00:00:00Z'
        }]
        
        client._client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        # Mock device ID
        with patch.object(client, '_get_device_id', return_value='device-123'):
            stats = client.get_contributor_stats()
        
        assert stats is not None
        assert 'contributor_id' in stats
        assert 'trust_score' in stats
        assert 'contribution_count' in stats
        assert 'helpful_votes' in stats


class TestCommunityConfig:
    """Tests for CommunityConfig."""
    
    def test_default_values(self):
        """Test CommunityConfig default values."""
        from video_censor.config import CommunityConfig
        
        config = CommunityConfig()
        
        assert config.enabled is True
        assert config.auto_lookup is True
        assert config.auto_upload is False  # Safer default
        assert config.min_quality_score == 0.5
        assert config.device_id == ""
    
    def test_config_includes_community(self):
        """Test that main Config includes community field."""
        from video_censor.config import Config
        
        config = Config()
        
        assert hasattr(config, 'community')
        assert config.community.enabled is True
