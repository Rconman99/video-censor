"""
Tests for video_censor/profanity/context_analyzer.py

Tests ContextAnalyzer, individual LLM providers (with mocked clients),
prompt construction, batch analysis, and error/fallback behavior.
"""

from dataclasses import dataclass
from unittest.mock import patch, MagicMock

import pytest

from video_censor.profanity.context_analyzer import (
    ContextResult,
    OllamaProvider,
    AnthropicProvider,
    OpenAIProvider,
    ContextAnalyzer,
)


# ---------------------------------------------------------------------------
# ContextResult dataclass
# ---------------------------------------------------------------------------

class TestContextResult:
    def test_defaults(self):
        r = ContextResult(should_censor=True, reason="test")
        assert r.confidence == 1.0

    def test_custom_confidence(self):
        r = ContextResult(should_censor=False, reason="quoted", confidence=0.5)
        assert r.confidence == 0.5


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    def test_censor_response(self):
        provider = OllamaProvider(model="test", timeout=1)
        mock_client = MagicMock()
        mock_client.generate.return_value = {"response": "CENSOR - genuine swearing"}
        provider._client = mock_client

        result = provider.analyze("damn", "He said damn it!")
        assert result.should_censor is True
        assert result.confidence == 0.8

    def test_skip_response(self):
        provider = OllamaProvider(model="test", timeout=1)
        mock_client = MagicMock()
        mock_client.generate.return_value = {"response": "SKIP - song lyrics"}
        provider._client = mock_client

        result = provider.analyze("hell", "Highway to Hell by AC/DC")
        assert result.should_censor is False

    def test_api_failure_defaults_to_censor(self):
        provider = OllamaProvider(model="test", timeout=1)
        mock_client = MagicMock()
        mock_client.generate.side_effect = ConnectionError("ollama down")
        provider._client = mock_client

        result = provider.analyze("shit", "context")
        assert result.should_censor is True
        assert "error" in result.reason.lower()

    def test_empty_response_does_not_censor(self):
        provider = OllamaProvider(model="test", timeout=1)
        mock_client = MagicMock()
        mock_client.generate.return_value = {"response": ""}
        provider._client = mock_client

        result = provider.analyze("damn", "context")
        assert result.should_censor is False

    def test_missing_import_raises(self):
        provider = OllamaProvider()
        provider._client = None
        with patch.dict("sys.modules", {"ollama": None}):
            with pytest.raises(RuntimeError, match="ollama"):
                provider._get_client()

    def test_prompt_contains_word_and_context(self):
        provider = OllamaProvider()
        prompt = provider._build_prompt("damn", "He said damn")
        assert "damn" in prompt
        assert "He said damn" in prompt
        assert "CENSOR" in prompt
        assert "SKIP" in prompt


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    def test_censor_response(self):
        provider = AnthropicProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="CENSOR")]
        mock_client.messages.create.return_value = mock_response
        provider._client = mock_client

        result = provider.analyze("fuck", "What the fuck?")
        assert result.should_censor is True
        assert result.confidence == 0.9

    def test_skip_response(self):
        provider = AnthropicProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="SKIP - educational")]
        mock_client.messages.create.return_value = mock_response
        provider._client = mock_client

        result = provider.analyze("ass", "the word ass is a donkey")
        assert result.should_censor is False

    def test_api_failure_defaults_to_censor(self):
        provider = AnthropicProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("rate limit")
        provider._client = mock_client

        result = provider.analyze("shit", "context")
        assert result.should_censor is True


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    def test_censor_response(self):
        provider = OpenAIProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="CENSOR"))]
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        result = provider.analyze("bitch", "You bitch!")
        assert result.should_censor is True
        assert result.confidence == 0.9

    def test_skip_response(self):
        provider = OpenAIProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="SKIP"))]
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        result = provider.analyze("hell", "What the hell is going on in this movie?")
        assert result.should_censor is False

    def test_api_failure_defaults_to_censor(self):
        provider = OpenAIProvider(api_key="sk-test", model="test")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("timeout")
        provider._client = mock_client

        result = provider.analyze("word", "context")
        assert result.should_censor is True


# ---------------------------------------------------------------------------
# ContextAnalyzer — initialization
# ---------------------------------------------------------------------------

class TestContextAnalyzerInit:
    def test_disabled_has_no_provider(self):
        ca = ContextAnalyzer(enabled=False)
        assert ca._provider is None

    def test_ollama_default(self):
        ca = ContextAnalyzer(provider="ollama", enabled=True)
        assert isinstance(ca._provider, OllamaProvider)

    def test_anthropic_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            ContextAnalyzer(provider="anthropic", api_key="", enabled=True)

    def test_openai_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            ContextAnalyzer(provider="openai", api_key="", enabled=True)

    def test_anthropic_with_key(self):
        ca = ContextAnalyzer(provider="anthropic", api_key="sk-test", enabled=True)
        assert isinstance(ca._provider, AnthropicProvider)

    def test_openai_with_key(self):
        ca = ContextAnalyzer(provider="openai", api_key="sk-test", enabled=True)
        assert isinstance(ca._provider, OpenAIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            ContextAnalyzer(provider="gemini", enabled=True)

    def test_custom_model_passed(self):
        ca = ContextAnalyzer(provider="ollama", model="mistral:7b", enabled=True)
        assert ca._provider.model == "mistral:7b"


# ---------------------------------------------------------------------------
# ContextAnalyzer — should_censor
# ---------------------------------------------------------------------------

class TestContextAnalyzerShouldCensor:
    def test_disabled_always_censors(self):
        ca = ContextAnalyzer(enabled=False)
        should, reason = ca.should_censor("fuck", "context")
        assert should is True
        assert "disabled" in reason.lower()

    def test_delegates_to_provider(self):
        ca = ContextAnalyzer(provider="ollama", enabled=True)
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = ContextResult(
            should_censor=False, reason="quoted"
        )
        ca._provider = mock_provider

        should, reason = ca.should_censor("damn", "he quoted: damn")
        assert should is False
        assert "quoted" in reason


# ---------------------------------------------------------------------------
# ContextAnalyzer — analyze_batch
# ---------------------------------------------------------------------------

class TestContextAnalyzerBatch:
    def test_disabled_returns_all(self):
        ca = ContextAnalyzer(enabled=False)
        detections = [
            {"word": "damn", "start": 1.0},
            {"word": "hell", "start": 5.0},
        ]
        assert ca.analyze_batch(detections, []) == detections

    def test_filters_based_on_context(self):
        ca = ContextAnalyzer(provider="ollama", enabled=True)
        mock_provider = MagicMock()

        # First call: censor, second call: skip
        mock_provider.analyze.side_effect = [
            ContextResult(should_censor=True, reason="genuine"),
            ContextResult(should_censor=False, reason="quoted"),
        ]
        ca._provider = mock_provider

        detections = [
            {"word": "damn", "start": 1.0},
            {"word": "hell", "start": 5.0},
        ]
        result = ca.analyze_batch(detections, [])
        assert len(result) == 1
        assert result[0]["word"] == "damn"

    def test_extract_context_with_word_objects(self):
        """Test _extract_context with objects that have .start and .word attrs."""
        ca = ContextAnalyzer(enabled=False)

        @dataclass
        class FakeWord:
            word: str
            start: float

        words = [
            FakeWord("the", 0.0),
            FakeWord("damn", 1.0),
            FakeWord("movie", 2.0),
        ]
        context = ca._extract_context(words, target_time=1.0, window=5)
        assert "the" in context
        assert "damn" in context
        assert "movie" in context

    def test_extract_context_no_match(self):
        ca = ContextAnalyzer(enabled=False)
        context = ca._extract_context([], target_time=5.0, window=10)
        assert context == ""

    def test_extract_context_with_strings(self):
        """Words can be plain strings (no .start, so no match)."""
        ca = ContextAnalyzer(enabled=False)
        context = ca._extract_context(["hello", "world"], target_time=0.0, window=5)
        assert context == ""  # no .start attr so no match
