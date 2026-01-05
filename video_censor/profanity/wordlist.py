"""
Enhanced profanity word list with variants and obfuscations.

Provides comprehensive profanity detection including:
- Common words and their inflections
- Obfuscated versions (f*ck, sh!t)
- Plural and verb forms
- Variant spellings
"""

import logging
import re
from pathlib import Path
from typing import Set, List, Dict

logger = logging.getLogger(__name__)


# Core profanity stems - base forms that will be expanded
PROFANITY_STEMS: Dict[str, List[str]] = {
    # F-word family
    "fuck": ["fuck", "fuk", "fck", "fuq", "phuck", "fvck", "f*ck", "f**k", "fxck"],
    "fucking": ["fucking", "fuking", "fcking", "f*cking", "fukking", "fkin", "effing"],
    "fucker": ["fucker", "fukker", "fcker", "f*cker"],
    "fucked": ["fucked", "fukked", "fcked", "f*cked"],
    
    # S-word family
    "shit": ["shit", "sht", "sh!t", "sh1t", "shyt", "shiit", "sh*t", "s**t"],
    "shitting": ["shitting", "shittin"],
    "shitty": ["shitty", "shitey", "sh!tty"],
    "bullshit": ["bullshit", "bs", "b.s.", "bullsh*t"],
    
    # A-word family
    "ass": ["ass", "azz", "a$$", "a**", "arse"],
    "asshole": ["asshole", "a-hole", "ahole", "a$$hole", "arsehole"],
    "dumbass": ["dumbass", "dumba$$"],
    "jackass": ["jackass", "jacka$$"],
    "badass": ["badass", "bada$$"],
    
    # B-word family
    "bitch": ["bitch", "b!tch", "b*tch", "biatch", "biotch", "beyotch"],
    "bitches": ["bitches", "b!tches"],
    "bitching": ["bitching", "bitchin"],
    
    # D-word family
    "damn": ["damn", "darn", "dam", "dayum"],
    "damned": ["damned", "darned"],
    "dammit": ["dammit", "damnit", "damit"],
    "goddamn": ["goddamn", "goddam", "gd", "g-damn", "god damn"],
    "goddammit": ["goddammit", "goddamnit", "god dammit"],
    
    # Hell
    "hell": ["hell", "heck", "h-e-double-hockey-sticks"],
    
    # Crap
    "crap": ["crap", "cr@p"],
    "crappy": ["crappy", "cr@ppy"],
    
    # Piss
    "piss": ["piss", "p!ss", "pizz"],
    "pissed": ["pissed", "p!ssed", "pist"],
    "pissing": ["pissing", "pissin"],
    
    # Bastard
    "bastard": ["bastard", "b@stard", "bstard"],
    
    # Crude anatomical
    "dick": ["dick", "d!ck", "d*ck", "dik"],
    "dickhead": ["dickhead", "d!ckhead", "dikhead"],
    "cock": ["cock", "c*ck", "c0ck"],
    "pussy": ["pussy", "pu$$y", "puss", "p*ssy"],
    "tits": ["tits", "t!ts", "titties", "tatas"],
    "balls": ["balls", "ballz", "nutz", "nuts"],
    "cunt": ["cunt", "c*nt", "c**t", "cnt"],
    "clit": ["clit", "cl!t", "clitoris"],
    "penis": ["penis", "p3nis"],
    "vagina": ["vagina", "vag"],
    "twat": ["twat", "tw@t"],
    "pecker": ["pecker"],
    "puntang": ["puntang", "poontang", "punani"],
    
    # Whore/slut
    "whore": ["whore", "wh0re", "h0", "ho"],
    "slut": ["slut", "sl*t", "s1ut"],
    
    # Slurs (important to catch)
    "nigger": ["nigger", "n-word", "n*gger", "n**ger", "nig", "n!gger"],
    "nigga": ["nigga", "n*gga", "niqqa"],
    "fag": ["fag", "f@g"],
    "faggot": ["faggot", "f@ggot", "f*ggot"],
    "retard": ["retard", "r*tard", "retart"],
    "retarded": ["retarded", "r*tarded"],
    "spick": ["spick", "spic"],
    "heimy": ["heimy", "heeb", "hymie"],
    "dyke": ["dyke", "d*ke"],
    
    # Other offensive
    "turd": ["turd", "t*rd"],
    "horny": ["horny", "h0rny"],
    "fugly": ["fugly"],
    "douche": ["douche", "douchebag", "douche bag", "d-bag"],
    "wiseass": ["wiseass", "wise ass", "wisea$$"],
}


# Complete expanded set of all profanity words
def _build_profanity_set() -> Set[str]:
    """Build complete set of profanity words from stems and variants."""
    words = set()
    for stem, variants in PROFANITY_STEMS.items():
        words.add(stem)
        words.update(variants)
    
    # Add additional standalone terms
    additional = {
        # Forms not covered by stems
        "fucks", "fuckers", "fuckface", "fuckhead", "fuckwit", "clusterfuck",
        "motherfucker", "motherfucking", "mf", "mofo", "milf",
        "shits", "shithead", "shitface", "dipshit", "horseshit", "apeshit",
        "asses", "assholes", "asshat", "assclown", "asswipe",
        "bitchy", "sonofabitch", "sob",
        "dicks", "cocks", "dickweed",
        "cunts",
        "pussies", "pussycat",
        "whores", "sluts", "slutty",
        "damning",
        "bastards",
        "pimp", "pimping",
        "screw", "screwing", "screwed",
        "cocks", "cocky", "cocksucker",
        
        # Religious exclamations
        "jesus", "christ", "jesuschrist", "god", "oh my god", "omg",
        "goddamnit", "godforsaken",
        
        # Racial/ethnic slurs
        "niggers", "niggas", "wetback", "spic", "chink", "gook", "kike",
        "beaner", "cracker", "honky",
        
        # LGBTQ slurs
        "fags", "faggots", "dyke", "tranny", "queer",
        
        # Other offensive
        "retards", "spaz", "spastic",
        
        # Crude terms
        "jerk", "jerkoff", "wanker", "wank", "tosser",
        "butthole", "butthead", "buttface",
        "boob", "boobs", "boobie", "boobies",
        "boner", "hardon", "erection",
        "cum", "cumming", "jizz", "spunk",
        
        # Abbreviations
        "wtf", "stfu", "gtfo", "lmfao", "lmao",
    }
    words.update(additional)
    
    return {w.lower() for w in words}


DEFAULT_PROFANITY: Set[str] = _build_profanity_set()


# Extended phrase list
DEFAULT_PHRASES: List[List[str]] = [
    # F-word phrases
    ["what", "the", "fuck"],
    ["what", "the", "f"],
    ["the", "fuck"],
    ["as", "fuck"],
    ["holy", "fuck"],
    ["fuck", "you"],
    ["fuck", "off"],
    ["fuck", "this"],
    ["fuck", "that"],
    ["fucked", "up"],
    ["fucking", "hell"],
    ["shut", "the", "fuck", "up"],
    ["get", "the", "fuck"],
    ["who", "the", "fuck"],
    ["why", "the", "fuck"],
    ["how", "the", "fuck"],
    ["where", "the", "fuck"],
    
    # Mother variants
    ["mother", "fucker"],
    ["mother", "fucking"],
    ["mutha", "fucka"],
    
    # S-word phrases
    ["holy", "shit"],
    ["oh", "shit"],
    ["no", "shit"],
    ["piece", "of", "shit"],
    ["bull", "shit"],
    ["horse", "shit"],
    ["ape", "shit"],
    ["dip", "shit"],
    ["full", "of", "shit"],
    ["shit", "head"],
    
    # Hell phrases
    ["what", "the", "hell"],
    ["the", "hell"],
    ["go", "to", "hell"],
    ["hell", "no"],
    ["hell", "yeah"],
    ["bloody", "hell"],
    ["oh", "hell"],
    
    # God phrases
    ["oh", "my", "god"],
    ["my", "god"],
    ["god", "damn"],
    ["god", "dammit"],
    ["goddamn", "it"],
    ["jesus", "christ"],
    ["oh", "god"],
    ["for", "god's", "sake"],
    ["for", "christ's", "sake"],
    
    # Bitch phrases
    ["son", "of", "a", "bitch"],
    ["son", "of", "bitch"],
    
    # Ass phrases
    ["kiss", "my", "ass"],
    ["up", "your", "ass"],
    ["pain", "in", "the", "ass"],
    ["kick", "ass"],
    ["bad", "ass"],
    ["dumb", "ass"],
    ["smart", "ass"],
    ["jack", "ass"],
    ["haul", "ass"],
    
    # Piss phrases
    ["piss", "off"],
    ["pissed", "off"],
    
    # Other phrases
    ["screw", "you"],
    ["screw", "this"],
    ["screw", "that"],
    ["suck", "my", "dick"],
    ["blow", "me"],
    ["bite", "me"],
    ["eat", "shit"],
    ["go", "screw", "yourself"],
    
    # Sexual phrases (from Google Sheets)
    ["blow", "job"],
    ["get", "laid"],
    ["got", "laid"],
    ["been", "laid"],
    ["gang", "bang"],
    ["piece", "of", "ass"],
    ["hard", "on"],
    ["up", "yours"],
    ["give", "a", "damn"],
    ["nooky"],
    ["nooner"],
    
    # Religious phrases (from Google Sheets)
    ["by", "god"],
    ["god", "almighty"],
    ["god", "blessed"],
]


def load_profanity_list(custom_path: str = "") -> Set[str]:
    """
    Load profanity word list.
    
    If a custom path is provided, loads words from that file (one per line)
    and MERGES with the default list.
    
    Args:
        custom_path: Optional path to custom word list file
        
    Returns:
        Set of profanity words (lowercase)
    """
    words = DEFAULT_PROFANITY.copy()
    
    if not custom_path:
        logger.info(f"Using default profanity list ({len(words)} words)")
        return words
    
    path = Path(custom_path)
    if not path.exists():
        logger.warning(f"Custom word list not found: {path}, using default")
        return words
    
    try:
        with open(path, 'r') as f:
            custom_count = 0
            for line in f:
                word = line.strip().lower()
                if word and not word.startswith('#'):
                    if word not in words:
                        custom_count += 1
                    words.add(word)
        
        logger.info(f"Loaded profanity list: {len(words)} words ({custom_count} custom from {path})")
        return words
        
    except Exception as e:
        logger.warning(f"Failed to load custom word list: {e}, using default")
        return DEFAULT_PROFANITY.copy()


def load_profanity_phrases(custom_path: str = "") -> List[List[str]]:
    """
    Load profanity phrase list.
    
    If a custom path is provided, loads phrases from that file
    and MERGES with the default list.
    
    Args:
        custom_path: Optional path to custom phrase list file
        
    Returns:
        List of phrases (each phrase is a list of words)
    """
    phrases = [phrase.copy() for phrase in DEFAULT_PHRASES]
    
    if not custom_path:
        logger.info(f"Using default profanity phrases ({len(phrases)} phrases)")
        return phrases
    
    path = Path(custom_path)
    if not path.exists():
        logger.warning(f"Custom phrase list not found: {path}, using default")
        return phrases
    
    try:
        custom_count = 0
        with open(path, 'r') as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith('#'):
                    words = line.split()
                    if len(words) >= 2:
                        if words not in phrases:
                            custom_count += 1
                            phrases.append(words)
        
        logger.info(f"Loaded phrase list: {len(phrases)} phrases ({custom_count} custom)")
        return phrases
        
    except Exception as e:
        logger.warning(f"Failed to load custom phrase list: {e}, using default")
        return [phrase.copy() for phrase in DEFAULT_PHRASES]


def save_profanity_list(words: Set[str], output_path: Path) -> None:
    """Save profanity list to a file."""
    with open(output_path, 'w') as f:
        f.write("# Profanity word list for Video Censor Tool\n")
        f.write("# One word per line, lines starting with # are comments\n\n")
        for word in sorted(words):
            f.write(f"{word}\n")
    
    logger.info(f"Saved {len(words)} words to {output_path}")
