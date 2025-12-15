"""
Semantic sexual content detection using sentence transformers.

Uses embeddings to detect sexual content based on semantic similarity,
catching euphemisms, slang, and implied content that keyword matching misses.

This module is optional - it gracefully handles missing dependencies.
Install with: pip install sentence-transformers
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Check if sentence-transformers is available
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer, util
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.debug("sentence-transformers not installed. Semantic detection disabled.")
    SentenceTransformer = None
    util = None
    np = None


# Pre-defined exemplar phrases for semantic matching
# These represent clearly sexual content that we want to detect
SEXUAL_CONTENT_EXEMPLARS = [
    # Explicit pornography references
    "he was watching pornography on his laptop",
    "she found him looking at porn videos",
    "they were browsing adult content online",
    "downloading explicit videos from the internet",
    
    # Sexual acts - explicit
    "they started having sex in the bedroom",
    "he was masturbating alone in his room",
    "she gave him oral sex",
    "they had intercourse for the first time",
    "he was pleasuring himself",
    
    # Nude/explicit imagery
    "she sent him nude pictures",
    "he took naked photos of her",
    "explicit sexual images were found",
    "sending sexually explicit messages",
    
    # Sexual solicitation
    "hiring an escort for the night",
    "paying for sexual services",
    "looking for a one night stand",
    "seeking casual sexual encounters",
    
    # Adult content platforms
    "subscribing to her OnlyFans account",
    "watching cam girls online",
    "visiting strip clubs regularly",
]

# Safe/innocent exemplars to help distinguish context
SAFE_CONTENT_EXEMPLARS = [
    # Medical context
    "the doctor examined the patient's chest",
    "discussing reproductive health in biology class",
    "the nurse performed a physical examination",
    
    # News/crime reporting
    "police arrested the suspect for assault",
    "the court sentenced the convicted criminal",
    "investigating allegations of misconduct",
    
    # Innocent uses of potentially flagged words
    "this movie really sucks",
    "the vacuum cleaner is broken",
    "the police escort arrived",
    "she turned on the lights",
    "licking an ice cream cone",
    "playing with the tennis balls",
]


@dataclass
class SemanticMatch:
    """Result from semantic similarity matching."""
    text: str
    score: float  # 0.0 to 1.0 similarity score
    matched_exemplar: str  # Which exemplar it matched
    is_safe_match: bool = False  # True if matched safe exemplar instead


@dataclass
class SemanticAnalysis:
    """Complete semantic analysis of a text segment."""
    text: str
    sexual_score: float = 0.0  # Max similarity to sexual exemplars
    safe_score: float = 0.0  # Max similarity to safe exemplars
    top_matches: List[SemanticMatch] = field(default_factory=list)
    
    @property 
    def net_score(self) -> float:
        """Net score after subtracting safe similarity."""
        return max(0.0, self.sexual_score - (self.safe_score * 0.5))
    
    @property
    def is_sexual(self) -> bool:
        """Whether this segment is likely sexual content."""
        # Must have meaningful sexual similarity AND not be primarily safe
        return self.sexual_score > 0.5 and self.net_score > 0.3
    
    @property
    def confidence(self) -> float:
        """Confidence score from 0.0 to 1.0."""
        if not self.is_sexual:
            return 0.0
        return min(1.0, self.net_score)


class SemanticSexualDetector:
    """
    Detects sexual content using semantic similarity with sentence transformers.
    
    Uses a pre-trained sentence transformer model to compare input text against
    known exemplars of sexual and safe content. This catches euphemisms, slang,
    and implied content that keyword matching would miss.
    """
    
    # Default model - small, fast, good accuracy
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        sexual_exemplars: Optional[List[str]] = None,
        safe_exemplars: Optional[List[str]] = None,
        threshold: float = 0.5,
        cache_embeddings: bool = True,
        device: str = "cpu"
    ):
        """
        Initialize the semantic detector.
        
        Args:
            model_name: Sentence transformer model to use
            sexual_exemplars: Custom exemplar phrases for sexual content
            safe_exemplars: Custom exemplar phrases for safe content
            threshold: Minimum similarity score to consider a match
            cache_embeddings: Whether to cache computed embeddings
            device: Device to run model on ("cpu" or "cuda")
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.threshold = threshold
        self.cache_embeddings = cache_embeddings
        self._embedding_cache: Dict[str, Any] = {}
        
        # Load model
        logger.info(f"Loading sentence transformer model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        
        # Set up exemplars
        self.sexual_exemplars = sexual_exemplars or SEXUAL_CONTENT_EXEMPLARS
        self.safe_exemplars = safe_exemplars or SAFE_CONTENT_EXEMPLARS
        
        # Pre-compute exemplar embeddings
        logger.info(f"Computing embeddings for {len(self.sexual_exemplars)} sexual exemplars")
        self.sexual_embeddings = self.model.encode(
            self.sexual_exemplars, 
            convert_to_tensor=True,
            show_progress_bar=False
        )
        
        logger.info(f"Computing embeddings for {len(self.safe_exemplars)} safe exemplars")
        self.safe_embeddings = self.model.encode(
            self.safe_exemplars,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        
        logger.info("Semantic detector initialized")
    
    def _get_embedding(self, text: str):
        """Get embedding for text, using cache if available."""
        if self.cache_embeddings and text in self._embedding_cache:
            return self._embedding_cache[text]
        
        embedding = self.model.encode(text, convert_to_tensor=True)
        
        if self.cache_embeddings:
            self._embedding_cache[text] = embedding
        
        return embedding
    
    def analyze(self, text: str) -> SemanticAnalysis:
        """
        Analyze text for semantic similarity to sexual content.
        
        Args:
            text: Text segment to analyze
            
        Returns:
            SemanticAnalysis with scores and matches
        """
        if not text.strip():
            return SemanticAnalysis(text=text)
        
        # Get embedding for input text
        text_embedding = self._get_embedding(text)
        
        # Compute similarities
        sexual_similarities = util.cos_sim(text_embedding, self.sexual_embeddings)[0]
        safe_similarities = util.cos_sim(text_embedding, self.safe_embeddings)[0]
        
        # Get max scores
        sexual_score = float(sexual_similarities.max())
        safe_score = float(safe_similarities.max())
        
        # Build top matches
        top_matches = []
        
        # Top sexual matches
        sexual_indices = sexual_similarities.argsort(descending=True)[:3]
        for idx in sexual_indices:
            score = float(sexual_similarities[idx])
            if score >= self.threshold:
                top_matches.append(SemanticMatch(
                    text=text,
                    score=score,
                    matched_exemplar=self.sexual_exemplars[idx],
                    is_safe_match=False
                ))
        
        # Top safe matches (if significant)
        safe_indices = safe_similarities.argsort(descending=True)[:2]
        for idx in safe_indices:
            score = float(safe_similarities[idx])
            if score >= self.threshold:
                top_matches.append(SemanticMatch(
                    text=text,
                    score=score,
                    matched_exemplar=self.safe_exemplars[idx],
                    is_safe_match=True
                ))
        
        return SemanticAnalysis(
            text=text,
            sexual_score=sexual_score,
            safe_score=safe_score,
            top_matches=top_matches
        )
    
    def is_sexual_content(self, text: str) -> Tuple[bool, float]:
        """
        Quick check if text is sexual content.
        
        Args:
            text: Text to check
            
        Returns:
            Tuple of (is_sexual, confidence)
        """
        analysis = self.analyze(text)
        return analysis.is_sexual, analysis.confidence
    
    def analyze_batch(self, texts: List[str]) -> List[SemanticAnalysis]:
        """
        Analyze multiple texts efficiently in batch.
        
        Args:
            texts: List of text segments
            
        Returns:
            List of SemanticAnalysis results
        """
        if not texts:
            return []
        
        # Batch encode all texts
        text_embeddings = self.model.encode(
            texts,
            convert_to_tensor=True,
            show_progress_bar=False,
            batch_size=32
        )
        
        results = []
        for i, text in enumerate(texts):
            text_embedding = text_embeddings[i]
            
            sexual_similarities = util.cos_sim(text_embedding, self.sexual_embeddings)[0]
            safe_similarities = util.cos_sim(text_embedding, self.safe_embeddings)[0]
            
            sexual_score = float(sexual_similarities.max())
            safe_score = float(safe_similarities.max())
            
            # Build matches for high scores only
            top_matches = []
            if sexual_score >= self.threshold:
                best_idx = int(sexual_similarities.argmax())
                top_matches.append(SemanticMatch(
                    text=text,
                    score=sexual_score,
                    matched_exemplar=self.sexual_exemplars[best_idx],
                    is_safe_match=False
                ))
            
            results.append(SemanticAnalysis(
                text=text,
                sexual_score=sexual_score,
                safe_score=safe_score,
                top_matches=top_matches
            ))
        
        return results
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()


def is_semantic_detection_available() -> bool:
    """Check if semantic detection is available."""
    return SENTENCE_TRANSFORMERS_AVAILABLE


def get_semantic_detector(
    model_name: str = SemanticSexualDetector.DEFAULT_MODEL,
    **kwargs
) -> Optional[SemanticSexualDetector]:
    """
    Get a semantic detector instance, or None if unavailable.
    
    Args:
        model_name: Model to use
        **kwargs: Additional arguments for SemanticSexualDetector
        
    Returns:
        SemanticSexualDetector instance or None
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        logger.warning(
            "Semantic detection requested but sentence-transformers not installed. "
            "Install with: pip install sentence-transformers"
        )
        return None
    
    try:
        return SemanticSexualDetector(model_name=model_name, **kwargs)
    except Exception as e:
        logger.error(f"Failed to initialize semantic detector: {e}")
        return None
