"""
Context-aware profanity detection using LLM.

Reduces false positives by checking whether profanity is genuine swearing
vs quoted/discussed content (song lyrics, movie titles, educational context).

Supports multiple LLM providers:
- Ollama (local, free)
- Anthropic (Claude API)
- OpenAI (GPT API)
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContextResult:
    """Result of context analysis."""
    should_censor: bool
    reason: str
    confidence: float = 1.0


class LLMProvider(ABC):
    """Abstract base for LLM providers."""
    
    @abstractmethod
    def analyze(self, word: str, context: str) -> ContextResult:
        """Analyze if profanity should be censored based on context."""
        pass


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama."""
    
    def __init__(self, model: str = "llama3.2:3b", timeout: int = 5):
        self.model = model
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client()
            except ImportError:
                raise RuntimeError("ollama package not installed. Run: pip install ollama")
        return self._client
    
    def analyze(self, word: str, context: str) -> ContextResult:
        prompt = self._build_prompt(word, context)
        
        try:
            client = self._get_client()
            response = client.generate(
                model=self.model,
                prompt=prompt,
                options={"num_predict": 20}
            )
            
            result_text = response.get('response', '').strip().upper()
            should_censor = result_text.startswith('CENSOR')
            
            return ContextResult(
                should_censor=should_censor,
                reason=f"LLM response: {result_text[:50]}",
                confidence=0.8
            )
            
        except Exception as e:
            logger.warning(f"Ollama analysis failed: {e}. Defaulting to censor.")
            return ContextResult(should_censor=True, reason=f"LLM error: {e}")
    
    def _build_prompt(self, word: str, context: str) -> str:
        return f"""You are a content moderation assistant. Determine if this profanity should be censored.

Context: "{context}"
Detected word: "{word}"

Should censor if: genuine swearing, insults, explicit intent
Should NOT censor if: quoting someone, song lyrics, educational discussion, sarcasm, movie title, character names

Respond with only: CENSOR or SKIP"""


class AnthropicProvider(LLMProvider):
    """Claude API via Anthropic."""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307", timeout: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        return self._client
    
    def analyze(self, word: str, context: str) -> ContextResult:
        prompt = self._build_prompt(word, context)
        
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text.strip().upper()
            should_censor = result_text.startswith('CENSOR')
            
            return ContextResult(
                should_censor=should_censor,
                reason=f"Claude: {result_text[:50]}",
                confidence=0.9
            )
            
        except Exception as e:
            logger.warning(f"Anthropic analysis failed: {e}. Defaulting to censor.")
            return ContextResult(should_censor=True, reason=f"API error: {e}")
    
    def _build_prompt(self, word: str, context: str) -> str:
        return f"""Determine if this profanity should be censored.

Context: "{context}"
Detected word: "{word}"

Censor if: genuine swearing, insults, explicit intent
Skip if: quoting someone, song lyrics, educational discussion, sarcasm, movie title

Respond with only: CENSOR or SKIP"""


class OpenAIProvider(LLMProvider):
    """GPT API via OpenAI."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("openai package not installed. Run: pip install openai")
        return self._client
    
    def analyze(self, word: str, context: str) -> ContextResult:
        prompt = self._build_prompt(word, context)
        
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.choices[0].message.content.strip().upper()
            should_censor = result_text.startswith('CENSOR')
            
            return ContextResult(
                should_censor=should_censor,
                reason=f"GPT: {result_text[:50]}",
                confidence=0.9
            )
            
        except Exception as e:
            logger.warning(f"OpenAI analysis failed: {e}. Defaulting to censor.")
            return ContextResult(should_censor=True, reason=f"API error: {e}")
    
    def _build_prompt(self, word: str, context: str) -> str:
        return f"""Determine if this profanity should be censored.

Context: "{context}"
Detected word: "{word}"

Censor if: genuine swearing, insults
Skip if: quoting, lyrics, educational, sarcasm, movie title

Respond: CENSOR or SKIP"""


class ContextAnalyzer:
    """
    Analyzes profanity context to reduce false positives.
    
    Uses LLM to determine if detected profanity is:
    - Genuine swearing → should censor
    - Quoted/discussed → should skip
    """
    
    def __init__(
        self,
        provider: str = "ollama",
        model: Optional[str] = None,
        api_key: str = "",
        timeout: int = 5,
        enabled: bool = True
    ):
        self.enabled = enabled
        self.provider_name = provider
        self._provider: Optional[LLMProvider] = None
        
        if enabled:
            self._provider = self._create_provider(provider, model, api_key, timeout)
    
    def _create_provider(
        self,
        provider: str,
        model: Optional[str],
        api_key: str,
        timeout: int
    ) -> LLMProvider:
        if provider == "ollama":
            return OllamaProvider(
                model=model or "llama3.2:3b",
                timeout=timeout
            )
        elif provider == "anthropic":
            if not api_key:
                raise ValueError("Anthropic provider requires api_key")
            return AnthropicProvider(
                api_key=api_key,
                model=model or "claude-3-haiku-20240307",
                timeout=timeout
            )
        elif provider == "openai":
            if not api_key:
                raise ValueError("OpenAI provider requires api_key")
            return OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4o-mini",
                timeout=timeout
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    
    def should_censor(self, word: str, context: str) -> Tuple[bool, str]:
        """
        Analyze if profanity should be censored based on context.
        
        Args:
            word: The detected profanity word
            context: Surrounding transcript text (±10 words)
            
        Returns:
            Tuple of (should_censor: bool, reason: str)
        """
        if not self.enabled or self._provider is None:
            return (True, "Context analysis disabled")
        
        result = self._provider.analyze(word, context)
        return (result.should_censor, result.reason)
    
    def analyze_batch(
        self,
        detections: list,
        transcript_words: list,
        context_window: int = 10
    ) -> list:
        """
        Analyze multiple detections and filter based on context.
        
        Args:
            detections: List of profanity detection dicts with 'word' and 'start' keys
            transcript_words: List of WordTimestamp objects (full transcript)
            context_window: Number of words to include on each side
            
        Returns:
            Filtered list of detections (only those that should be censored)
        """
        if not self.enabled:
            return detections
        
        filtered = []
        for detection in detections:
            word = detection.get('word', '')
            start_time = detection.get('start', 0)
            
            # Extract context
            context = self._extract_context(transcript_words, start_time, context_window)
            
            should_censor, reason = self.should_censor(word, context)
            
            if should_censor:
                filtered.append(detection)
            else:
                logger.info(f"Skipping '{word}' at {start_time:.1f}s: {reason}")
        
        return filtered
    
    def _extract_context(
        self,
        words: list,
        target_time: float,
        window: int
    ) -> str:
        """Extract surrounding words for context."""
        # Find words near target time
        target_idx = None
        for i, w in enumerate(words):
            if hasattr(w, 'start') and abs(w.start - target_time) < 0.5:
                target_idx = i
                break
        
        if target_idx is None:
            return ""
        
        start_idx = max(0, target_idx - window)
        end_idx = min(len(words), target_idx + window + 1)
        
        context_words = []
        for w in words[start_idx:end_idx]:
            if hasattr(w, 'word'):
                context_words.append(w.word)
            elif isinstance(w, str):
                context_words.append(w)
        
        return ' '.join(context_words)
