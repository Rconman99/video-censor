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
)
from .detector import (
    detect_sexual_content,
    SexualContentDetector,
    SexualContentMatch,
    SegmentScore,
)

__all__ = [
    'load_sexual_terms',
    'load_sexual_phrases',
    'DEFAULT_SEXUAL_TERMS',
    'DEFAULT_SEXUAL_PHRASES',
    'CATEGORY_PORNOGRAPHY',
    'CATEGORY_SEXUAL_ACTS', 
    'CATEGORY_SEXUAL_BODY_PARTS',
    'CATEGORY_MINORS_UNSAFE',
    'detect_sexual_content',
    'SexualContentDetector',
    'SexualContentMatch',
    'SegmentScore',
]
