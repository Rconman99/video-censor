"""
Subtitle profanity filtering.

Provides functions to censor profanity in SRT subtitle files while
preserving timing and formatting.
"""

import logging
import re
from pathlib import Path
from typing import Set, Optional

logger = logging.getLogger(__name__)


def censor_word(word: str, replacement: str = "[...]") -> str:
    """
    Replace a word with censored version while preserving surrounding punctuation.
    
    Args:
        word: The word to censor
        replacement: The replacement text (default: "[...]")
        
    Returns:
        The censored word with punctuation preserved
    """
    # Extract leading and trailing punctuation
    leading = ""
    trailing = ""
    
    # Find leading punctuation
    i = 0
    while i < len(word) and not word[i].isalnum():
        leading += word[i]
        i += 1
    
    # Find trailing punctuation
    j = len(word)
    while j > i and not word[j-1].isalnum():
        j -= 1
        trailing = word[j] + trailing
    
    return leading + replacement + trailing


def censor_text_line(
    text: str,
    profanity_set: Set[str],
    replacement: str = "[...]"
) -> str:
    """
    Censor profanity in a single line of text.
    
    Args:
        text: The text line to censor
        profanity_set: Set of lowercase profanity words to filter
        replacement: The replacement text
        
    Returns:
        The censored text line
    """
    # Split into words while preserving whitespace
    words = re.split(r'(\s+)', text)
    result = []
    
    for token in words:
        # Skip whitespace tokens
        if not token.strip():
            result.append(token)
            continue
        
        # Extract core word (without punctuation) for matching
        core_match = re.match(r'^([^\w]*)(\w+)([^\w]*)$', token, re.UNICODE)
        
        if core_match:
            prefix, core, suffix = core_match.groups()
            
            # Check if core word is profanity (case-insensitive)
            if core.lower() in profanity_set:
                # Replace with censored version
                result.append(prefix + replacement + suffix)
                logger.debug(f"Censored subtitle word: '{core}' -> '{replacement}'")
            else:
                result.append(token)
        else:
            # No word content, keep as-is
            result.append(token)
    
    return ''.join(result)


def parse_srt_content(content: str) -> list:
    """
    Parse SRT content into a list of subtitle entries.
    
    Each entry is a dict with:
    - index: The subtitle number
    - timestamp: The timing line
    - text: List of text lines
    
    Args:
        content: The raw SRT file content
        
    Returns:
        List of subtitle entry dicts
    """
    entries = []
    
    # Split by double newline to get subtitle blocks
    # Handle both \r\n and \n line endings
    content = content.replace('\r\n', '\n')
    blocks = re.split(r'\n\n+', content.strip())
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        # First line should be the index number
        try:
            index = int(lines[0].strip())
        except ValueError:
            # Not a valid index, skip this block
            continue
        
        # Second line should be timestamp
        timestamp = lines[1].strip()
        
        # Remaining lines are text
        text_lines = lines[2:] if len(lines) > 2 else []
        
        entries.append({
            'index': index,
            'timestamp': timestamp,
            'text': text_lines
        })
    
    return entries


def format_srt_content(entries: list) -> str:
    """
    Format parsed subtitle entries back to SRT content.
    
    Args:
        entries: List of subtitle entry dicts
        
    Returns:
        Formatted SRT content string
    """
    blocks = []
    
    for entry in entries:
        block_lines = [
            str(entry['index']),
            entry['timestamp']
        ]
        block_lines.extend(entry['text'])
        blocks.append('\n'.join(block_lines))
    
    return '\n\n'.join(blocks) + '\n'


def censor_srt_content(
    srt_content: str,
    profanity_set: Set[str],
    replacement: str = "[...]"
) -> str:
    """
    Censor profanity in SRT subtitle content.
    
    Args:
        srt_content: The raw SRT file content
        profanity_set: Set of lowercase profanity words to filter
        replacement: The replacement text (default: "[...]")
        
    Returns:
        The censored SRT content
    """
    # Parse SRT
    entries = parse_srt_content(srt_content)
    
    censored_count = 0
    
    # Process each entry
    for entry in entries:
        censored_lines = []
        for line in entry['text']:
            original = line
            censored = censor_text_line(line, profanity_set, replacement)
            if censored != original:
                censored_count += 1
            censored_lines.append(censored)
        entry['text'] = censored_lines
    
    logger.info(f"Censored {censored_count} subtitle lines containing profanity")
    
    # Format back to SRT
    return format_srt_content(entries)


def censor_subtitle_file(
    input_path: Path,
    output_path: Path,
    profanity_set: Set[str],
    replacement: str = "[...]"
) -> Optional[Path]:
    """
    Censor profanity in an SRT subtitle file.
    
    Args:
        input_path: Path to input SRT file
        output_path: Path for output censored SRT file
        profanity_set: Set of lowercase profanity words to filter
        replacement: The replacement text
        
    Returns:
        Path to censored SRT file, or None on error
    """
    try:
        # Read input file
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read subtitle file {input_path}: {e}")
        return None
    
    # Censor content
    censored_content = censor_srt_content(content, profanity_set, replacement)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Write output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(censored_content)
        
        logger.info(f"Wrote censored subtitles to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to write subtitle file {output_path}: {e}")
        return None
