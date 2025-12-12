
"""
Subtitle Parsing Module.

Parses SRT files and converts them into normalized TimeIntervals
for use in the detection pipeline.
"""

import re
import logging
from pathlib import Path
from typing import List, Generator

from video_censor.editing.intervals import TimeInterval, MatchSource, Action

logger = logging.getLogger(__name__)

def parse_srt(srt_path: Path) -> List[TimeInterval]:
    """
    Parse an SRT file into TimeInterval objects.
    
    Each subtitle block becomes a TimeInterval with:
    - start/end time
    - reason = subtitle text (cleaned)
    - source = MatchSource.SUBTITLE
    - metadata = {'text': original_text}
    """
    if not srt_path.exists():
        logger.warning(f"Subtitle file not found: {srt_path}")
        return []
        
    intervals = []
    
    try:
        content = srt_path.read_text(encoding='utf-8', errors='replace')
        # Normalize newlines
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split by double newlines (standard SRT block separator)
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
                
            # Line 1: Index (skip)
            
            # Line 2: Timestamp (00:00:20,000 --> 00:00:24,400)
            timestamps = lines[1]
            if '-->' not in timestamps:
                continue
                
            start_str, end_str = timestamps.split('-->')
            start = _parse_timestamp(start_str.strip())
            end = _parse_timestamp(end_str.strip())
            
            # Line 3+: Text
            text_lines = lines[2:]
            text = " ".join(text_lines)
            
            # Create interval
            interval = TimeInterval(
                start=start,
                end=end,
                reason=text, # Temporary storage for text, will be used by detector
                action=Action.NONE, # No action determined yet
                source=MatchSource.SUBTITLE,
                metadata={'text': text}
            )
            intervals.append(interval)
            
    except Exception as e:
        logger.error(f"Failed to parse SRT file {srt_path}: {e}")
        
    logger.info(f"Parsed {len(intervals)} subtitle segments from {srt_path.name}")
    return intervals

def _parse_timestamp(t: str) -> float:
    """Convert SRT timestamp (00:00:20,000) to seconds."""
    # Handle comma or dot for milliseconds
    t = t.replace(',', '.')
    
    try:
        parts = t.split(':')
        h = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    except Exception:
        return 0.0
