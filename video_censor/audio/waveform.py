"""
Audio waveform generation for timeline visualization.

Generates waveform images using FFmpeg's showwavespic filter.
These can be displayed behind timeline tracks for better audio context.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_waveform_png(
    input_path: Path,
    output_path: Optional[Path] = None,
    width: int = 1920,
    height: int = 100,
    color: str = "blue",
    background: str = "transparent",
    timeout: int = 60
) -> Optional[Path]:
    """
    Generate a waveform PNG image from audio/video file.
    
    Uses FFmpeg's showwavespic filter to create a visual representation
    of the audio waveform.
    
    Args:
        input_path: Path to audio or video file
        output_path: Output PNG path (creates temp file if None)
        width: Image width in pixels
        height: Image height in pixels
        color: Waveform color (hex or name like 'blue', 'cyan')
        background: Background color ('transparent', 'black', etc.)
        timeout: Max time to wait for generation (seconds)
        
    Returns:
        Path to generated PNG, or None if failed
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='.png'))
    
    logger.info(f"Generating waveform for: {input_path.name} ({width}x{height})")
    
    # Build filter with appropriate colors
    # Colors: a=waveform, b=background
    if background == 'transparent':
        # For transparency, use split alpha
        filter_str = f"showwavespic=s={width}x{height}:colors={color}"
    else:
        filter_str = f"showwavespic=s={width}x{height}:colors={color}:split_channels=0"
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output
        '-i', str(input_path),
        '-filter_complex', f'[0:a]{filter_str}[out]',
        '-map', '[out]',
        '-frames:v', '1',
        str(output_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.warning(f"Waveform generation failed: {result.stderr[-500:]}")
            return None
        
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"Waveform saved to: {output_path}")
            return output_path
        else:
            logger.warning("Waveform file not created or empty")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"Waveform generation timed out after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"Failed to generate waveform: {e}")
        return None


def generate_waveform_for_segment(
    input_path: Path,
    start: float,
    end: float,
    output_path: Optional[Path] = None,
    width: int = 800,
    height: int = 60,
    color: str = "cyan"
) -> Optional[Path]:
    """
    Generate waveform for a specific time segment.
    
    Args:
        input_path: Path to audio/video file
        start: Start time in seconds
        end: End time in seconds
        output_path: Output PNG path
        width: Image width in pixels
        height: Image height in pixels
        color: Waveform color
        
    Returns:
        Path to generated PNG, or None if failed
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='.png'))
    
    duration = end - start
    if duration <= 0:
        return None
    
    filter_str = f"showwavespic=s={width}x{height}:colors={color}"
    
    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(start),
        '-t', str(duration),
        '-i', str(input_path),
        '-filter_complex', f'[0:a]{filter_str}[out]',
        '-map', '[out]',
        '-frames:v', '1',
        str(output_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and output_path.exists():
            return output_path
        return None
        
    except Exception as e:
        logger.error(f"Failed to generate segment waveform: {e}")
        return None


def get_audio_peaks(
    input_path: Path,
    num_samples: int = 500,
    timeout: int = 30
) -> list[float]:
    """
    Get audio peak levels across the file for lightweight visualization.
    
    Uses ffprobe to sample audio levels without generating full waveform.
    Good for previews or when full waveform is too slow.
    
    Args:
        input_path: Path to audio/video file
        num_samples: Number of peak samples to return
        timeout: Max time in seconds
        
    Returns:
        List of peak values (0.0 to 1.0)
    """
    # Use volumedetect filter with astats for peak detection
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-f', 'lavfi',
        '-i', f'amovie={input_path}:loop=0,astats=metadata=1:reset={num_samples}',
        '-show_entries', 'frame_tags=lavfi.astats.Overall.Peak_level',
        '-of', 'csv=p=0'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            return []
        
        # Parse peak levels
        peaks = []
        for line in result.stdout.strip().split('\n'):
            try:
                # Convert dB to linear (0-1)
                db = float(line)
                # dB is typically -inf to 0, convert to 0-1
                linear = 10 ** (db / 20) if db > -60 else 0
                peaks.append(min(1.0, linear))
            except (ValueError, TypeError):
                continue
        
        return peaks[:num_samples]
        
    except Exception as e:
        logger.error(f"Failed to get audio peaks: {e}")
        return []
