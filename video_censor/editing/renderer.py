"""
Video rendering with ffmpeg.

Applies edit plan to produce final censored video.
"""

import logging
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from typing import List, Optional

from .planner import EditPlan, AudioEdit, adjust_edits_for_cuts
from .intervals import TimeInterval
from ..config import Config

from .planner import EditPlan, AudioEdit, adjust_edits_for_cuts
from .intervals import TimeInterval
from ..config import Config

logger = logging.getLogger(__name__)


def get_quality_args(config: Config, duration: Optional[float] = None) -> List[str]:
    """
    Get ffmpeg arguments for quality preset.
    
    Args:
        config: Configuration object
        duration: Video duration in seconds (not used for preset mode)
        
    Returns:
        List of ffmpeg arguments
    """
    preset = getattr(config.output, 'quality_preset', 'original')
    
    # If original, no scaling/bitrate changes
    if preset in ('original', 'auto'):
        return ['-preset', 'medium', '-crf', str(config.output.video_crf)]
    
    # Map presets to (height, bitrate_mbps)
    presets = {
        "4k_high": (2160, 40),
        "4k_med": (2160, 24),
        "4k_low": (2160, 18),
        "1080p_high": (1080, 20),
        "1080p_med": (1080, 12),
        "1080p_10": (1080, 10),
        "1080p_low": (1080, 8),
        "720p_high": (720, 4),
        "720p_med": (720, 3),
        "720p_low": (720, 2),
        "480p": (480, 1.5),
        "328p": (328, 0.7),
        "240p": (240, 0.3),
        "160p": (160, 0.2),
    }
    
    if preset not in presets:
        logger.warning(f"Unknown quality preset '{preset}', using original")
        return ['-preset', 'medium', '-crf', str(config.output.video_crf)]
    
    height, bitrate_mbps = presets[preset]
    bitrate_kbps = int(bitrate_mbps * 1000)
    
    args = [
        '-preset', 'medium',
        '-vf', f'scale=-2:{height}',
        '-b:v', f'{bitrate_kbps}k',
        '-maxrate', f'{int(bitrate_kbps * 1.5)}k',
        '-bufsize', f'{int(bitrate_kbps * 2)}k'
    ]
    
    logger.info(f"Quality preset '{preset}': {height}p @ {bitrate_mbps} Mbps")
    
    return args


def generate_beep_tone(
    duration: float,
    frequency: int = 1000,
    volume: float = 0.5,
    output_path: Optional[Path] = None
) -> Path:
    """
    Generate a beep tone audio file.
    
    Args:
        duration: Duration in seconds
        frequency: Tone frequency in Hz
        volume: Volume level (0.0 to 1.0)
        output_path: Output file path (creates temp file if not provided)
        
    Returns:
        Path to generated audio file
    """
    if output_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_"))
        output_path = temp_dir / "beep.wav"
    
    # Generate sine wave with ffmpeg
    cmd = [
        'ffmpeg',
        '-y',
        '-f', 'lavfi',
        '-i', f'sine=frequency={frequency}:duration={duration}',
        '-af', f'volume={volume}',
        '-ar', '44100',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to generate beep: {e.stderr}")
    
    return output_path


def build_audio_filter(
    audio_edits: List[AudioEdit],
    beep_frequency: int = 1000,
    beep_volume: float = 0.5
) -> str:
    """
    Build ffmpeg audio filter for muting/beeping.
    
    Args:
        audio_edits: List of audio edits to apply
        beep_frequency: Frequency for beep tones
        beep_volume: Volume for beep tones
        
    Returns:
        ffmpeg filter string
    """
    if not audio_edits:
        return "anull"  # Pass through unchanged
    
    filters = []
    
    for edit in audio_edits:
        if edit.edit_type == "mute":
            # Volume=0 for muted sections
            filters.append(
                f"volume=enable='between(t,{edit.start:.3f},{edit.end:.3f})':volume=0"
            )
        elif edit.edit_type == "beep":
            # For beep, we'll mute and add tone in separate step
            filters.append(
                f"volume=enable='between(t,{edit.start:.3f},{edit.end:.3f})':volume=0"
            )
    
    if not filters:
        return "anull"
    
    return ",".join(filters)


def render_with_cuts_and_mutes(
    input_path: Path,
    output_path: Path,
    plan: EditPlan,
    config: Config,
    duration: Optional[float] = None
) -> None:
    """
    Render video with nudity cuts and profanity mutes.
    
    Uses ffmpeg's concat demuxer for segment stitching.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        plan: Edit plan with cuts and audio edits
        config: Configuration settings
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_render_"))
    
    try:
        # If no cuts needed, just apply audio edits
        if not plan.cut_intervals:
            render_audio_only(input_path, output_path, plan, config, duration=duration)
            return
        
        # Extract each keep segment
        segment_paths: List[Path] = []
        adjusted_audio_edits = adjust_edits_for_cuts(plan)
        
        logger.info(f"Extracting {len(plan.keep_segments)} segments...")
        
        cumulative_offset = 0.0
        
        for i, segment in enumerate(plan.keep_segments):
            segment_path = temp_dir / f"segment_{i:04d}.mp4"
            
            # Find audio edits that apply to this segment
            segment_audio_edits = []
            for edit in plan.audio_edits:
                if edit.start >= segment.start and edit.start < segment.end:
                    # Adjust to segment-local time
                    local_edit = AudioEdit(
                        start=edit.start - segment.start,
                        end=min(edit.end, segment.end) - segment.start,
                        edit_type=edit.edit_type,
                        reason=edit.reason
                    )
                    segment_audio_edits.append(local_edit)
            
            # Extract segment with audio edits
            extract_segment(
                input_path=input_path,
                output_path=segment_path,
                start=segment.start,
                end=segment.end,
                audio_edits=segment_audio_edits,
                config=config,
                total_duration=duration
            )
            
            segment_paths.append(segment_path)
            cumulative_offset += segment.duration
        
        # Concatenate segments
        logger.info("Concatenating segments...")
        concat_segments(segment_paths, output_path, temp_dir)
        
    finally:
        # Cleanup temp files
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")


def _get_hardware_encoder_args(config: Config, prefer_hevc: bool = True) -> Optional[List[str]]:
    """
    Get ffmpeg arguments for hardware encoding if available/configured.
    
    Args:
        config: Configuration object
        prefer_hevc: Use HEVC/H.265 encoder (better for HDR, faster on recent hardware)
    
    Returns:
        List of ffmpeg args or None if hardware encoding disabled/unavailable
    """
    strategy = config.output.hardware_acceleration
    if strategy == "off":
        return None
        
    # Check for macOS VideoToolbox
    if strategy in ["auto", "videotoolbox"] and sys.platform == "darwin":
        # Choose codec based on preference
        if prefer_hevc:
            # HEVC VideoToolbox - better for HDR content, faster on M1+
            args = [
                '-c:v', 'hevc_videotoolbox',
                '-allow_sw', '1',      # Allow software fallback if needed
                '-realtime', '0',      # High quality offline encoding
                '-q:v', '65',          # Quality-based (0-100, higher = better)
            ]
        else:
            # H.264 VideoToolbox - maximum compatibility
            args = [
                '-c:v', 'h264_videotoolbox',
                '-allow_sw', '1',
                '-realtime', '0',
                '-q:v', '70',
            ]
        
        logger.info(f"Using {'HEVC' if prefer_hevc else 'H.264'} VideoToolbox hardware encoder")
        return args

    return None


def extract_segment(
    input_path: Path,
    output_path: Path,
    start: float,
    end: float,
    audio_edits: List[AudioEdit],
    config: Config,
    total_duration: Optional[float] = None,
    force_copy: bool = False
) -> None:
    """
    Extract a segment from the video with audio edits applied.
    
    SMART RENDERING LOGIC:
    1. NO edits + NO scaling → Stream copy everything (FASTEST, ~50x)
    2. Audio edits only → Copy video, re-encode audio only
    3. Quality scaling → Re-encode both (hardware accelerated if available)
    
    Args:
        input_path: Input video path
        output_path: Output segment path
        start: Start time in seconds
        end: End time in seconds
        audio_edits: Audio edits to apply (in segment-local time)
        config: Configuration settings
        force_copy: Force stream copy mode (ignore quality settings)
    """
    duration = end - start
    
    # Determine quality/scaling requirements
    quality_args = get_quality_args(config, total_duration) if not force_copy else []
    must_reencode_video = bool(quality_args)
    has_audio_edits = bool(audio_edits)
    
    # Common input args
    common_args = [
        '-y',
        '-ss', str(start),
        '-i', str(input_path),
        '-t', str(duration)
    ]
    
    # SMART RENDERING: Choose the fastest method
    if not has_audio_edits and not must_reencode_video:
        # CASE 1: PURE STREAM COPY (fastest - no encoding at all)
        # Use -fflags +genpts to regenerate timestamps and avoid muxing errors
        cmd = ['ffmpeg', '-fflags', '+genpts'] + common_args + [
            '-avoid_negative_ts', 'make_zero',
            '-c', 'copy', 
            str(output_path)
        ]
        method = "stream-copy"
        
    elif has_audio_edits and not must_reencode_video:
        # CASE 2: COPY VIDEO, RE-ENCODE AUDIO ONLY
        audio_filter = build_audio_filter(
            audio_edits,
            beep_frequency=config.profanity.beep_frequency_hz,
            beep_volume=config.profanity.beep_volume
        )
        cmd = ['ffmpeg'] + common_args + [
            '-c:v', 'copy',  # No video re-encoding
            '-c:a', config.output.audio_codec,
            '-b:a', config.output.audio_bitrate,
            '-af', audio_filter,
            str(output_path)
        ]
        method = "copy-video"
        
    else:
        # CASE 3: RE-ENCODE (quality scaling or hardware acceleration)
        hw_args = _get_hardware_encoder_args(config)
        
        # Audio args
        if has_audio_edits:
            audio_filter = build_audio_filter(
                audio_edits,
                beep_frequency=config.profanity.beep_frequency_hz,
                beep_volume=config.profanity.beep_volume
            )
            audio_args = [
                '-c:a', config.output.audio_codec,
                '-b:a', config.output.audio_bitrate,
                '-af', audio_filter
            ]
        else:
            audio_args = ['-c:a', 'copy']
        
        # Video args
        if hw_args:
            video_args = hw_args + quality_args
            method = "hw-encode"
        else:
            video_args = ['-c:v', config.output.video_codec, '-preset', 'fast'] + quality_args
            method = "sw-encode"
        
        cmd = ['ffmpeg'] + common_args + video_args + audio_args + [str(output_path)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.debug(f"Extracted segment: {start:.2f}s - {end:.2f}s ({method})")
    except subprocess.CalledProcessError as e:
        logger.error(f"Segment extraction failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract segment: {e.stderr}")


def concat_segments(
    segment_paths: List[Path],
    output_path: Path,
    temp_dir: Path
) -> None:
    """
    Concatenate video segments using ffmpeg concat demuxer.
    
    Args:
        segment_paths: List of segment file paths
        output_path: Output file path
        temp_dir: Temp directory for concat list file
    """
    # Create concat list file
    list_path = temp_dir / "concat_list.txt"
    
    with open(list_path, 'w') as f:
        for path in segment_paths:
            # Escape single quotes in path
            escaped = str(path).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    
    # Run concat
    cmd = [
        'ffmpeg',
        '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(list_path),
        '-fflags', '+genpts',  # Regenerate timestamps to fix discontinuities
        '-c', 'copy',  # No re-encoding needed
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Concatenated {len(segment_paths)} segments to {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Concatenation failed: {e.stderr}")
        raise RuntimeError(f"Failed to concatenate segments: {e.stderr}")


def render_audio_only(
    input_path: Path,
    output_path: Path,
    plan: EditPlan,
    config: Config,
    subtitle_path: Optional[Path] = None,
    duration: Optional[float] = None
) -> None:
    """
    Render video with only audio edits (no cuts).
    
    Args:
        input_path: Input video path
        output_path: Output video path
        plan: Edit plan with audio edits
        config: Configuration settings
        subtitle_path: Optional path to SRT file to burn into video
    """
    audio_filter = build_audio_filter(
        plan.audio_edits,
        beep_frequency=config.profanity.beep_frequency_hz,
        beep_volume=config.profanity.beep_volume
    )
    
    quality_args = get_quality_args(config, duration)
    must_reencode = bool(quality_args)
    
    # If we have subtitles OR quality scaling, we need to re-encode video
    if subtitle_path or must_reencode:
        hw_args = _get_hardware_encoder_args(config)
        
        cmd = ['ffmpeg', '-y', '-i', str(input_path)]
        
        if hw_args:
            # Use hardware encoder
            logger.debug("Using hardware encoder for render (audio/subs/scale)")
            cmd.extend(hw_args)
        else:
            # Use software encoder
            cmd.extend([
                '-c:v', config.output.video_codec,
                '-preset', 'medium',
            ])
            if not must_reencode:
                 # Only if NOT using quality args (which set their own bitrate/crf default via scaling)
                 # Wait, get_quality_args sets bitrate. If no preset, we use default CRF.
                 cmd.extend(['-crf', str(config.output.video_crf)])
            
        # Add quality args (scale, bitrate) if any
        cmd.extend(quality_args)
            
        # Video filter for subtitles
        vf_filters = []
        if subtitle_path:
            escaped_sub_path = str(subtitle_path).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
            vf_filters.append(f"subtitles='{escaped_sub_path}'")
        
        if vf_filters:
            # Check if quality args already include a filter (scale)
            # get_quality_args returns ['-vf', 'scale=...']
            # We need to merge filters if both exist.
            # Only simplistic checking here. Ideally, we parse args.
            # But get_quality_args returns a list for subprocess.
            # If we simply append multiple -vf args, ffmpeg might complain or only use last.
            # Better to construct filter string manually here.
            pass # See revised logic below code block
            
            # REVISION: Let's extract scale filter from quality_args if present and combine
            # This is tricky with list args. 
            # Alternative: don't use get_quality_args list directly for filters.
            
    # Redoing the implementation logic to handle filter combining cleanly
    
    # ... (Actual implementation below)
    
    vf_chain = []
    
    # 1. Scaling
    if must_reencode:
        # get_quality_args returns ['-vf', 'scale=...', '-b:v', ...]
        # We need to parse it or just manually rebuild scaling here for safer combining
        # Let's extract just the non-filter args from get_quality_args then add scale to vf_chain.
        # But get_quality_args logic is centered in that function.
        # Let's modify get_quality_args to return (filter_str, other_args) or just peek.
        # For simplicity, let's just peek config logic here or accept the complexity.
        # Config logic is better:
        pass
        
    # Let's do a cleaner full replacement of this function body:
    
    cmd = ['ffmpeg', '-y', '-i', str(input_path)]
    
    # Determine video filters
    vf_filters = []
    
    # Quality/Scaling
    quality_args = get_quality_args(config)
    # Extract scale filter if present
    other_quality_args = []
    for i in range(len(quality_args)):
        if quality_args[i] == '-vf' and i+1 < len(quality_args):
            vf_filters.append(quality_args[i+1])
        elif i > 0 and quality_args[i-1] == '-vf':
            continue # already handled
        else:
            other_quality_args.append(quality_args[i])
            
    # Subtitles
    if subtitle_path:
        escaped_sub_path = str(subtitle_path).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
        vf_filters.append(f"subtitles='{escaped_sub_path}'")
        
    must_reencode_video = bool(vf_filters) or bool(other_quality_args)

    if must_reencode_video:
        hw_args = _get_hardware_encoder_args(config)
        if hw_args:
            cmd.extend(hw_args)
        else:
             cmd.extend(['-c:v', config.output.video_codec, '-preset', 'medium'])
             if not other_quality_args: # If no explicit bitrate control, use CRF default
                 cmd.extend(['-crf', str(config.output.video_crf)])
                 
        if vf_filters:
            cmd.extend(['-vf', ",".join(vf_filters)])
            
        cmd.extend(other_quality_args)
    else:
        cmd.extend(['-c:v', 'copy'])
        
    # Audio args
    cmd.extend(['-c:a', config.output.audio_codec, '-b:a', config.output.audio_bitrate])
    
    if audio_filter != "anull":
        cmd.extend(['-af', audio_filter])
        
    if must_reencode_video:
        cmd.extend(['-movflags', '+faststart'])
        
    cmd.append(str(output_path))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Rendered audio edits{' (and video changes)' if must_reencode_video else ''} to {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Render failed: {e.stderr}")
        raise RuntimeError(f"Failed to render: {e.stderr}")


def render_with_subtitles(
    input_path: Path,
    output_path: Path,
    subtitle_path: Path,
    config: Config,
    duration: Optional[float] = None
) -> None:
    """
    Render video with subtitles burned in (no other edits).
    
    Requires full video re-encoding.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        subtitle_path: Path to SRT subtitle file
        config: Configuration settings
    """
    # Combined logic with get_quality_args
    # This function was for subtitles only (no audio edits)
    # We apply similar logic: combine subtitle filter with quality scaler
    
    cmd = ['ffmpeg', '-y', '-i', str(input_path)]
    
    vf_filters = []
    
    # Quality/Scaling
    quality_args = get_quality_args(config, duration)
    other_quality_args = []
    for i in range(len(quality_args)):
        if quality_args[i] == '-vf' and i+1 < len(quality_args):
            vf_filters.append(quality_args[i+1])
        elif i > 0 and quality_args[i-1] == '-vf':
            continue
        else:
            other_quality_args.append(quality_args[i])
            
    # Subtitles
    escaped_sub_path = str(subtitle_path).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
    vf_filters.append(f"subtitles='{escaped_sub_path}'")
    
    hw_args = _get_hardware_encoder_args(config)
    if hw_args:
        cmd.extend(hw_args)
    else:
        cmd.extend(['-c:v', config.output.video_codec, '-preset', 'medium'])
        if not other_quality_args:
             cmd.extend(['-crf', str(config.output.video_crf)])
             
    if vf_filters:
        cmd.extend(['-vf', ",".join(vf_filters)])
        
    cmd.extend(other_quality_args)
    
    cmd.extend([
        '-c:a', 'copy',
        '-movflags', '+faststart',
        str(output_path)
    ])
    
    logger.info("Burning subtitles/resizing video...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Rendered video with subtitles to {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Subtitle render failed: {e.stderr}")
        raise RuntimeError(f"Failed to render subtitles: {e.stderr}")


def render_censored_video(
    input_path: Path,
    output_path: Path,
    plan: EditPlan,
    config: Config,
    subtitle_path: Optional[Path] = None,
    input_duration: Optional[float] = None
) -> Path:
    """
    Main rendering function - produces censored video from edit plan.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        plan: Edit plan with all edits
        config: Configuration settings
        subtitle_path: Optional path to SRT file to burn into video
        input_duration: Total duration of input video (required for Target Size mode)
        
    Returns:
        Path to output video
    """
    logger.info(f"Rendering censored video to {output_path}")
    
    if subtitle_path:
        logger.info(f"Subtitles will be burned in from: {subtitle_path}")
    
    # Calculate target duration for quality scaling
    # If we have cuts, the output will be shorter, so we can use a higher bitrate
    target_duration = input_duration
    if plan.keep_segments:
        target_duration = sum(seg.end - seg.start for seg in plan.keep_segments)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Choose rendering strategy based on edit plan
    if not plan.cut_intervals and not plan.audio_edits:
        if subtitle_path:
            # Only subtitles, no other edits
            render_with_subtitles(input_path, output_path, subtitle_path, config, target_duration)
        else:
            # No edits needed, just copy
            logger.info("No edits required, copying input to output")
            import shutil
            shutil.copy(input_path, output_path)
    elif not plan.cut_intervals:
        # Only audio edits (and possibly subtitles)
        render_audio_only(input_path, output_path, plan, config, subtitle_path, target_duration)
    else:
        # Full rendering with cuts
        # Note: When we have cuts AND subtitles, we need a more complex approach:
        # 1. First render with cuts (no subtitles)
        # 2. Then burn subtitles into the result
        # This is because subtitle timing is based on original video timeline
        if subtitle_path:
            # Two-pass approach for cuts + subtitles
            temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_sub_"))
            try:
                temp_output = temp_dir / "temp_no_subs.mp4"
                render_with_cuts_and_mutes(input_path, temp_output, plan, config, target_duration)
                
                # Now burn subtitles into the temporary output
                # Note: This burns original timeline subtitles, which may not sync perfectly
                # with cut video. This is a known limitation.
                logger.warning(
                    "Burning subtitles with video cuts: subtitle timing may not sync "
                    "perfectly due to removed segments."
                )
                render_with_subtitles(temp_output, output_path, subtitle_path, config, target_duration)
            finally:
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
        else:
            render_with_cuts_and_mutes(input_path, output_path, plan, config, target_duration)
    
    # Removed old post-processing logic for target size
    # Scaling is now handled during segment extraction via get_quality_args


    if output_path.exists():
        file_size = output_path.stat().st_size / 1024 / 1024
        logger.info(f"Output file: {output_path} ({file_size:.2f} MB)")
    
    return output_path
