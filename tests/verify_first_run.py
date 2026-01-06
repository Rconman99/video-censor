from video_censor.first_run import FirstRunManager
from pathlib import Path
import json

def test_first_run_manager():
    # Setup: Ensure clean state
    if FirstRunManager.STATE_FILE.exists():
        FirstRunManager.STATE_FILE.unlink()
    
    print("1. Checking initial state...")
    assert FirstRunManager.is_first_run() == True, "Should be first run initially"
    print("   PASS: Initial state is first run")
    
    print("2. Marking setup complete...")
    FirstRunManager.mark_setup_complete()
    assert FirstRunManager.STATE_FILE.exists(), "State file should exist"
    
    print("3. Checking state after setup...")
    assert FirstRunManager.is_first_run() == False, "Should not be first run after marking complete"
    print("   PASS: State updated correctly")
    
    print("4. Resetting first run...")
    FirstRunManager.reset_first_run()
    
    # Reload to check content
    state = json.loads(FirstRunManager.STATE_FILE.read_text())
    assert state["setup_complete"] == False, "Setup complete should be False"
    # Note: is_first_run() checks setup_complete flag too
    assert FirstRunManager.is_first_run() == True, "Should be first run after reset"
    print("   PASS: Reset successful")
    
    # Cleanup
    FirstRunManager.STATE_FILE.unlink()
    
if __name__ == "__main__":
    try:
        test_first_run_manager()
        print("\nAll FirstRunManager tests passed!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")
