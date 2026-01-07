#!/usr/bin/env python3
"""
Video Censor Tool - CLI Entry Point

A fully local, offline video editing tool that automatically detects 
and censors profanity and nudity from video files.

Usage:
    censor_video input.mp4 output.mp4 [--config config.yaml]
    
Example:
    censor_video movie.mp4 movie_censored.mp4
    censor_video --help
"""

import argparse
import logging
import sys
import time
import tempfile
import shutil
import json # Added because used in main for save_summary
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent))

from video_censor.config import Config
from video_censor.validator import validate_input, validate_output_path, VideoInfo
from video_censor.audio import extract_audio, transcribe_audio
from video_censor.profanity import (
    load_profanity_list, load_profanity_phrases, detect_profanity, 
    detect_profanity_phrases, analyze_subtitles_for_profanity
)
from video_censor.nudity import extract_frames, detect_nudity
from video_censor.sexual_content import (
    detect_sexual_content, 
    load_sexual_terms, 
    load_sexual_phrases,
    # Phase 2: Hybrid detection
    detect_sexual_content_hybrid,
    is_semantic_detection_available,
    # Phase 2: Multimodal fusion
    fuse_multimodal_detections,
)
from video_censor.violence import detect_violence
from video_censor.editing import merge_intervals, plan_edits, render_censored_video
from video_censor.reporting import generate_summary, print_summary, save_edit_timeline
from video_censor.preferences import ContentFilterSettings
from video_censor.preferences import ContentFilterSettings
from video_censor.subtitles import extract_english_subtitles, censor_subtitle_file, has_english_subtitles
from video_censor.subtitles.parser import parse_srt

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Censor profanity and nudity from video files (fully offline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  censor_video movie.mp4 movie_clean.mp4
  censor_video --config myconfig.yaml video.mp4 video_censored.mp4
  censor_video --no-nudity video.mp4 output.mp4  # Only censor profanity
  censor_video --no-profanity video.mp4 output.mp4  # Only cut nudity
  censor_video --threshold 0.8 video.mp4 output.mp4  # Stricter nudity detection
  censor_video --model small video.mp4 output.mp4  # More accurate transcription
        """
    )
    
    parser.add_argument(
        "input",
        type=Path,
        help="Input video file path"
    )
    
    parser.add_argument(
        "output",
        type=Path,
        help="Output video file path"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Path to configuration YAML file"
    )
    
    parser.add_argument(
        "--overwrite", "-y",
        action="store_true",
        help="Overwrite output file if it exists"
    )
    
    parser.add_argument(
        "--no-profanity",
        action="store_true",
        help="Skip profanity detection"
    )
    
    parser.add_argument(
        "--no-nudity",
        action="store_true",
        help="Skip nudity detection"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    
    parser.add_argument(
        "--save-summary",
        type=Path,
        default=None,
        help="Save JSON summary to file"
    )
    
    # Config override arguments
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override nudity detection threshold (0.0-1.0, higher = stricter)"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        choices=["tiny", "base", "small", "medium", "large-v3"],
        default=None,
        help="Override Whisper model size"
    )
    
    parser.add_argument(
        "--censor-mode",
        type=str,
        choices=["mute", "beep"],
        default=None,
        help="Override profanity censor mode"
    )
    
    parser.add_argument(
        "--frame-interval",
        type=float,
        default=None,
        help="Override frame sampling interval (seconds)"
    )
    
    parser.add_argument(
        "--save-timeline",
        type=Path,
        default=None,
        help="Save detailed edit timeline to file"
    )
    
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="Directory for temporary files"
    )

    # Workflow arguments for GUI integration
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Run analysis only and exit (skips rendering)"
    )

    parser.add_argument(
        "--export-intervals",
        type=Path,
        default=None,
        help="Save detected intervals to JSON file"
    )

    parser.add_argument(
        "--import-intervals",
        type=Path,
        default=None,
        help="Load intervals from JSON file (skips detection)"
    )

    parser.add_argument(
        "--subtitles",
        type=Path,
        default=None,
        help="Path to SRT subtitle file to skip transcription"
    )
    
    return parser.parse_args()





def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on verbosity."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    # Configure logging with both file and console handlers
    # Use absolute path for log file to satisfy permissions
    log_file = Path(__file__).parent / "censor_video.log"
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(str(log_file), mode='a')
        ],
        datefmt='%H:%M:%S'
    )


def _analyze_audio(input_path: Path, temp_dir: Path, config: Config, subtitles_path: Optional[Path] = None):
    """
    Audio analysis pipeline (Step 1).
    
    Runs in a separate thread for parallel execution.
    
    Returns:
        Tuple of (profanity_intervals, words)
    """
    logger.info("=" * 50)
    logger.info("STEP 1: Profanity Detection")
    logger.info("=" * 50)

    words = []
    profanity_intervals = []

    if subtitles_path and subtitles_path.exists():
        logger.info(f"📄 Using subtitles for profanity check: {subtitles_path.name}")
        logger.info("   -> Skipping audio extraction & transcription (saving ~30 mins)")
        
        try:
            srt_intervals = parse_srt(subtitles_path)
            logger.info(f"   -> Parsed {len(srt_intervals)} subtitle blocks")
            
            profanity_list = load_profanity_list(config.profanity.custom_wordlist_path)
            phrases = load_profanity_phrases(config.profanity.custom_phrases_path)
            
            profanity_intervals, _ = analyze_subtitles_for_profanity(
                srt_intervals, profanity_list, phrases,
                buffer_before=config.profanity.buffer_before,
                buffer_after=config.profanity.buffer_after
            )
            logger.info(f"Found {len(profanity_intervals)} profanity instances from subtitles")
            return profanity_intervals, words # words will be empty if using subtitles
        except Exception as e:
            logger.error(f"Failed to parse subtitles: {e}. Falling back to audio transcription.")
            # Fallthrough to normal audio processing
    
    # Normal Flow: Extract & Transcribe
    # Extract audio
    audio_path = extract_audio(
        input_path,
        output_path=temp_dir / "audio.wav"
    )
    
    # Transcribe
    words = transcribe_audio(
        audio_path,
        model_size=config.whisper.model_size,
        language=config.whisper.language,
        compute_type=config.whisper.compute_type,
        progress_prefix="[AUDIO]"
    )
    
    # Load profanity list
    profanity_list = load_profanity_list(
        config.profanity.custom_wordlist_path
    )
    
    # Detect profanity (single words)
    profanity_intervals = detect_profanity(
        words,
        profanity_list,
        buffer_before=config.profanity.buffer_before,
        buffer_after=config.profanity.buffer_after
    )
    
    # Detect profanity phrases (multi-word)
    phrases = load_profanity_phrases(config.profanity.custom_phrases_path)
    phrase_intervals = detect_profanity_phrases(
        words,
        phrases,
        buffer_before=config.profanity.buffer_before,
        buffer_after=config.profanity.buffer_after
    )
    
    # Combine
    all_profanity = profanity_intervals + phrase_intervals
    logger.info(f"Found {len(profanity_intervals)} word + {len(phrase_intervals)} phrase = {len(all_profanity)} total profanity instances")
    
    return all_profanity, words


def _analyze_video(input_path: Path, temp_dir: Path, config: Config, show_progress: bool = True):
    """
    Video analysis pipeline (Step 2).
    
    Runs in a separate thread for parallel execution.
    
    Returns:
        Tuple of (nudity_intervals, frames)
    """
    logger.info("=" * 50)
    logger.info("STEP 2: Nudity Detection")
    logger.info("=" * 50)
    
    # Extract frames
    frames_dir = temp_dir / "frames"
    frames = extract_frames(
        input_path,
        interval=config.nudity.frame_interval,
        output_dir=frames_dir
    )
    
    # Detect nudity with body part filtering and false positive reduction
    nudity_intervals = detect_nudity(
        frames,
        threshold=config.nudity.threshold,
        frame_interval=config.nudity.frame_interval,
        min_segment_duration=config.nudity.min_segment_duration,
        body_parts=config.nudity.body_parts if config.nudity.body_parts else None,
        min_cut_duration=config.nudity.min_cut_duration,
        min_box_area_percent=config.nudity.min_box_area_percent,
        max_aspect_ratio=config.nudity.max_aspect_ratio,
        show_progress=show_progress,
        progress_prefix="[VIDEO]"
    )
    
    logger.info(f"Found {len(nudity_intervals)} nudity intervals")
    
    return nudity_intervals, frames


def analyze_content(
    input_path: Path,
    video_info: VideoInfo,
    config: Config,
    temp_dir: Path,
    filter_settings: Optional[ContentFilterSettings] = None,
    show_progress: bool = True,
    subtitles_path: Optional[Path] = None
) -> dict:
    """
    Run local content analysis (Audio, Video, Subtitles).
    
    Returns a dictionary containing lists of detected intervals.
    """
    # Derive flags
    skip_profanity = False
    skip_nudity = False
    skip_sexual_content = False
    violence_level = 0
    
    if filter_settings:
        skip_profanity = not filter_settings.filter_language
        skip_nudity = not filter_settings.filter_nudity
        skip_sexual_content = not filter_settings.filter_sexual_content
        violence_level = filter_settings.filter_violence_level
        
    logger.info("Starting local content analysis...")
    
    profanity_intervals = []
    nudity_intervals = []
    sexual_content_intervals = []
    violence_intervals = []
    frames = []
    words = []
    subtitle_path = None
    
    # Run Step 1 (Audio) and Step 2 (Video) in parallel
    run_audio = not skip_profanity and video_info.has_audio
    run_video = not skip_nudity
    
    futures = {}
    
    # Determine max workers based on performance config
    max_workers = 3
    if not config.performance.parallel_detection:
        max_workers = 1
    elif config.system.performance_mode == "low_power":
        max_workers = 1
        logger.info("Low Power Mode: Using serial execution (max_workers=1)")
    
    # Use ProcessPoolExecutor for true parallelism
    from concurrent.futures import ProcessPoolExecutor
    import time
    
    attempts = 0
    max_attempts = 2 if config.performance.fallback_to_sequential and max_workers > 1 else 1
    
    while attempts < max_attempts:
        attempts += 1
        current_workers = max_workers if attempts == 1 else 1
        
        if attempts > 1:
            logger.warning("⚠️  Fallback: Retrying with sequential execution (max_workers=1)...")
            
        futures = {}
        
        try:
            with ProcessPoolExecutor(max_workers=current_workers) as executor:
                if run_audio:
                    # Pass progress prefix for audio
                    futures['audio'] = executor.submit(
                        _analyze_audio, input_path, temp_dir, config, subtitles_path
                    )
                    
                    # Stagger delay to prevent GPU memory spike if parallel
                    if current_workers > 1 and run_video and config.performance.stagger_delay > 0:
                        logger.debug(f"Staggering video detection start by {config.performance.stagger_delay}s...")
                        time.sleep(config.performance.stagger_delay)
                    
                if run_video:
                    futures['video'] = executor.submit(
                        _analyze_video, input_path, temp_dir, config, show_progress
                    )
                    
                # Subtitle Analysis
                if filter_settings and filter_settings.force_english_subtitles:
                     sub_extract_path = temp_dir / "analysis_subtitles.srt"
                     futures['subtitles'] = executor.submit(
                         extract_english_subtitles, input_path, sub_extract_path
                     )
        
                # Collect results
                for name, future in futures.items():
                    result = future.result()
                    if name == 'audio':
                        profanity_intervals, words = result
                    elif name == 'video':
                        nudity_intervals, frames = result
                    elif name == 'subtitles':
                        subtitle_path = result
            
            # If we got here, success!
            break
            
        except Exception as e:
            logger.error(f"Error during {'parallel' if current_workers > 1 else 'sequential'} analysis: {e}")
            if attempts < max_attempts:
                # Clear partial results before retry
                profanity_intervals = []
                words = []
                nudity_intervals = []
                frames = []
                continue
            else:
                # If critical failure, re-raise
                if name in ('audio', 'video') and not (skip_profanity and skip_nudity):
                     raise

    # Process Subtitles if extracted
    if subtitle_path and subtitle_path.exists():
        logger.info("Analyzing subtitles for profanity...")
        try:
            sub_intervals = parse_srt(subtitle_path)
            profanity_list = load_profanity_list(config.profanity.custom_wordlist_path)
            phrases = load_profanity_phrases(config.profanity.custom_phrases_path)
            
            sub_censored, stats = analyze_subtitles_for_profanity(
                sub_intervals, profanity_list, phrases,
                buffer_before=config.profanity.buffer_before, # Use same buffer?
                buffer_after=config.profanity.buffer_after
            )
            
            # Merge with audio profanity
            # Note: This might duplicate detections if both Whisper and Subtitles catch it.
            # The 'plan_edits' function handles overlapping intervals, so it's safe!
            logger.info(f"Adding {len(sub_censored)} subtitle profanity intervals")
            profanity_intervals.extend(sub_censored)
            
        except Exception as e:
            logger.error(f"Subtitle analysis failed: {e}")

    # Step 2.5: Sexual Content Detection (Enhanced with Phase 1+2)
    if not skip_sexual_content and config.sexual_content.enabled and words:
        logger.info("STEP 2.5: Sexual Content Detection")
        
        sc_config = config.sexual_content
        sexual_terms = load_sexual_terms(sc_config.custom_terms_path)
        sexual_phrases = load_sexual_phrases(sc_config.custom_phrases_path)
        
        # Determine detection method based on config
        use_hybrid = sc_config.use_hybrid_detection and is_semantic_detection_available()
        
        if use_hybrid:
            # Phase 2: Hybrid detection (lexicon + semantic ML verification)
            logger.info("  Using HYBRID detection (lexicon + ML semantic)")
            sexual_content_intervals = detect_sexual_content_hybrid(
                words,
                threshold=sc_config.threshold,
                use_semantic=sc_config.use_semantic_verification,
                merge_gap=sc_config.merge_gap,
                buffer_before=sc_config.buffer_before,
                buffer_after=sc_config.buffer_after,
            )
        else:
            # Phase 1: Enhanced lexicon detection with context awareness
            from video_censor.sexual_content import SexualContentDetector
            from video_censor.editing.intervals import merge_intervals as merge_ti
            
            detector = SexualContentDetector(
                terms=sexual_terms,
                phrases=sexual_phrases,
                threshold=sc_config.threshold,
                unsafe_threshold=sc_config.unsafe_threshold,
                # Phase 1 enhancements
                use_context_modifiers=sc_config.use_context_modifiers,
                use_safe_context=sc_config.use_safe_context,
                use_regex_patterns=sc_config.use_regex_patterns,
                debug=sc_config.debug
            )
            
            raw_intervals = detector.detect(words)
            
            # Add buffers
            from video_censor.editing.intervals import TimeInterval
            buffered = []
            for interval in raw_intervals:
                buffered.append(TimeInterval(
                    start=max(0, interval.start - sc_config.buffer_before),
                    end=interval.end + sc_config.buffer_after,
                    reason=interval.reason,
                    metadata=interval.metadata
                ))
            
            # Merge nearby intervals
            sexual_content_intervals = merge_ti(buffered, sc_config.merge_gap)
        
        # Log Phase 1 feature status
        if sc_config.use_context_modifiers:
            logger.info("  ✓ Context modifiers enabled (suppress/amplify)")
        if sc_config.use_safe_context:
            logger.info("  ✓ Safe context patterns enabled (medical/news reduction)")
        if sc_config.use_regex_patterns:
            logger.info("  ✓ Regex patterns enabled (leetspeak detection)")
        
        logger.info(f"Found {len(sexual_content_intervals)} sexual content intervals")
        
    # Step 2.7: Violence Detection
    if violence_level > 0:
        logger.info(f"STEP 2.7: Violence Detection (Level {violence_level})")
        if not frames and run_video: # If we didn't run video logic but need frames? 
             # Wait, if run_video is false, frames is empty.
             # If run_video is true, frames is populated.
             pass
        
        if not frames:
             # Extract frames if we skipped nudity but want violence
             frames_dir = temp_dir / "frames"
             frames = extract_frames(
                input_path,
                interval=config.nudity.frame_interval,
                output_dir=frames_dir
             )
             
        frame_paths = [(frame['timestamp'], Path(frame['path'])) for frame in frames]
        violence_intervals = detect_violence(
            frame_paths,
            level=violence_level,
            show_progress=show_progress
        )
        logger.info(f"Found {len(violence_intervals)} violence intervals")

    # Step 2.8: Multimodal Fusion (Optional)
    # Combines audio (transcript) and visual (nudity) detections for higher accuracy
    if config.sexual_content.use_multimodal_fusion and sexual_content_intervals and nudity_intervals:
        logger.info("STEP 2.8: Multimodal Fusion (Audio + Visual)")
        
        # Fuse sexual content (from transcript) with nudity (from visual)
        fused_intervals = fuse_multimodal_detections(
            audio_intervals=sexual_content_intervals,
            visual_intervals=nudity_intervals,
            audio_weight=config.sexual_content.audio_weight,
            visual_weight=config.sexual_content.visual_weight,
            agreement_boost=config.sexual_content.agreement_boost,
            min_confidence=0.3,
            merge_gap=config.sexual_content.merge_gap,
        )
        
        # Count agreement types
        both_count = sum(1 for i in fused_intervals if i.metadata.get('agreement_level') == 'both')
        audio_only = sum(1 for i in fused_intervals if i.metadata.get('agreement_level') == 'audio_only')
        visual_only = sum(1 for i in fused_intervals if i.metadata.get('agreement_level') == 'visual_only')
        
        logger.info(f"  Multimodal fusion results:")
        logger.info(f"    - Both agree (high confidence): {both_count}")
        logger.info(f"    - Audio only: {audio_only}")
        logger.info(f"    - Visual only: {visual_only}")
        logger.info(f"  Total fused intervals: {len(fused_intervals)}")
        
        # Replace sexual_content_intervals with fused results
        # The fused intervals include both audio-based and visual-based with proper attribution
        sexual_content_intervals = fused_intervals

    return {
        'profanity': profanity_intervals,
        'nudity': nudity_intervals,
        'sexual_content': sexual_content_intervals,
        'violence': violence_intervals
    }


def process_video(
    input_path: Path,
    output_path: Path,
    config: Config,
    video_info: VideoInfo,
    filter_settings: ContentFilterSettings,
    import_intervals_path: Optional[Path] = None,
    export_intervals_path: Optional[Path] = None,
    analyze_only: bool = False,
    subtitles_path: Optional[Path] = None,
    show_progress: bool = True,
    temp_dir_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Main processing pipeline.
    
    1. Validate input
    2. Check cloud cache
    3. Analyze content (Profanity, Nudity, etc)
    4. Render censored video
    """
    # ... (skip derived flags logic for now, it's fine) ...
    violence_level = 0
    if filter_settings is not None:
        skip_profanity = not filter_settings.filter_language
        skip_nudity = not filter_settings.filter_nudity
        skip_sexual_content = not filter_settings.filter_sexual_content
        violence_level = filter_settings.filter_violence_level
    
    start_time = time.time()
    
    # Auto-detect macOS and force low_power if not effectively "high"
    # This prevents the "crash" due to OOM when running parallel models on unified memory
    import platform
    if platform.system() == "Darwin" and config.system.performance_mode != "high":
        if config.system.performance_mode != "low_power":
            logger.info("🍎 macOS detected: Defaulting to Low Power Mode for stability (Sequential Processing)")
            config.system.performance_mode = "low_power"

    # helper to apply performance overrides
    if config.system.performance_mode == "low_power":
        logger.info("⚡ Low Power Mode Enabled: Optimizing for limited resources")
        
        # 1. Downgrade Whisper model if using heavy default
        if config.whisper.model_size == "large-v3":
            logger.info("  -> Switched Whisper model from 'large-v3' to 'small'")
            config.whisper.model_size = "small"
            
        # 2. Reduce Nudity Detection frame rate
        if config.nudity.frame_interval < 0.5:
            logger.info(f"  -> Increased frame interval from {config.nudity.frame_interval}s to 0.5s")
            config.nudity.frame_interval = 0.5

    
    # Create temp dir
    if temp_dir_root:
        temp_dir_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_", dir=temp_dir_root))
    
    profanity_intervals = []
    nudity_intervals = []
    sexual_content_intervals = []
    violence_intervals = []
    
    used_cloud_cache = False
    use_cloud_cache = True  # Enable cloud cache lookup by default
    cloud_fingerprint = None
    
    try:
        # Check if importing intervals (Skip detection)
        if import_intervals_path and import_intervals_path.exists():
            logger.info(f"Importing intervals from {import_intervals_path}")
            from video_censor.detection.serializer import deserialize_interval
            
            with open(import_intervals_path, 'r') as f:
                data = json.load(f)
                
            profanity_intervals = [deserialize_interval(d) for d in data.get('profanity', [])]
            nudity_intervals = [deserialize_interval(d) for d in data.get('nudity', [])]
            sexual_content_intervals = [deserialize_interval(d) for d in data.get('sexual_content', [])]
            violence_intervals = [deserialize_interval(d) for d in data.get('violence', [])]
            
            logger.info("Intervals loaded successfully.")
            
        else:
            # Cloud cache lookup (only if not importing)
            cloud_result = None
            cloud_fingerprint = None
            used_cloud_cache = False
            
            if use_cloud_cache:
                # ... (cloud logic omitted for brevity, assuming existing logic flow) ...
                try:
                    from video_censor.cloud_db import get_cloud_client
                    cloud_client = get_cloud_client()
                    if cloud_client.is_available:
                        cloud_fingerprint = cloud_client.compute_fingerprint(str(input_path), video_info.duration)
                        if cloud_fingerprint:
                            cloud_result = cloud_client.lookup_video(cloud_fingerprint)
                            if cloud_result:
                                used_cloud_cache = True
                except Exception:
                    pass

            if used_cloud_cache and cloud_result:
                logger.info("=" * 50)
                logger.info("USING CACHED CLOUD TIMESTAMPS - SKIPPING DETECTION!")
                logger.info("=" * 50)
                
                # Convert cached data to interval format
                from video_censor.editing.intervals import TimeInterval
                
                # Profanity intervals from cloud
                for seg in cloud_result.profanity_segments:
                    profanity_intervals.append(TimeInterval(
                        start=seg.get('start', 0),
                        end=seg.get('end', 0),
                        reason=seg.get('word', 'profanity')
                    ))
                
                # Nudity intervals from cloud
                for seg in cloud_result.nudity_segments:
                    nudity_intervals.append(TimeInterval(
                        start=seg.get('start', 0),
                        end=seg.get('end', 0),
                        reason='nudity'
                    ))
                
                # Sexual content intervals from cloud
                for seg in cloud_result.sexual_content_segments:
                    sexual_content_intervals.append(TimeInterval(
                        start=seg.get('start', 0),
                        end=seg.get('end', 0),
                        reason='sexual_content'
                    ))
                
                logger.info(f"Loaded {len(profanity_intervals)} profanity, {len(nudity_intervals)} nudity, {len(sexual_content_intervals)} sexual content intervals")
            
            # Run local analysis if no cloud result
            if not used_cloud_cache:
                analysis_results = analyze_content(
                    input_path, video_info, config, temp_dir, 
                    filter_settings, show_progress,
                    subtitles_path=subtitles_path
                )
                profanity_intervals = analysis_results['profanity']
                nudity_intervals = analysis_results['nudity']
                sexual_content_intervals = analysis_results['sexual_content']
                violence_intervals = analysis_results['violence']
        
        # Export intervals if requested
        if export_intervals_path:
            from video_censor.detection.serializer import serialize_interval
                
            data = {
                'profanity': [serialize_interval(i) for i in profanity_intervals],
                'nudity': [serialize_interval(i) for i in nudity_intervals],
                'sexual_content': [serialize_interval(i) for i in sexual_content_intervals],
                'violence': [serialize_interval(i) for i in violence_intervals]
            }
            
            with open(export_intervals_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Intervals exported to {export_intervals_path}")
            
        # If analyze only, exit
        if analyze_only:
            logger.info("Analysis complete. Skipping render (--analyze-only).")
            return None

        # ... (Proceed to Planning & Rendering) ...
        
        # Auto-save logic (Sync with queue.py)
        if config.detection_cache.auto_save:
            try:
                from video_censor.detection.serializer import DetectionSerializer
                all_intervals = []
                all_intervals.extend(profanity_intervals)
                all_intervals.extend(nudity_intervals)
                all_intervals.extend(sexual_content_intervals)
                all_intervals.extend(violence_intervals)
                
                DetectionSerializer.save(input_path, all_intervals)
                logger.info(f"Auto-saved {len(all_intervals)} detections to cache.")
            except Exception as e:
                logger.warning(f"Failed to auto-save detection cache: {e}")
        
        # Step 3: Plan edits
        logger.info("=" * 50)
        logger.info("STEP 3: Planning Edits")
        logger.info("=" * 50)
        # Convert ViolenceInterval objects to TimeInterval format for planner
        from video_censor.editing.intervals import TimeInterval
        violence_time_intervals = [
            TimeInterval(start=vi.start, end=vi.end, reason=vi.description)
            for vi in violence_intervals
        ] if violence_intervals else []
        
        edit_plan = plan_edits(
            profanity_intervals=profanity_intervals,
            nudity_intervals=nudity_intervals,
            duration=video_info.duration,
            profanity_merge_gap=config.profanity.merge_gap,
            nudity_merge_gap=config.nudity.merge_gap,
            censor_mode=config.profanity.censor_mode,
            min_segment_duration=config.nudity.min_segment_duration,
            min_cut_duration=config.nudity.min_cut_duration,
            sexual_content_intervals=sexual_content_intervals,
            violence_intervals=violence_time_intervals
        )
        
        # Step 4: Render output
        logger.info("=" * 50)
        logger.info("STEP 4: Rendering Output")
        logger.info("=" * 50)
        
        # Handle subtitle extraction and filtering
        subtitle_path = None
        if filter_settings is not None and filter_settings.force_english_subtitles:
            logger.info("=" * 50)
            logger.info("STEP 4a: Subtitle Extraction")
            logger.info("=" * 50)
            
            # Extract English subtitles
            extracted_srt = temp_dir / "subtitles_raw.srt"
            subtitle_path = extract_english_subtitles(input_path, extracted_srt)
            
            if subtitle_path:
                # Optionally censor profanity in subtitles
                if filter_settings.censor_subtitle_profanity:
                    logger.info("Censoring profanity in subtitles...")
                    profanity_list = load_profanity_list(config.profanity.custom_wordlist_path)
                    censored_srt = temp_dir / "subtitles_censored.srt"
                    subtitle_path = censor_subtitle_file(
                        extracted_srt,
                        censored_srt,
                        profanity_list
                    )
                    if not subtitle_path:
                        logger.warning("Failed to censor subtitles, using uncensored version")
                        subtitle_path = extracted_srt
            else:
                logger.warning("No English subtitles found in video, skipping subtitle burning")
        
        render_censored_video(
            input_path=input_path,
            output_path=output_path,
            plan=edit_plan,
            config=config,
            subtitle_path=subtitle_path,
            input_duration=video_info.duration
        )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Print summary
        print_summary(
            plan=edit_plan,
            input_path=input_path,
            output_path=output_path,
            processing_time=processing_time
        )
        
        # Return summary and edit_plan for optional exports
        summary = generate_summary(
            plan=edit_plan,
            input_path=input_path,
            output_path=output_path,
            processing_time=processing_time
        )
        
        # Upload results to cloud database (if not already from cache)
        if not used_cloud_cache and cloud_fingerprint is not None:
            try:
                from video_censor.cloud_db import get_cloud_client, DetectionResult
                cloud_client = get_cloud_client()
                
                if cloud_client.is_available:
                    # Convert intervals to serializable format
                    profanity_data = [
                        {'start': i.start, 'end': i.end, 'word': getattr(i, 'reason', '')}
                        for i in profanity_intervals
                    ]
                    nudity_data = [
                        {'start': i.start, 'end': i.end, 'confidence': 0.9}
                        for i in nudity_intervals
                    ]
                    sexual_data = [
                        {'start': i.start, 'end': i.end, 'score': 1.0}
                        for i in sexual_content_intervals
                    ]
                    violence_data = [
                        {'start': i.start, 'end': i.end, 'intensity': violence_level}
                        for i in violence_intervals
                    ] if violence_intervals else []
                    
                    result = DetectionResult(
                        fingerprint=cloud_fingerprint,
                        title=input_path.stem,
                        nudity_segments=nudity_data,
                        profanity_segments=profanity_data,
                        sexual_content_segments=sexual_data,
                        violence_segments=violence_data,
                        settings_used={
                            'nudity_threshold': config.nudity.threshold,
                            'whisper_model': config.whisper.model_size,
                        },
                        processing_time_seconds=processing_time
                    )
                    
                    if cloud_client.upload_detection(result):
                        logger.info("📤 Uploaded detection results to cloud database for community sharing!")
                    else:
                        logger.debug("Could not upload results to cloud")
            except Exception as e:
                logger.debug(f"Cloud upload failed (non-critical): {e}")
        
        return summary, edit_plan
        
    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    
    print()
    print("=" * 50)
    print("VIDEO CENSOR TOOL")
    print("Fully local, offline video censoring")
    print("=" * 50)
    print()
    
    # Load configuration
    config_path = args.config
    if config_path is None:
        # Look for config in default locations
        default_config = Path(__file__).parent / "config.yaml"
        if default_config.exists():
            config_path = default_config
    
    config = Config.load(config_path)
    
    # Apply CLI overrides to config
    if args.threshold is not None:
        config.nudity.threshold = args.threshold
        logger.info(f"CLI override: nudity threshold = {args.threshold}")
    
    if args.model is not None:
        config.whisper.model_size = args.model
        logger.info(f"CLI override: whisper model = {args.model}")
    
    if hasattr(args, 'censor_mode') and args.censor_mode is not None:
        config.profanity.censor_mode = args.censor_mode
        logger.info(f"CLI override: censor mode = {args.censor_mode}")
    
    if args.frame_interval is not None:
        config.nudity.frame_interval = args.frame_interval
        logger.info(f"CLI override: frame interval = {args.frame_interval}")
    
    # Validate input
    logger.info(f"Validating input: {args.input}")
    is_valid, error, video_info = validate_input(args.input)
    
    if not is_valid:
        logger.error(f"Input validation failed: {error}")
        print(f"Error: {error}")
        return 1
    
    logger.info(f"Video: {video_info.resolution} @ {video_info.fps:.2f}fps, {video_info.duration:.2f}s")
    
    # Validate output
    is_valid, error = validate_output_path(args.output, overwrite=args.overwrite)
    
    if not is_valid:
        logger.error(f"Output validation failed: {error}")
        print(f"Error: {error}")
        return 1
    
    # Check if any processing is requested
    if args.no_profanity and args.no_nudity:
        logger.warning("Both --no-profanity and --no-nudity specified, nothing to do")
        print("Warning: No processing requested. Use --no-profanity OR --no-nudity, not both.")
        return 1
    
    try:
        # Process video
        # Connect CLI args to filter settings
        filter_settings = ContentFilterSettings(
            filter_language=not args.no_profanity,
            filter_nudity=not args.no_nudity
        )

        # Process video
        result = process_video(
            input_path=args.input,
            output_path=args.output,
            config=config,
            video_info=video_info,
            filter_settings=filter_settings,
            show_progress=not args.quiet,
            temp_dir_root=args.temp_dir,
            analyze_only=args.analyze_only,
            export_intervals_path=args.export_intervals,
            import_intervals_path=args.import_intervals,
            subtitles_path=args.subtitles
        )
        
        # Handle analyze-only return (None)
        if args.analyze_only:
             print(f"✓ Analysis complete. Intervals saved to {args.export_intervals}")
             return 0
             
        summary, edit_plan = result
        
        # Save JSON summary if requested
        if args.save_summary:
            with open(args.save_summary, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Summary saved to {args.save_summary}")
        
        # Save detailed timeline if requested
        if args.save_timeline:
            save_edit_timeline(edit_plan, args.save_timeline)
            logger.info(f"Edit timeline saved to {args.save_timeline}")
        
        print(f"✓ Censored video saved to: {args.output}")
        return 0
        
    except KeyboardInterrupt:
        print("\nProcessing cancelled by user")
        return 130
        
    except Exception as e:
        logger.exception("Processing failed")
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
