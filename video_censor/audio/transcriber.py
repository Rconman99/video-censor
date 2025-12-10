"""
Speech-to-text transcription using faster-whisper.

Provides word-level timestamps for profanity detection.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WordTimestamp:
    """A word with its timing information."""
    word: str
    start: float  # seconds
    end: float    # seconds
    probability: float = 1.0
    
    def __repr__(self) -> str:
        return f"WordTimestamp('{self.word}', {self.start:.2f}-{self.end:.2f}s)"


def transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    language: str = "en",
    compute_type: str = "int8"
) -> List[WordTimestamp]:
    """
    Transcribe audio file to text with word-level timestamps.
    
    Uses faster-whisper for efficient local inference.
    
    Args:
        audio_path: Path to the audio file (WAV, 16kHz mono recommended)
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        language: Language code (e.g., "en" for English)
        compute_type: Compute type (int8, float16, float32)
        
    Returns:
        List of WordTimestamp objects
        
    Raises:
        RuntimeError: If transcription fails
    """
    logger.info(f"Loading Whisper model: {model_size} (compute_type={compute_type})")
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper not installed. Run: pip install faster-whisper"
        )
    
    # Determine device - use CPU for macOS compatibility
    # faster-whisper will use Metal acceleration on Apple Silicon when available
    device = "cpu"
    
    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        raise RuntimeError(f"Failed to load Whisper model: {e}")
    
    logger.info(f"Transcribing audio: {audio_path.name}")
    
    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=language if language else None,
            word_timestamps=True,
            vad_filter=True,  # Voice activity detection to filter silence
        )
        
        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        words: List[WordTimestamp] = []
        # Calculate progress info
        total_duration = info.duration
        if total_duration <= 0:
            total_duration = 1.0  # Avoid division by zero
        
        last_progress_int = 0
        segment_count = 0
            
        for segment in segments:
            segment_count += 1
            if segment.words:
                for word_info in segment.words:
                    words.append(WordTimestamp(
                        word=word_info.word.strip(),
                        start=word_info.start,
                        end=word_info.end,
                        probability=word_info.probability
                    ))
            
            # Print progress update (0-100%)
            if segment.end > 0:
                progress = min(1.0, segment.end / total_duration)
                progress_int = int(progress * 100)
                
                # Update every 1% or at least every 5 seconds of content
                if progress_int > last_progress_int:
                    print(f"PROGRESS: {progress_int}% (Step 1)")
                    import sys
                    sys.stdout.flush()
                    last_progress_int = progress_int
        
        logger.info(f"Transcribed {segment_count} segments, {len(words)} words")
        
        return words
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise RuntimeError(f"Transcription failed: {e}")


def format_transcript(words: List[WordTimestamp], include_times: bool = False) -> str:
    """
    Format word list as readable text.
    
    Args:
        words: List of WordTimestamp objects
        include_times: Whether to include timestamps
        
    Returns:
        Formatted transcript string
    """
    if not include_times:
        return ' '.join(w.word for w in words)
    
    lines = []
    current_line = []
    current_end = 0.0
    
    for word in words:
        # Start new line for significant gaps
        if word.start - current_end > 1.0 and current_line:
            lines.append(' '.join(current_line))
            current_line = []
        
        current_line.append(word.word)
        current_end = word.end
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)
