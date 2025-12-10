"""
Summary report generation.

Creates human-readable and JSON reports of censoring results.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from ..editing.planner import EditPlan

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    else:
        return f"{minutes:02d}:{secs:06.3f}"


def generate_summary(
    plan: EditPlan,
    input_path: Path,
    output_path: Path,
    processing_time: float = 0.0
) -> Dict[str, Any]:
    """
    Generate a summary report of the censoring operation.
    
    Args:
        plan: The executed edit plan
        input_path: Path to input video
        output_path: Path to output video
        processing_time: Total processing time in seconds
        
    Returns:
        Dictionary with summary data
    """
    summary = {
        "timestamp": datetime.now().isoformat(),
        "input": {
            "path": str(input_path),
            "duration": plan.original_duration,
            "duration_formatted": format_duration(plan.original_duration)
        },
        "output": {
            "path": str(output_path),
            "duration": plan.output_duration,
            "duration_formatted": format_duration(plan.output_duration)
        },
        "processing": {
            "time_seconds": processing_time,
            "time_formatted": format_duration(processing_time)
        },
        "profanity": {
            "detected_count": plan.profanity_count,
            "audio_edits_count": len(plan.audio_edits),
            "intervals": [
                {
                    "start": interval.start,
                    "end": interval.end,
                    "reason": interval.reason
                }
                for interval in plan.profanity_intervals
            ]
        },
        "nudity": {
            "segments_cut": plan.nudity_count,
            "duration_removed": plan.cut_duration,
            "duration_removed_formatted": format_duration(plan.cut_duration),
            "intervals": [
                {
                    "start": interval.start,
                    "end": interval.end,
                    "duration": interval.duration
                }
                for interval in plan.cut_intervals
            ]
        },
        "summary": {
            "total_profanity_instances": plan.profanity_count,
            "total_nudity_segments": plan.nudity_count,
            "duration_before": plan.original_duration,
            "duration_after": plan.output_duration,
            "duration_removed": plan.cut_duration,
            "percent_removed": (plan.cut_duration / plan.original_duration * 100) 
                              if plan.original_duration > 0 else 0
        }
    }
    
    return summary


def print_summary(
    plan: EditPlan,
    input_path: Path,
    output_path: Path,
    processing_time: float = 0.0
) -> None:
    """
    Print a human-readable summary to console.
    
    Args:
        plan: The executed edit plan
        input_path: Path to input video
        output_path: Path to output video
        processing_time: Total processing time in seconds
    """
    width = 50
    
    print()
    print("=" * width)
    print("VIDEO CENSOR - PROCESSING COMPLETE")
    print("=" * width)
    print()
    
    # Input/Output
    print(f"Input:  {input_path.name}")
    print(f"Output: {output_path.name}")
    print()
    
    # Duration
    print("-" * width)
    print("DURATION")
    print("-" * width)
    print(f"  Original:  {format_duration(plan.original_duration)}")
    print(f"  Final:     {format_duration(plan.output_duration)}")
    
    if plan.cut_duration > 0:
        percent = plan.cut_duration / plan.original_duration * 100
        print(f"  Removed:   {format_duration(plan.cut_duration)} ({percent:.1f}%)")
    print()
    
    # Profanity
    print("-" * width)
    print("PROFANITY CENSORING")
    print("-" * width)
    print(f"  Instances detected: {plan.profanity_count}")
    print(f"  Audio edits made:   {len(plan.audio_edits)}")
    
    if plan.audio_edits:
        print()
        print("  Edit details:")
        for i, edit in enumerate(plan.audio_edits[:10], 1):  # Show first 10
            print(f"    {i}. {format_duration(edit.start)} - {format_duration(edit.end)} [{edit.edit_type}]")
        if len(plan.audio_edits) > 10:
            print(f"    ... and {len(plan.audio_edits) - 10} more")
    print()
    
    # Nudity
    print("-" * width)
    print("NUDITY REMOVAL")
    print("-" * width)
    print(f"  Segments cut:     {plan.nudity_count}")
    print(f"  Duration removed: {format_duration(plan.cut_duration)}")
    
    if plan.cut_intervals:
        print()
        print("  Cut details:")
        for i, interval in enumerate(plan.cut_intervals[:10], 1):
            print(f"    {i}. {format_duration(interval.start)} - {format_duration(interval.end)}")
        if len(plan.cut_intervals) > 10:
            print(f"    ... and {len(plan.cut_intervals) - 10} more")
    print()
    
    # Processing time
    if processing_time > 0:
        print("-" * width)
        print(f"Processing time: {format_duration(processing_time)}")
    
    print("=" * width)
    print()


def save_summary_json(
    summary: Dict[str, Any],
    output_path: Path
) -> None:
    """
    Save summary to a JSON file.
    
    Args:
        summary: Summary dictionary
        output_path: Path for JSON output
    """
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Summary saved to {output_path}")


def save_edit_timeline(
    plan: EditPlan,
    output_path: Path
) -> None:
    """
    Save a detailed timeline of all edits.
    
    Args:
        plan: Edit plan with all intervals
        output_path: Path for timeline output
    """
    with open(output_path, 'w') as f:
        f.write("VIDEO CENSOR - EDIT TIMELINE\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        
        # Profanity timeline
        f.write("PROFANITY DETECTIONS\n")
        f.write("-" * 40 + "\n")
        for i, interval in enumerate(plan.profanity_intervals, 1):
            f.write(f"{i:4d}. {format_duration(interval.start)} - {format_duration(interval.end)}\n")
            if interval.reason:
                f.write(f"      Reason: {interval.reason}\n")
        f.write("\n")
        
        # Audio edits timeline
        f.write("AUDIO EDITS (after merging)\n")
        f.write("-" * 40 + "\n")
        for i, edit in enumerate(plan.audio_edits, 1):
            f.write(f"{i:4d}. {format_duration(edit.start)} - {format_duration(edit.end)} [{edit.edit_type}]\n")
        f.write("\n")
        
        # Nudity timeline
        f.write("NUDITY CUTS\n")
        f.write("-" * 40 + "\n")
        for i, interval in enumerate(plan.cut_intervals, 1):
            f.write(f"{i:4d}. {format_duration(interval.start)} - {format_duration(interval.end)}\n")
            f.write(f"      Duration: {interval.duration:.3f}s\n")
        f.write("\n")
        
        # Keep segments
        f.write("KEEP SEGMENTS\n")
        f.write("-" * 40 + "\n")
        for i, segment in enumerate(plan.keep_segments, 1):
            f.write(f"{i:4d}. {format_duration(segment.start)} - {format_duration(segment.end)}\n")
            f.write(f"      Duration: {segment.duration:.3f}s\n")
    
    logger.info(f"Edit timeline saved to {output_path}")
