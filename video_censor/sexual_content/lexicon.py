"""
Sexual content lexicon for detecting sexually explicit dialog.

Organized by categories:
- Pornography references
- Sexual acts
- Sexual body parts in explicit context
- Minors/unsafe context (always cut aggressively)

Terms and phrases with category tags for weighted scoring.
"""

import logging
from pathlib import Path
from typing import Set, List, Dict, Tuple

logger = logging.getLogger(__name__)


# Category constants
CATEGORY_PORNOGRAPHY = "pornography"
CATEGORY_SEXUAL_ACTS = "sexual_acts"
CATEGORY_SEXUAL_BODY_PARTS = "sexual_body_parts"
CATEGORY_MINORS_UNSAFE = "minors_unsafe"


# Category weights for scoring (higher = more severe)
CATEGORY_WEIGHTS: Dict[str, float] = {
    CATEGORY_PORNOGRAPHY: 1.0,
    CATEGORY_SEXUAL_ACTS: 1.2,
    CATEGORY_SEXUAL_BODY_PARTS: 0.8,
    CATEGORY_MINORS_UNSAFE: 2.0,  # Always aggressive
}


# Single-word sexual terms with categories
DEFAULT_SEXUAL_TERMS: Dict[str, str] = {
    # Pornography references
    "porn": CATEGORY_PORNOGRAPHY,
    "porno": CATEGORY_PORNOGRAPHY,
    "pornography": CATEGORY_PORNOGRAPHY,
    "pornographic": CATEGORY_PORNOGRAPHY,
    "pron": CATEGORY_PORNOGRAPHY,  # Common misspelling
    "p0rn": CATEGORY_PORNOGRAPHY,
    "pr0n": CATEGORY_PORNOGRAPHY,
    "xxx": CATEGORY_PORNOGRAPHY,
    "nsfw": CATEGORY_PORNOGRAPHY,
    "nudes": CATEGORY_PORNOGRAPHY,
    "nude": CATEGORY_PORNOGRAPHY,
    "nudity": CATEGORY_PORNOGRAPHY,
    "playboy": CATEGORY_PORNOGRAPHY,
    "hustler": CATEGORY_PORNOGRAPHY,
    "penthouse": CATEGORY_PORNOGRAPHY,
    "camgirl": CATEGORY_PORNOGRAPHY,
    "webcam": CATEGORY_PORNOGRAPHY,  # Context-dependent
    "onlyfans": CATEGORY_PORNOGRAPHY,
    "stripper": CATEGORY_PORNOGRAPHY,
    "stripping": CATEGORY_PORNOGRAPHY,
    "striptease": CATEGORY_PORNOGRAPHY,
    "stripclub": CATEGORY_PORNOGRAPHY,
    "topless": CATEGORY_PORNOGRAPHY,
    "sexting": CATEGORY_PORNOGRAPHY,
    "sext": CATEGORY_PORNOGRAPHY,
    
    # Sexual acts
    "sex": CATEGORY_SEXUAL_ACTS,
    "sexual": CATEGORY_SEXUAL_ACTS,
    "sexually": CATEGORY_SEXUAL_ACTS,
    "intercourse": CATEGORY_SEXUAL_ACTS,
    "fornication": CATEGORY_SEXUAL_ACTS,
    "fucking": CATEGORY_SEXUAL_ACTS,  # In sexual context
    "fucked": CATEGORY_SEXUAL_ACTS,
    "blowjob": CATEGORY_SEXUAL_ACTS,
    "blowjobs": CATEGORY_SEXUAL_ACTS,
    "bj": CATEGORY_SEXUAL_ACTS,
    "handjob": CATEGORY_SEXUAL_ACTS,
    "handjobs": CATEGORY_SEXUAL_ACTS,
    "rimjob": CATEGORY_SEXUAL_ACTS,
    "titjob": CATEGORY_SEXUAL_ACTS,
    "footjob": CATEGORY_SEXUAL_ACTS,
    "masturbate": CATEGORY_SEXUAL_ACTS,
    "masturbating": CATEGORY_SEXUAL_ACTS,
    "masturbation": CATEGORY_SEXUAL_ACTS,
    "jacking": CATEGORY_SEXUAL_ACTS,
    "jerkoff": CATEGORY_SEXUAL_ACTS,
    "jerking": CATEGORY_SEXUAL_ACTS,
    "orgasm": CATEGORY_SEXUAL_ACTS,
    "orgasms": CATEGORY_SEXUAL_ACTS,
    "orgasming": CATEGORY_SEXUAL_ACTS,
    "cumming": CATEGORY_SEXUAL_ACTS,
    "cum": CATEGORY_SEXUAL_ACTS,
    "cumshot": CATEGORY_SEXUAL_ACTS,
    "creampie": CATEGORY_SEXUAL_ACTS,
    "anal": CATEGORY_SEXUAL_ACTS,
    "oral": CATEGORY_SEXUAL_ACTS,
    "doggy": CATEGORY_SEXUAL_ACTS,  # Style
    "missionary": CATEGORY_SEXUAL_ACTS,
    "69": CATEGORY_SEXUAL_ACTS,
    "sixtynine": CATEGORY_SEXUAL_ACTS,
    "threesome": CATEGORY_SEXUAL_ACTS,
    "foursome": CATEGORY_SEXUAL_ACTS,
    "gangbang": CATEGORY_SEXUAL_ACTS,
    "orgy": CATEGORY_SEXUAL_ACTS,
    "bondage": CATEGORY_SEXUAL_ACTS,
    "bdsm": CATEGORY_SEXUAL_ACTS,
    "fetish": CATEGORY_SEXUAL_ACTS,
    "kinky": CATEGORY_SEXUAL_ACTS,
    "kink": CATEGORY_SEXUAL_ACTS,
    "dildo": CATEGORY_SEXUAL_ACTS,
    "vibrator": CATEGORY_SEXUAL_ACTS,
    "hooking": CATEGORY_SEXUAL_ACTS,  # "hooking up"
    "hookup": CATEGORY_SEXUAL_ACTS,
    "booty": CATEGORY_SEXUAL_ACTS,  # "booty call"
    "aroused": CATEGORY_SEXUAL_ACTS,
    "horny": CATEGORY_SEXUAL_ACTS,
    "turned": CATEGORY_SEXUAL_ACTS,  # "turned on"
    "erection": CATEGORY_SEXUAL_ACTS,
    "erect": CATEGORY_SEXUAL_ACTS,
    "boner": CATEGORY_SEXUAL_ACTS,
    "hardon": CATEGORY_SEXUAL_ACTS,
    "suck": CATEGORY_SEXUAL_ACTS,  # Context-dependent
    "sucking": CATEGORY_SEXUAL_ACTS,
    "lick": CATEGORY_SEXUAL_ACTS,  # Context-dependent
    "licking": CATEGORY_SEXUAL_ACTS,
    "penetrate": CATEGORY_SEXUAL_ACTS,
    "penetration": CATEGORY_SEXUAL_ACTS,
    "climax": CATEGORY_SEXUAL_ACTS,
    "ejaculate": CATEGORY_SEXUAL_ACTS,
    "ejaculation": CATEGORY_SEXUAL_ACTS,
    "prostitute": CATEGORY_SEXUAL_ACTS,
    "prostitution": CATEGORY_SEXUAL_ACTS,
    "escort": CATEGORY_SEXUAL_ACTS,  # In sexual context
    "whore": CATEGORY_SEXUAL_ACTS,
    "slut": CATEGORY_SEXUAL_ACTS,
    
    # Sexual body parts in explicit context
    "penis": CATEGORY_SEXUAL_BODY_PARTS,
    "penises": CATEGORY_SEXUAL_BODY_PARTS,
    "dick": CATEGORY_SEXUAL_BODY_PARTS,
    "dicks": CATEGORY_SEXUAL_BODY_PARTS,
    "cock": CATEGORY_SEXUAL_BODY_PARTS,
    "cocks": CATEGORY_SEXUAL_BODY_PARTS,
    "vagina": CATEGORY_SEXUAL_BODY_PARTS,
    "vaginas": CATEGORY_SEXUAL_BODY_PARTS,
    "pussy": CATEGORY_SEXUAL_BODY_PARTS,
    "pussies": CATEGORY_SEXUAL_BODY_PARTS,
    "cunt": CATEGORY_SEXUAL_BODY_PARTS,
    "cunts": CATEGORY_SEXUAL_BODY_PARTS,
    "tits": CATEGORY_SEXUAL_BODY_PARTS,
    "titties": CATEGORY_SEXUAL_BODY_PARTS,
    "breasts": CATEGORY_SEXUAL_BODY_PARTS,
    "boobs": CATEGORY_SEXUAL_BODY_PARTS,
    "boobies": CATEGORY_SEXUAL_BODY_PARTS,
    "nipples": CATEGORY_SEXUAL_BODY_PARTS,
    "balls": CATEGORY_SEXUAL_BODY_PARTS,
    "testicles": CATEGORY_SEXUAL_BODY_PARTS,
    "scrotum": CATEGORY_SEXUAL_BODY_PARTS,
    "butthole": CATEGORY_SEXUAL_BODY_PARTS,
    "anus": CATEGORY_SEXUAL_BODY_PARTS,
    "asshole": CATEGORY_SEXUAL_BODY_PARTS,
    "clit": CATEGORY_SEXUAL_BODY_PARTS,
    "clitoris": CATEGORY_SEXUAL_BODY_PARTS,
    "genitals": CATEGORY_SEXUAL_BODY_PARTS,
    "genitalia": CATEGORY_SEXUAL_BODY_PARTS,
    "privates": CATEGORY_SEXUAL_BODY_PARTS,
    
    # Minors/unsafe context - ALWAYS cut aggressively
    "pedophile": CATEGORY_MINORS_UNSAFE,
    "pedophilia": CATEGORY_MINORS_UNSAFE,
    "pedo": CATEGORY_MINORS_UNSAFE,
    "underage": CATEGORY_MINORS_UNSAFE,
    "jailbait": CATEGORY_MINORS_UNSAFE,
    "lolita": CATEGORY_MINORS_UNSAFE,
    "molest": CATEGORY_MINORS_UNSAFE,
    "molesting": CATEGORY_MINORS_UNSAFE,
    "molestation": CATEGORY_MINORS_UNSAFE,
    "molested": CATEGORY_MINORS_UNSAFE,
    "rape": CATEGORY_MINORS_UNSAFE,
    "raped": CATEGORY_MINORS_UNSAFE,
    "raping": CATEGORY_MINORS_UNSAFE,
    "rapist": CATEGORY_MINORS_UNSAFE,
    "incest": CATEGORY_MINORS_UNSAFE,
    "grooming": CATEGORY_MINORS_UNSAFE,
    "child abuse": CATEGORY_MINORS_UNSAFE,
}


# Multi-word phrases with categories
DEFAULT_SEXUAL_PHRASES: List[Tuple[List[str], str]] = [
    # Pornography references
    (["watching", "porn"], CATEGORY_PORNOGRAPHY),
    (["looking", "at", "porn"], CATEGORY_PORNOGRAPHY),
    (["looking", "up", "porn"], CATEGORY_PORNOGRAPHY),
    (["porn", "on", "his"], CATEGORY_PORNOGRAPHY),
    (["porn", "on", "her"], CATEGORY_PORNOGRAPHY),
    (["porn", "on", "the"], CATEGORY_PORNOGRAPHY),
    (["watching", "pornography"], CATEGORY_PORNOGRAPHY),
    (["porn", "site"], CATEGORY_PORNOGRAPHY),
    (["porn", "sites"], CATEGORY_PORNOGRAPHY),
    (["porn", "video"], CATEGORY_PORNOGRAPHY),
    (["porn", "videos"], CATEGORY_PORNOGRAPHY),
    (["adult", "video"], CATEGORY_PORNOGRAPHY),
    (["adult", "videos"], CATEGORY_PORNOGRAPHY),
    (["adult", "website"], CATEGORY_PORNOGRAPHY),
    (["adult", "content"], CATEGORY_PORNOGRAPHY),
    (["explicit", "content"], CATEGORY_PORNOGRAPHY),
    (["explicit", "video"], CATEGORY_PORNOGRAPHY),
    (["explicit", "images"], CATEGORY_PORNOGRAPHY),
    (["nude", "pics"], CATEGORY_PORNOGRAPHY),
    (["nude", "pictures"], CATEGORY_PORNOGRAPHY),
    (["nude", "photos"], CATEGORY_PORNOGRAPHY),
    (["naked", "pictures"], CATEGORY_PORNOGRAPHY),
    (["naked", "pics"], CATEGORY_PORNOGRAPHY),
    (["naked", "photos"], CATEGORY_PORNOGRAPHY),
    (["sending", "nudes"], CATEGORY_PORNOGRAPHY),
    (["send", "nudes"], CATEGORY_PORNOGRAPHY),
    (["sent", "nudes"], CATEGORY_PORNOGRAPHY),
    (["strip", "club"], CATEGORY_PORNOGRAPHY),
    (["strip", "show"], CATEGORY_PORNOGRAPHY),
    (["sex", "tape"], CATEGORY_PORNOGRAPHY),
    (["sex", "video"], CATEGORY_PORNOGRAPHY),
    (["xxx", "video"], CATEGORY_PORNOGRAPHY),
    (["download", "porn"], CATEGORY_PORNOGRAPHY),
    (["streaming", "porn"], CATEGORY_PORNOGRAPHY),
    
    # Sexual acts - clear implications
    (["having", "sex"], CATEGORY_SEXUAL_ACTS),
    (["had", "sex"], CATEGORY_SEXUAL_ACTS),
    (["have", "sex"], CATEGORY_SEXUAL_ACTS),
    (["has", "sex"], CATEGORY_SEXUAL_ACTS),
    (["make", "love"], CATEGORY_SEXUAL_ACTS),
    (["made", "love"], CATEGORY_SEXUAL_ACTS),
    (["making", "love"], CATEGORY_SEXUAL_ACTS),
    (["doing", "it"], CATEGORY_SEXUAL_ACTS),  # Context-sensitive
    (["did", "it"], CATEGORY_SEXUAL_ACTS),
    (["sleeping", "together"], CATEGORY_SEXUAL_ACTS),
    (["slept", "together"], CATEGORY_SEXUAL_ACTS),
    (["sleeping", "with"], CATEGORY_SEXUAL_ACTS),
    (["slept", "with"], CATEGORY_SEXUAL_ACTS),
    (["hooking", "up"], CATEGORY_SEXUAL_ACTS),
    (["hooked", "up"], CATEGORY_SEXUAL_ACTS),
    (["hook", "up"], CATEGORY_SEXUAL_ACTS),
    (["booty", "call"], CATEGORY_SEXUAL_ACTS),
    (["one", "night", "stand"], CATEGORY_SEXUAL_ACTS),
    (["friends", "with", "benefits"], CATEGORY_SEXUAL_ACTS),
    (["fwb"], CATEGORY_SEXUAL_ACTS),
    (["going", "down", "on"], CATEGORY_SEXUAL_ACTS),
    (["went", "down", "on"], CATEGORY_SEXUAL_ACTS),
    (["give", "head"], CATEGORY_SEXUAL_ACTS),
    (["giving", "head"], CATEGORY_SEXUAL_ACTS),
    (["gave", "head"], CATEGORY_SEXUAL_ACTS),
    (["blow", "job"], CATEGORY_SEXUAL_ACTS),
    (["hand", "job"], CATEGORY_SEXUAL_ACTS),
    (["jerk", "off"], CATEGORY_SEXUAL_ACTS),
    (["jerking", "off"], CATEGORY_SEXUAL_ACTS),
    (["jerked", "off"], CATEGORY_SEXUAL_ACTS),
    (["jack", "off"], CATEGORY_SEXUAL_ACTS),
    (["jacking", "off"], CATEGORY_SEXUAL_ACTS),
    (["beat", "off"], CATEGORY_SEXUAL_ACTS),
    (["beating", "off"], CATEGORY_SEXUAL_ACTS),
    (["getting", "off"], CATEGORY_SEXUAL_ACTS),
    (["get", "off"], CATEGORY_SEXUAL_ACTS),
    (["getting", "laid"], CATEGORY_SEXUAL_ACTS),
    (["get", "laid"], CATEGORY_SEXUAL_ACTS),
    (["got", "laid"], CATEGORY_SEXUAL_ACTS),
    (["turned", "on"], CATEGORY_SEXUAL_ACTS),
    (["turn", "on"], CATEGORY_SEXUAL_ACTS),
    (["in", "bed", "together"], CATEGORY_SEXUAL_ACTS),
    (["in", "bed", "with"], CATEGORY_SEXUAL_ACTS),
    (["suck", "my"], CATEGORY_SEXUAL_ACTS),
    (["sucking", "his"], CATEGORY_SEXUAL_ACTS),
    (["sucking", "her"], CATEGORY_SEXUAL_ACTS),
    (["bend", "over"], CATEGORY_SEXUAL_ACTS),  # Context-sensitive
    (["bent", "over"], CATEGORY_SEXUAL_ACTS),
    (["on", "top", "of"], CATEGORY_SEXUAL_ACTS),  # Context-sensitive
    (["inside", "her"], CATEGORY_SEXUAL_ACTS),
    (["inside", "him"], CATEGORY_SEXUAL_ACTS),
    (["come", "on", "her"], CATEGORY_SEXUAL_ACTS),
    (["came", "on", "her"], CATEGORY_SEXUAL_ACTS),
    
    # Explicitly unsafe/minors
    (["sex", "with", "a", "minor"], CATEGORY_MINORS_UNSAFE),
    (["sex", "with", "minors"], CATEGORY_MINORS_UNSAFE),
    (["sex", "with", "children"], CATEGORY_MINORS_UNSAFE),
    (["child", "pornography"], CATEGORY_MINORS_UNSAFE),
    (["child", "porn"], CATEGORY_MINORS_UNSAFE),
    (["child", "abuse"], CATEGORY_MINORS_UNSAFE),
    (["sexual", "abuse"], CATEGORY_MINORS_UNSAFE),
    (["sexually", "abused"], CATEGORY_MINORS_UNSAFE),
    (["sexually", "assaulted"], CATEGORY_MINORS_UNSAFE),
    (["sexual", "assault"], CATEGORY_MINORS_UNSAFE),
]


# =============================================================================
# CONTEXT MODIFIERS - For ambiguous terms that need surrounding word analysis
# =============================================================================
# Format: term -> { "suppress_if": [...], "amplify_if": [...], "require_any": [...] }
# - suppress_if: If any of these words are nearby, suppress the match (score = 0)
# - amplify_if: If any of these words are nearby, amplify the score (weight * 1.5)
# - require_any: Only match if at least one of these words is nearby

CONTEXT_MODIFIERS: Dict[str, Dict[str, List[str]]] = {
    # Words that are commonly used innocently
    "suck": {
        "suppress_if": ["this", "that", "it", "movie", "music", "song", "game", "life", "weather", "vacuum"],
        "amplify_if": ["my", "his", "her", "your", "dick", "cock", "balls"],
    },
    "sucking": {
        "suppress_if": ["up", "thumb", "lollipop", "candy", "straw"],
        "amplify_if": ["dick", "cock", "his", "her", "my"],
    },
    "escort": {
        "suppress_if": ["police", "security", "military", "funeral", "vip", "protection", "convoy"],
        "amplify_if": ["service", "agency", "girl", "hire", "paid"],
    },
    "turned": {
        "suppress_if": ["around", "off", "down", "left", "right", "corner", "away", "lights", "car", "engine"],
        "amplify_if": ["on", "aroused"],
        "require_any": ["on"],  # "turned" alone shouldn't match, only "turned on"
    },
    "licking": {
        "suppress_if": ["ice", "cream", "lollipop", "envelope", "stamp", "wound", "lips", "fingers"],
        "amplify_if": ["pussy", "dick", "cock", "balls"],
    },
    "lick": {
        "suppress_if": ["ice", "cream", "lollipop", "wound", "lips"],
        "amplify_if": ["my", "her", "his"],
    },
    "balls": {
        "suppress_if": ["basket", "soccer", "football", "tennis", "golf", "bowling", "sports", "game", "playing"],
        "amplify_if": ["suck", "lick", "his", "my"],
    },
    "booty": {
        "suppress_if": ["pirate", "treasure", "hunt"],
        "amplify_if": ["call", "shake", "slap", "grab"],
    },
    "doggy": {
        "suppress_if": ["dog", "puppy", "pet", "bag", "paddle"],
        "amplify_if": ["style", "position"],
        "require_any": ["style", "position"],
    },
    "missionary": {
        "suppress_if": ["church", "religious", "christian", "work", "trip"],
        "amplify_if": ["position", "style", "sex"],
    },
    "69": {
        "suppress_if": ["street", "highway", "route", "number", "year", "age", "degrees"],
        "amplify_if": ["position", "do", "did"],
    },
    "oral": {
        "suppress_if": ["exam", "test", "hygiene", "surgeon", "surgery", "health", "care"],
        "amplify_if": ["sex", "pleasure"],
    },
    "come": {
        "suppress_if": ["here", "over", "back", "home", "on", "in", "out", "with"],
        "amplify_if": ["inside", "on her", "on him", "face"],
    },
    "climax": {
        "suppress_if": ["movie", "story", "plot", "book", "scene"],
        "amplify_if": ["sexual", "orgasm", "reached"],
    },
    "kinky": {
        "suppress_if": ["hair", "curly"],
        "amplify_if": ["sex", "stuff", "things", "bedroom"],
    },
    "topless": {
        "suppress_if": ["car", "convertible", "jeep"],
        "amplify_if": ["woman", "girl", "beach", "bar"],
    },
}


# =============================================================================
# SAFE CONTEXT PATTERNS - Suppress matches when in educational/medical/news contexts
# =============================================================================
# Format: (context_words, score_reduction)
# If 2+ context words appear in segment, multiply score by (1.0 - score_reduction)

SAFE_CONTEXT_PATTERNS: List[Tuple[List[str], float]] = [
    # Medical/Educational contexts (reduce score by 70%)
    (["doctor", "medical", "diagnosis", "treatment", "patient", "hospital", "clinic", "nurse"], 0.7),
    (["anatomy", "biology", "education", "reproductive", "health", "class", "textbook", "scientific"], 0.7),
    (["gynecologist", "urologist", "obstetrician", "examination", "checkup"], 0.8),
    
    # News/Reporting contexts (reduce score by 50%)
    (["police", "arrested", "charged", "court", "trial", "investigation", "alleged"], 0.5),
    (["news", "report", "journalist", "documentary", "coverage", "reporter"], 0.5),
    (["victim", "survivor", "assault", "crime", "convicted", "sentenced"], 0.4),
    
    # Religious/Historical contexts (reduce score by 60%)
    (["bible", "scripture", "church", "religious", "sermon", "pastor", "priest"], 0.6),
    (["historical", "ancient", "period", "century", "era", "culture"], 0.5),
    
    # Parenting/Child safety discussions (reduce score by 40%)
    (["parent", "child", "protect", "safety", "warning", "prevent", "teach"], 0.4),
    (["awareness", "education", "prevention", "workshop", "seminar"], 0.5),
]


# =============================================================================
# REGEX PATTERNS - For catching evasion attempts (leetspeak, spacing, etc.)
# =============================================================================
import re
from dataclasses import dataclass as regex_dataclass

@regex_dataclass
class RegexPattern:
    """A regex-based detection rule."""
    pattern: str
    category: str
    weight: float = 1.0
    description: str = ""
    
    def __post_init__(self):
        self._compiled = re.compile(self.pattern, re.IGNORECASE)
    
    def find_matches(self, text: str) -> List[Tuple[int, int, str]]:
        """Return list of (start, end, matched_text) tuples."""
        return [(m.start(), m.end(), m.group()) for m in self._compiled.finditer(text)]


DEFAULT_SEXUAL_PATTERNS: List[RegexPattern] = [
    # Leetspeak variations
    RegexPattern(r"\bp+[o0]+r+n+\w*\b", CATEGORY_PORNOGRAPHY, 1.0, "porn with leetspeak"),
    RegexPattern(r"\bf+[u*]+c+k+\w*\b", CATEGORY_SEXUAL_ACTS, 1.0, "fuck with asterisks"),
    RegexPattern(r"\b[s$5]+[e3]+x+\w*\b", CATEGORY_SEXUAL_ACTS, 1.0, "sex with leetspeak"),
    RegexPattern(r"\bn+[u0]+d+[e3]+[s$5]*\b", CATEGORY_PORNOGRAPHY, 1.0, "nudes with leetspeak"),
    RegexPattern(r"\bc+[o0]+c+k+[s$5]*\b", CATEGORY_SEXUAL_BODY_PARTS, 0.8, "cock with leetspeak"),
    RegexPattern(r"\bd+[i1]+c+k+[s$5]*\b", CATEGORY_SEXUAL_BODY_PARTS, 0.8, "dick with leetspeak"),
    RegexPattern(r"\bp+[u*]+[s$5]+[s$5]+y+\b", CATEGORY_SEXUAL_BODY_PARTS, 0.8, "pussy with leetspeak"),
    RegexPattern(r"\bb+[o0]+[o0]+b+[s$5]*\b", CATEGORY_SEXUAL_BODY_PARTS, 0.8, "boobs with leetspeak"),
    
    # Spaced-out evasion
    RegexPattern(r"\bp\s*o\s*r\s*n\b", CATEGORY_PORNOGRAPHY, 1.2, "spaced p-o-r-n"),
    RegexPattern(r"\bs\s*e\s*x\b", CATEGORY_SEXUAL_ACTS, 1.0, "spaced s-e-x"),
    RegexPattern(r"\bn\s*u\s*d\s*e\s*s?\b", CATEGORY_PORNOGRAPHY, 1.0, "spaced n-u-d-e-s"),
    
    # Multi-word phrase patterns
    RegexPattern(r"\bhaving\s+\w+\s+sex\b", CATEGORY_SEXUAL_ACTS, 1.3, "having ___ sex"),
    RegexPattern(r"\bwatch(ing|ed)?\s+\w*\s*porn\b", CATEGORY_PORNOGRAPHY, 1.2, "watching/watched porn"),
    RegexPattern(r"\bsend(ing|s)?\s+\w*\s*nudes?\b", CATEGORY_PORNOGRAPHY, 1.2, "sending nudes"),
    RegexPattern(r"\bget(ting)?\s+(laid|off|some)\b", CATEGORY_SEXUAL_ACTS, 1.0, "getting laid/off/some"),
    
    # Explicit platform names (newer/less common)
    RegexPattern(r"\b(pornhub|xvideos|xhamster|redtube|youporn)\b", CATEGORY_PORNOGRAPHY, 1.5, "explicit sites"),
    RegexPattern(r"\b(onlyfans|fansly|manyvids)\b", CATEGORY_PORNOGRAPHY, 1.3, "adult creator platforms"),
]


def check_context_modifiers(word: str, context_words: List[str], window: int = 5) -> float:
    """
    Check if a word should be suppressed or amplified based on context.
    
    Args:
        word: The matched term
        context_words: Surrounding words (normalized to lowercase)
        window: Not used (kept for API compatibility)
        
    Returns:
        Score modifier: 0.0 (suppress), 1.0 (normal), 1.5 (amplify)
    """
    modifiers = CONTEXT_MODIFIERS.get(word.lower())
    if not modifiers:
        return 1.0  # No modification rules for this word
    
    context_set = set(w.lower() for w in context_words)
    
    # Check require_any first - if present, word must have at least one
    require_any = modifiers.get("require_any", [])
    if require_any:
        if not any(req in context_set for req in require_any):
            return 0.0  # Required context not found, suppress
    
    # Check suppress_if - any match suppresses
    for suppress in modifiers.get("suppress_if", []):
        if suppress in context_set:
            return 0.0  # Suppress this match
    
    # Check amplify_if - any match amplifies
    for amplify in modifiers.get("amplify_if", []):
        if amplify in context_set:
            return 1.5  # Amplify this match
    
    return 1.0  # Normal score


def calculate_safe_context_modifier(segment_words: List[str], min_matches: int = 2) -> float:
    """
    Calculate score reduction if safe context is detected.
    
    Args:
        segment_words: Words in the segment
        min_matches: Minimum context word matches required
        
    Returns:
        Multiplier (1.0 = no reduction, 0.3 = 70% reduction)
    """
    normalized = set(w.lower() for w in segment_words)
    
    best_reduction = 0.0
    
    for safe_words, reduction in SAFE_CONTEXT_PATTERNS:
        matches = sum(1 for w in safe_words if w in normalized)
        if matches >= min_matches:
            best_reduction = max(best_reduction, reduction)
    
    return 1.0 - best_reduction


def load_sexual_terms(custom_path: str = "") -> Dict[str, str]:
    """
    Load sexual content terms with category mappings.
    
    If a custom path is provided, loads additional terms from file.
    Format: one term per line, optionally followed by | and category.
    Example: 
        porn|pornography
        xxx
    
    Args:
        custom_path: Optional path to custom terms file
        
    Returns:
        Dict mapping terms to categories
    """
    terms = DEFAULT_SEXUAL_TERMS.copy()
    
    if not custom_path:
        logger.info(f"Using default sexual terms ({len(terms)} terms)")
        return terms
    
    path = Path(custom_path)
    if not path.exists():
        logger.warning(f"Custom sexual terms file not found: {path}")
        return terms
    
    try:
        with open(path, 'r') as f:
            custom_count = 0
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '|' in line:
                    term, category = line.split('|', 1)
                    term = term.strip().lower()
                    category = category.strip().lower()
                else:
                    term = line.lower()
                    category = CATEGORY_SEXUAL_ACTS  # Default category
                
                if term and term not in terms:
                    custom_count += 1
                    terms[term] = category
        
        logger.info(f"Loaded sexual terms: {len(terms)} ({custom_count} custom)")
        return terms
        
    except Exception as e:
        logger.warning(f"Failed to load custom sexual terms: {e}")
        return DEFAULT_SEXUAL_TERMS.copy()


def load_sexual_phrases(custom_path: str = "") -> List[Tuple[List[str], str]]:
    """
    Load sexual content phrases with categories.
    
    Custom file format: phrase with words separated by spaces,
    optionally followed by | and category.
    Example:
        watching porn|pornography
        having sex|sexual_acts
    
    Args:
        custom_path: Optional path to custom phrases file
        
    Returns:
        List of (phrase_words, category) tuples
    """
    phrases = list(DEFAULT_SEXUAL_PHRASES)
    
    if not custom_path:
        logger.info(f"Using default sexual phrases ({len(phrases)} phrases)")
        return phrases
    
    path = Path(custom_path)
    if not path.exists():
        logger.warning(f"Custom sexual phrases file not found: {path}")
        return phrases
    
    try:
        with open(path, 'r') as f:
            custom_count = 0
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '|' in line:
                    phrase_part, category = line.split('|', 1)
                    words = phrase_part.strip().lower().split()
                    category = category.strip().lower()
                else:
                    words = line.lower().split()
                    category = CATEGORY_SEXUAL_ACTS
                
                if len(words) >= 2:
                    phrase_tuple = (words, category)
                    if phrase_tuple not in phrases:
                        custom_count += 1
                        phrases.append(phrase_tuple)
        
        logger.info(f"Loaded sexual phrases: {len(phrases)} ({custom_count} custom)")
        return phrases
        
    except Exception as e:
        logger.warning(f"Failed to load custom sexual phrases: {e}")
        return list(DEFAULT_SEXUAL_PHRASES)


def get_category_weight(category: str) -> float:
    """Get the severity weight for a category."""
    return CATEGORY_WEIGHTS.get(category, 1.0)
