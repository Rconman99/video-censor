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
