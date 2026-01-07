"""
File browser utilities for opening folders and revealing files.
"""

import subprocess
import platform
from pathlib import Path
from typing import Union


def open_folder(path: Union[str, Path]):
    """Open folder in system file browser."""
    path = Path(path)
    if not path.exists():
        path = Path.home()
    
    if path.is_file():
        path = path.parent
    
    system = platform.system()
    
    if system == "Darwin":
        subprocess.run(["open", str(path)])
    elif system == "Windows":
        subprocess.run(["explorer", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])


def reveal_in_finder(file_path: Union[str, Path]):
    """Open folder and select/highlight the file."""
    file_path = Path(file_path)
    system = platform.system()
    
    if not file_path.exists():
        open_folder(file_path.parent)
        return
    
    if system == "Darwin":
        subprocess.run(["open", "-R", str(file_path)])
    elif system == "Windows":
        subprocess.run(["explorer", "/select,", str(file_path)])
    else:
        open_folder(file_path.parent)


def get_output_folder() -> Path:
    """Get the default output folder for rendered videos."""
    # Check common locations
    candidates = [
        Path.home() / "Movies",
        Path.home() / "Videos",
        Path.home() / "Desktop",
    ]
    
    for folder in candidates:
        if folder.exists():
            return folder
    
    return Path.home()
