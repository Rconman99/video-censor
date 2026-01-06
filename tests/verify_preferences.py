import sys
from PySide6.QtWidgets import QApplication, QDialog
from video_censor.config import Config
from pathlib import Path

# Mock UI context
app = QApplication(sys.argv)

def test_preferences_logic():
    print("1. Testing Config updates...")
    # Verify default method exists
    cfg = Config.default()
    assert cfg.profanity.censor_mode == "beep"
    print("   PASS: Config.default() works")
    
    # Verify save path logic
    test_path = Path("test_config.yaml")
    cfg.save(test_path)
    assert test_path.exists()
    print("   PASS: Config.save(path) works")
    
    # Verify load stores path
    loaded = Config.load(test_path)
    assert loaded._path == test_path
    print("   PASS: Config.load() stores path")
    
    # Verify parameterless save
    loaded.profanity.censor_mode = "mute"
    loaded.save()
    
    reloaded = Config.load(test_path)
    assert reloaded.profanity.censor_mode == "mute"
    print("   PASS: Config.save() without path works")
    
    print("2. Testing Dialog instantiation...")
    # Import here to avoid issues if import fails
    from ui.preferences_dialog import PreferencesDialog
    
    dlg = PreferencesDialog()
    assert dlg.windowTitle() == "Preferences"
    print("   PASS: Dialog instantiated")
    
    # Cleanup
    if test_path.exists():
        test_path.unlink()
        
    print("\nAll Preferences logic tests passed!")

if __name__ == "__main__":
    try:
        test_preferences_logic()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
