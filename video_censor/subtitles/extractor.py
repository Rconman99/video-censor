"""
Subtitle extraction from video files.

Uses ffmpeg/ffprobe to detect and extract subtitle tracks from video files.
Supports SRT, ASS, and other text-based subtitle formats.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubtitleTrack:
    """Information about a subtitle track in a video file."""
    index: int  # Stream index in the container
    codec: str  # Codec name (subrip, ass, mov_text, etc.)
    language: Optional[str]  # Language code (eng, spa, etc.)
    title: Optional[str]  # Track title if available
    forced: bool  # Whether this is a forced subtitle track
    default: bool  # Whether this is the default track
    
    @property
    def is_text_based(self) -> bool:
        """Check if this is a text-based subtitle (not bitmap)."""
        text_codecs = {'subrip', 'ass', 'ssa', 'mov_text', 'webvtt', 'srt', 'text'}
        return self.codec.lower() in text_codecs
    
    @property
    def is_english(self) -> bool:
        """Check if this track is English."""
        if not self.language:
            return False
        eng_codes = {'eng', 'en', 'english'}
        return self.language.lower() in eng_codes


def detect_subtitle_tracks(input_path: Path) -> List[SubtitleTrack]:
    """
    Detect all subtitle tracks in a video file.
    
    Args:
        input_path: Path to the video file
        
    Returns:
        List of SubtitleTrack objects describing available subtitles
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 's',  # Only subtitle streams
        str(input_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to probe video for subtitles: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe output: {e}")
        return []
    
    tracks = []
    streams = data.get('streams', [])
    
    for stream in streams:
        tags = stream.get('tags', {})
        disposition = stream.get('disposition', {})
        
        track = SubtitleTrack(
            index=stream.get('index', 0),
            codec=stream.get('codec_name', 'unknown'),
            language=tags.get('language'),
            title=tags.get('title'),
            forced=disposition.get('forced', 0) == 1,
            default=disposition.get('default', 0) == 1
        )
        tracks.append(track)
        
        logger.debug(
            f"Found subtitle track {track.index}: "
            f"codec={track.codec}, lang={track.language}, "
            f"forced={track.forced}, default={track.default}"
        )
    
    logger.info(f"Found {len(tracks)} subtitle track(s) in {input_path.name}")
    return tracks


def find_best_english_track(tracks: List[SubtitleTrack]) -> Optional[SubtitleTrack]:
    """
    Find the best English subtitle track from a list.
    
    Priority:
    1. English + forced + text-based
    2. English + default + text-based
    3. English + text-based
    4. Any English track
    
    Args:
        tracks: List of subtitle tracks
        
    Returns:
        Best matching SubtitleTrack, or None if no English track found
    """
    english_tracks = [t for t in tracks if t.is_english]
    
    if not english_tracks:
        return None
    
    # Priority 1: English + forced + text-based
    for track in english_tracks:
        if track.forced and track.is_text_based:
            logger.info(f"Selected forced English subtitle track {track.index}")
            return track
    
    # Priority 2: English + default + text-based
    for track in english_tracks:
        if track.default and track.is_text_based:
            logger.info(f"Selected default English subtitle track {track.index}")
            return track
    
    # Priority 3: English + text-based
    for track in english_tracks:
        if track.is_text_based:
            logger.info(f"Selected English subtitle track {track.index}")
            return track
    
    # Priority 4: Any English (might be bitmap)
    logger.warning(f"Only bitmap English subtitle found (track {english_tracks[0].index})")
    return english_tracks[0]


def extract_english_subtitles(
    input_path: Path,
    output_path: Path,
    track_index: Optional[int] = None
) -> Optional[Path]:
    """
    Extract English subtitles from a video file to SRT format.
    
    Args:
        input_path: Path to the video file
        output_path: Path for output SRT file
        track_index: Optional specific track index to extract.
                     If None, automatically selects best English track.
    
    Returns:
        Path to extracted SRT file, or None if no English subtitles found
    """
    # Detect available tracks
    tracks = detect_subtitle_tracks(input_path)
    
    if not tracks:
        logger.warning(f"No subtitle tracks found in {input_path.name}")
        return None
    
    # Find track to extract
    if track_index is not None:
        # Use specified track
        matching = [t for t in tracks if t.index == track_index]
        if not matching:
            logger.error(f"Subtitle track {track_index} not found")
            return None
        track = matching[0]
    else:
        # Auto-select best English track
        track = find_best_english_track(tracks)
        if not track:
            logger.warning(f"No English subtitle track found in {input_path.name}")
            return None
    
    # Check if text-based
    if not track.is_text_based:
        logger.warning(
            f"Track {track.index} is bitmap-based ({track.codec}), "
            "cannot extract as SRT. OCR would be required."
        )
        return None
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract subtitle track to SRT
    # The stream index in -map is relative to subtitle streams only when using 0:s:N
    # But we have the absolute index, so we use 0:N
    cmd = [
        'ffmpeg',
        '-y',
        '-i', str(input_path),
        '-map', f'0:{track.index}',
        '-c:s', 'srt',  # Convert to SRT format
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Extracted English subtitles to {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitles: {e.stderr}")
        return None


def has_english_subtitles(input_path: Path) -> bool:
    """
    Quick check if a video file has English subtitles.
    
    Args:
        input_path: Path to the video file
        
    Returns:
        True if English subtitles are available
    """
    tracks = detect_subtitle_tracks(input_path)
    return any(t.is_english for t in tracks)
