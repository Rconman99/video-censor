"""
Severity tiers for profanity categorization.
Used to group detections in the UI for faster review.
"""

from typing import Tuple, List, Dict

SEVERITY_TIERS = {
    "severe": {
        "order": 1,
        "color": "#FF0000",  # Red
        "words": [
            "fuck", "fucking", "fucked", "fucker", "motherfucker", "clusterfuck", "fuckhead", "fuckface",
            "shit", "shitty", "bullshit", "horseshit", "apeshit", "shithead", "dipshit",
            "cunt", "cunts",
            "bitch", "bitches", "bitching", "sonofabitch",
            "cock", "cocks", "dick", "dicks", "pussy", "pussies",
            "asshole", "assholes",
            "whore", "whores", "slut", "sluts",
            "nigger", "nigga", "fag", "faggot", "kike", "spic", "chink", "gook", "wetback", "dyke" # Slurs
        ]
    },
    "moderate": {
        "order": 2,
        "color": "#FFA500",  # Orange
        "words": [
            "bastard", "bastards",
            "piss", "pissed", "pissing",
            "crap", "crappy",
            "suck", "sucks", "sucking",
            "screw", "screwed", "screwing",
            "tits", "titties", "boobs", "boobies",
            "douche", "douchebag",
            "prick", "twat", "wanker",
        ]
    },
    "mild": {
        "order": 3,
        "color": "#FFD700",  # Yellow
        "words": [
            "damn", "dammit", "goddamn", "damned",
            "hell", "heck",
            "ass", "asses", # Standalone ass is often mild compared to asshole
            "arse",
            "bloody", "bugger",
        ]
    },
    "religious": {
        "order": 4,
        "color": "#9370DB",  # Purple
        "words": [
            "god", "jesus", "christ", "jesuschrist",
            "lord", "omg", "oh my god",
        ]
    },
}

def get_severity(word: str, overrides: Dict[str, str] = None, custom_tiers: List[Dict] = None) -> Tuple[str, int, str]:
    """
    Returns (tier_name, order, color) for a word.
    
    Args:
        word: The word to classify.
        overrides: Dictionary mapping words to tier names.
        custom_tiers: List of custom tier definitions from config.
    """
    word_lower = word.lower()
    
    # Merge default and custom tiers
    active_tiers = SEVERITY_TIERS.copy()
    if custom_tiers:
        for tier in custom_tiers:
            name = tier.get("name")
            if name:
                active_tiers[name] = {
                    "order": tier.get("order", 99),
                    "color": tier.get("color", "#808080"),
                    "words": tier.get("words", [])
                }

    # 1. Check Overrides
    if overrides and word_lower in overrides:
        tier_name = overrides[word_lower]
        if tier_name in active_tiers:
            tier_data = active_tiers[tier_name]
            return (tier_name, tier_data["order"], tier_data["color"])

    # 2. Check exact match in tiers
    for tier_name, tier_data in active_tiers.items():
        if word_lower in tier_data["words"]:
            return (tier_name, tier_data["order"], tier_data["color"])
            
    # 3. Check partial match (check severe/low-order first)
    # Sort tiers by order to ensure higher severity matches first
    sorted_tiers = sorted(active_tiers.items(), key=lambda x: x[1]['order'])
    
    for tier_name, tier_data in sorted_tiers:
        for tier_word in tier_data["words"]:
            if tier_word in word_lower:
                 return (tier_name, tier_data["order"], tier_data["color"])

    return ("unknown", 99, "#808080")  # Gray for unknown

def get_tier_words(tier_name: str) -> List[str]:
    """Get all words in a tier."""
    return SEVERITY_TIERS.get(tier_name, {}).get("words", [])
