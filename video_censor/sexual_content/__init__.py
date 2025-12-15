"""Sexual content detection subpackage."""

from .lexicon import (
    load_sexual_terms,
    load_sexual_phrases,
    DEFAULT_SEXUAL_TERMS,
    DEFAULT_SEXUAL_PHRASES,
    CATEGORY_PORNOGRAPHY,
    CATEGORY_SEXUAL_ACTS,
    CATEGORY_SEXUAL_BODY_PARTS,
    CATEGORY_MINORS_UNSAFE,
    # Phase 1 additions
    CONTEXT_MODIFIERS,
    SAFE_CONTEXT_PATTERNS,
    DEFAULT_SEXUAL_PATTERNS,
    RegexPattern,
    check_context_modifiers,
    calculate_safe_context_modifier,
)
from .detector import (
    detect_sexual_content,
    SexualContentDetector,
    SexualContentMatch,
    SegmentScore,
)

# Phase 2: Semantic detection (optional - requires sentence-transformers)
from .semantic_detector import (
    is_semantic_detection_available,
    get_semantic_detector,
    SemanticSexualDetector,
    SemanticAnalysis,
    SemanticMatch,
    SEXUAL_CONTENT_EXEMPLARS,
    SAFE_CONTENT_EXEMPLARS,
)

# Phase 2: Hybrid detection
from .hybrid_detector import (
    HybridSexualContentDetector,
    HybridSegmentScore,
    detect_sexual_content_hybrid,
)

# Phase 2: Multimodal fusion
from .multimodal_fusion import (
    MultimodalFusion,
    FusedSegment,
    ModalityScore,
    Modality,
    fuse_multimodal_detections,
)

__all__ = [
    # Lexicon
    'load_sexual_terms',
    'load_sexual_phrases',
    'DEFAULT_SEXUAL_TERMS',
    'DEFAULT_SEXUAL_PHRASES',
    'CATEGORY_PORNOGRAPHY',
    'CATEGORY_SEXUAL_ACTS', 
    'CATEGORY_SEXUAL_BODY_PARTS',
    'CATEGORY_MINORS_UNSAFE',
    
    # Phase 1: Basic detection
    'detect_sexual_content',
    'SexualContentDetector',
    'SexualContentMatch',
    'SegmentScore',
    
    # Phase 1: Context modifiers
    'CONTEXT_MODIFIERS',
    'SAFE_CONTEXT_PATTERNS',
    'DEFAULT_SEXUAL_PATTERNS',
    'RegexPattern',
    'check_context_modifiers',
    'calculate_safe_context_modifier',
    
    # Phase 2: Semantic detection
    'is_semantic_detection_available',
    'get_semantic_detector',
    'SemanticSexualDetector',
    'SemanticAnalysis',
    'SemanticMatch',
    'SEXUAL_CONTENT_EXEMPLARS',
    'SAFE_CONTENT_EXEMPLARS',
    
    # Phase 2: Hybrid detection
    'HybridSexualContentDetector',
    'HybridSegmentScore',
    'detect_sexual_content_hybrid',
    
    # Phase 2: Multimodal fusion
    'MultimodalFusion',
    'FusedSegment',
    'ModalityScore',
    'Modality',
    'fuse_multimodal_detections',
    
    # Phase 3: ONNX optimization
    'is_onnx_available',
    'get_onnx_detector',
    'ONNXSemanticDetector',
    'ONNXBenchmark',
    'clear_onnx_cache',
]

# Phase 3: ONNX optimization (optional)
from .onnx_optimizer import (
    is_onnx_available,
    get_onnx_detector,
    ONNXSemanticDetector,
    ONNXBenchmark,
    clear_onnx_cache,
)


