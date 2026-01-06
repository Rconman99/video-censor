"""
Processing stages for video censoring workflow.
Defines stages, labels, icons, and progress weight calculations.
"""

from enum import Enum
from dataclasses import dataclass


class ProcessingStage(Enum):
    INITIALIZING = "initializing"
    EXTRACTING_AUDIO = "extracting_audio"
    ANALYZING_AUDIO = "analyzing_audio"
    ANALYZING_VIDEO = "analyzing_video"
    MERGING_DETECTIONS = "merging_detections"
    REVIEWING = "reviewing"
    RENDERING = "rendering"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StageInfo:
    label: str
    icon: str
    weight: float  # Percentage of total time this stage typically takes


STAGE_INFO = {
    ProcessingStage.INITIALIZING: StageInfo(
        label="Preparing...",
        icon="⏳",
        weight=0.02
    ),
    ProcessingStage.EXTRACTING_AUDIO: StageInfo(
        label="Extracting audio track...",
        icon="🎵",
        weight=0.05
    ),
    ProcessingStage.ANALYZING_AUDIO: StageInfo(
        label="Analyzing speech...",
        icon="🎤",
        weight=0.35
    ),
    ProcessingStage.ANALYZING_VIDEO: StageInfo(
        label="Scanning video frames...",
        icon="👁",
        weight=0.35
    ),
    ProcessingStage.MERGING_DETECTIONS: StageInfo(
        label="Processing detections...",
        icon="🔄",
        weight=0.03
    ),
    ProcessingStage.REVIEWING: StageInfo(
        label="Ready for review",
        icon="✏️",
        weight=0
    ),
    ProcessingStage.RENDERING: StageInfo(
        label="Rendering output...",
        icon="🎬",
        weight=0.18
    ),
    ProcessingStage.FINALIZING: StageInfo(
        label="Finalizing...",
        icon="✨",
        weight=0.02
    ),
    ProcessingStage.COMPLETE: StageInfo(
        label="Complete!",
        icon="✅",
        weight=0
    ),
    ProcessingStage.ERROR: StageInfo(
        label="Error occurred",
        icon="❌",
        weight=0
    ),
}


def get_stage_label(stage: ProcessingStage, detail: str = None) -> str:
    """Get display label for stage, optionally with detail"""
    info = STAGE_INFO.get(stage)
    if not info:
        return "Processing..."
    
    if detail:
        return f"{info.icon} {info.label} ({detail})"
    return f"{info.icon} {info.label}"


def get_overall_progress(stage: ProcessingStage, stage_progress: float) -> float:
    """
    Calculate overall progress given current stage and progress within that stage.
    
    Example: If in ANALYZING_AUDIO (weight=0.35) at 50% done,
    overall = prior_stages + (0.35 * 0.5) = ~0.07 + 0.175 = ~24%
    """
    stages_order = [
        ProcessingStage.INITIALIZING,
        ProcessingStage.EXTRACTING_AUDIO,
        ProcessingStage.ANALYZING_AUDIO,
        ProcessingStage.ANALYZING_VIDEO,
        ProcessingStage.MERGING_DETECTIONS,
        ProcessingStage.RENDERING,
        ProcessingStage.FINALIZING,
        ProcessingStage.COMPLETE,
    ]
    
    overall = 0.0
    
    for s in stages_order:
        info = STAGE_INFO.get(s)
        if not info:
            continue
        
        if s == stage:
            # Add partial progress in current stage
            overall += info.weight * (stage_progress / 100)
            break
        else:
            # Add full weight of completed stages
            overall += info.weight
    
    return min(overall * 100, 100)
