import sys
from PySide6.QtWidgets import QApplication
from ui.error_dialog import show_error
from ui.styles import DARK_STYLESHEET

def test_dialog():
    app = QApplication(sys.argv)
    
    # Apply global stylesheet to match real app condition
    app.setStyleSheet(DARK_STYLESHEET)
    
    print("Showing styled error dialog...")
    show_error(
        "Design Limitation",
        "This is a test of the new dark mode styling for the error dialog.\n\n"
        "The text should be easily readable (light gray on dark gray).",
        "Technical Details:\nStack trace goes here...\nMore info..."
    )
    print("Dialog closed.")

if __name__ == "__main__":
    test_dialog()
