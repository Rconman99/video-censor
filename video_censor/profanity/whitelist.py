"""
Safe words that contain profanity substrings but should not be flagged.
"""

# Words that contain profanity substrings but are safe
DEFAULT_WHITELIST = {
    # Contains "god"
    "good", "goody", "goodness", "goodbye", "goodwill",
    "godfather", "godmother", "goddaughter", "godson", "godspeed",
    
    # Contains "christ"
    "christopher", "christian", "christina", "christmas",
    "christine", "christoph", "christy", "christie",
    
    # Contains "ass"
    "class", "pass", "mass", "bass", "grass", "glass", "brass",
    "assign", "assist", "asset", "assemble", "assembly", "assert",
    "cassette", "classic", "compass", "embassy", "harass", "massachusetts",
    "passive", "passion", "passport", "password", "passage", "passenger",
    "assume", "assurance", "assure", "associate", "association",
    
    # Contains "hell"
    "hello", "shell", "dwell", "spell", "swell", "well", "bell", "cell", "fell", "sell", "tell",
    "shelter", "michelle", "seychelles", "misspell", "bookshelf", "eggshell",
    "winchell", "satchel", 
    
    # Contains "damn"
    "amsterdam", "damnation", # Depending on context, damnation might be biblical/ok
    "fundamental", "damage", "damp", "damsel", "adamant",
    
    # Contains "shit"
    "shiitake", "shitzu", "shirt", "shift", # Shift/Shirt shouldn't match shit anyway but good to be safe
    
    # Contains "cock"
    "cockpit", "cockatoo", "cockatiel", "peacock", "hancock", "cocktail",
    "cockroach", "shuttlecock", "weathercock", "babcock", "hitchcock",
    
    # Contains "dick"
    "dickens", "edict", "predict", "addict", "verdict", "contradict", "indict",
    "dickson", "dickinson", "moby-dick", # Context
    
    # Contains "piss"
    "mississippi", 
    
    # Contains "crap"
    "scrap", "scrappy", "skyscraper", "scrapbook",
    
    # Contains "tit"
    "title", "constitution", "institution", "petition", "entitled", "attitude",
    "repetition", "competition", "appetite", "entity", "identity", "quantity",
    "titanic", "titanium", "stitch", "altitude", "latitude", "gratitude",
    
    # Contains "cum"
    "document", "circumstance", "accumulate", "cucumber", "succumb",
    "scum", # Maybe?
    
    # Contains "anal"
    "analyze", "analysis", "analog", "analogy", "analyst", "banal", "canal",
    
    # Contains "sex"
    "middlesex", "essex", "sussex", "wessex",
}

# Words to ALWAYS flag regardless of context
# These override whitelist if there's a conflict
ALWAYS_FLAG = {
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty", "bullshit", 
    "ass", "asshole", 
    "bitch", "bitches",
    "damn", "dammit", "goddamn",
    "cunt",
    "cock", "dick", 
    "piss", "pissed",
    "bastard",
    "whore", "slut",
    "nigger", "nigga",
    "fag", "faggot",
    "retard", "retarded",
}
