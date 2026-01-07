"""
Recent files management for VideoCensor.
Tracks recently opened videos with metadata.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

MAX_RECENT_FILES = 10
CONFIG_DIR = Path.home() / ".videocensor"
RECENT_FILE = CONFIG_DIR / "recent_files.json"


def get_recent_files() -> List[Dict]:
    """Get list of recent files with metadata."""
    if not RECENT_FILE.exists():
        return []
    
    try:
        data = json.loads(RECENT_FILE.read_text())
        # Filter out files that no longer exist
        return [f for f in data if Path(f["path"]).exists()]
    except Exception:
        return []


def add_recent_file(path: str, name: Optional[str] = None):
    """Add a file to the recent files list."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    path = str(Path(path).resolve())
    name = name or Path(path).name
    
    recent = get_recent_files()
    
    # Remove if already exists (will re-add at top)
    recent = [f for f in recent if f["path"] != path]
    
    # Add to top
    recent.insert(0, {
        "path": path,
        "name": name,
        "opened_at": datetime.now().isoformat()
    })
    
    # Limit to max
    recent = recent[:MAX_RECENT_FILES]
    
    RECENT_FILE.write_text(json.dumps(recent, indent=2))


def clear_recent_files():
    """Clear the recent files list."""
    if RECENT_FILE.exists():
        RECENT_FILE.unlink()
