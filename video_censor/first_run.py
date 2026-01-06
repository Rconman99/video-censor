from pathlib import Path
import json
import os

class FirstRunManager:
    """Manages the first-run state of the application."""
    
    # Use a hidden directory in user's home for app state
    CONFIG_DIR = Path.home() / ".videocensor"
    STATE_FILE = CONFIG_DIR / "app_state.json"
    
    @classmethod
    def is_first_run(cls) -> bool:
        """Check if this is the first time the app is launched."""
        if not cls.STATE_FILE.exists():
            return True
            
        try:
            content = cls.STATE_FILE.read_text()
            if not content.strip():
                return True
                
            state = json.loads(content)
            return not state.get("setup_complete", False)
        except Exception:
            # If state file is corrupted, treat as first run
            return True
    
    @classmethod
    def mark_setup_complete(cls):
        """Mark first-run setup as complete."""
        try:
            cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            state = {}
            if cls.STATE_FILE.exists():
                try:
                    state = json.loads(cls.STATE_FILE.read_text())
                except Exception:
                    pass
            
            state["setup_complete"] = True
            state["setup_version"] = "1.0"
            
            cls.STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            print(f"Error marking setup complete: {e}")
    
    @classmethod
    def reset_first_run(cls):
        """Reset first-run state for testing or re-running setup."""
        if cls.STATE_FILE.exists():
            try:
                state = json.loads(cls.STATE_FILE.read_text())
                state["setup_complete"] = False
                cls.STATE_FILE.write_text(json.dumps(state, indent=2))
            except Exception:
                # If file is bad, just delete it to force reset
                try:
                    cls.STATE_FILE.unlink()
                except Exception:
                    pass
