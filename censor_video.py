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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent))

from video_censor.config import Config
from video_censor.validator import validate_input, validate_output_path, VideoInfo
from video_censor.audio import extract_audio, transcribe_audio
from video_censor.profanity import load_profanity_list, load_profanity_phrases, detect_profanity, detect_profanity_phrases
from video_censor.nudity import extract_frames, detect_nudity
from video_censor.sexual_content import detect_sexual_content, load_sexual_terms, load_sexual_phrases
from video_censor.violence import detect_violence
from video_censor.editing import merge_intervals, plan_edits, render_censored_video
from video_censor.reporting import generate_summary, print_summary, save_edit_timeline
from video_censor.preferences import ContentFilterSettings
from video_censor.subtitles import extract_english_subtitles, censor_subtitle_file, has_english_subtitles

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


def _analyze_audio(input_path: Path, temp_dir: Path, config: Config):
    """
    Audio analysis pipeline (Step 1).
    
    Runs in a separate thread for parallel execution.
    
    Returns:
        Tuple of (profanity_intervals, words)
    """
    logger.info("=" * 50)
    logger.info("STEP 1: Profanity Detection")
    logger.info("=" * 50)
    
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
        compute_type=config.whisper.compute_type
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
    
    # Detect nudity with body part filtering
    nudity_intervals = detect_nudity(
        frames,
        threshold=config.nudity.threshold,
        frame_interval=config.nudity.frame_interval,
        min_segment_duration=config.nudity.min_segment_duration,
        body_parts=config.nudity.body_parts if config.nudity.body_parts else None,
        min_cut_duration=config.nudity.min_cut_duration,
        show_progress=show_progress
    )
    
    logger.info(f"Found {len(nudity_intervals)} nudity intervals")
    
    return nudity_intervals, frames


def process_video(
    input_path: Path,
    output_path: Path,
    config: Config,

    video_info: VideoInfo,
    skip_profanity: bool = False,
    skip_nudity: bool = False,
    skip_sexual_content: bool = False,
    show_progress: bool = True,
    filter_settings: "Optional[ContentFilterSettings]" = None,
    temp_dir_root: Optional[Path] = None
) -> None:
    """
    Main processing pipeline.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        config: Configuration settings
        video_info: Validated video information
        skip_profanity: Skip profanity detection (overridden by filter_settings)
        skip_nudity: Skip nudity detection (overridden by filter_settings)
        skip_sexual_content: Skip sexual content detection (overridden by filter_settings)
        show_progress: Show progress indicators
        filter_settings: Optional ContentFilterSettings to control what gets filtered
        temp_dir_root: Optional directory for temporary files
    """
    # If filter_settings provided, derive skip flags from it
    violence_level = 0
    if filter_settings is not None:
        skip_profanity = not filter_settings.filter_language
        skip_nudity = not filter_settings.filter_nudity
        skip_sexual_content = not filter_settings.filter_sexual_content
        violence_level = filter_settings.filter_violence_level
        # Note: filter_romance_level and filter_mature_themes are for future use
    
    start_time = time.time()
    # Create temp dir in specified location or default
    if temp_dir_root:
        temp_dir_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_", dir=temp_dir_root))
    
    try:
        profanity_intervals = []
        nudity_intervals = []
        sexual_content_intervals = []
        violence_intervals = []
        frames = []  # Store extracted frames for reuse
        words = []  # Store for sexual content detection
        
        # Run Step 1 (Audio) and Step 2 (Video) in parallel
        run_audio = not skip_profanity and video_info.has_audio
        run_video = not skip_nudity
        
        futures = {}
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            if run_audio:
                futures['audio'] = executor.submit(
                    _analyze_audio, input_path, temp_dir, config
                )
            else:
                if skip_profanity:
                    logger.info("Skipping profanity detection (--no-profanity)")
                elif not video_info.has_audio:
                    logger.info("Skipping profanity detection (no audio track)")
            
            if run_video:
                futures['video'] = executor.submit(
                    _analyze_video, input_path, temp_dir, config, show_progress
                )
            else:
                logger.info("Skipping nudity detection (--no-nudity)")
            
            # Collect results as they complete
            for name, future in futures.items():
                try:
                    result = future.result()
                    if name == 'audio':
                        profanity_intervals, words = result
                    elif name == 'video':
                        nudity_intervals, frames = result
                except Exception as e:
                    logger.error(f"Error in {name} analysis: {e}")
                    raise
        
        # Step 2.5: Sexual content detection (dialog-based)
        if not skip_sexual_content and config.sexual_content.enabled and words:
            logger.info("=" * 50)
            logger.info("STEP 2.5: Sexual Content Detection")
            logger.info("=" * 50)
            
            # Load terms and phrases
            sexual_terms = load_sexual_terms(config.sexual_content.custom_terms_path)
            sexual_phrases = load_sexual_phrases(config.sexual_content.custom_phrases_path)
            
            # Detect sexual content from transcript
            sexual_content_intervals = detect_sexual_content(
                words,
                terms=sexual_terms,
                phrases=sexual_phrases,
                threshold=config.sexual_content.threshold,
                unsafe_threshold=config.sexual_content.unsafe_threshold,
                merge_gap=config.sexual_content.merge_gap,
                buffer_before=config.sexual_content.buffer_before,
                buffer_after=config.sexual_content.buffer_after,
                debug=config.sexual_content.debug
            )
            
            logger.info(f"Found {len(sexual_content_intervals)} sexual content intervals to cut")
        elif skip_sexual_content:
            logger.info("Skipping sexual content detection (filter disabled)")
        elif not words:
            logger.info("Skipping sexual content detection (no transcript available)")
        elif not config.sexual_content.enabled:
            logger.info("Skipping sexual content detection (disabled in config)")
        
        # Step 2.7: Violence detection
        if violence_level > 0:
            logger.info("=" * 50)
            logger.info(f"STEP 2.7: Violence Detection (Level {violence_level})")
            logger.info("=" * 50)
            
            # Reuse frames from nudity detection or extract new ones
            if not frames:
                frames_dir = temp_dir / "frames"
                frames = extract_frames(
                    input_path,
                    interval=config.nudity.frame_interval,
                    output_dir=frames_dir
                )
            
            # Convert frames to (timestamp, path) format for violence detector
            frame_paths = [(frame['timestamp'], Path(frame['path'])) for frame in frames]
            
            # Detect violence
            violence_intervals = detect_violence(
                frame_paths,
                level=violence_level,
                threshold=0.3,
                min_segment_duration=0.5,
                buffer_before=0.25,
                buffer_after=0.25,
                merge_gap=1.0,
                show_progress=show_progress
            )
            
            logger.info(f"Found {len(violence_intervals)} violence intervals to cut")
        else:
            logger.info("Skipping violence detection (level 0 - keep all)")
        
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
        summary, edit_plan = process_video(
            input_path=args.input,
            output_path=args.output,
            config=config,
            video_info=video_info,
            skip_profanity=args.no_profanity,
            skip_nudity=args.no_nudity,
            show_progress=not args.quiet,
            temp_dir_root=args.temp_dir
        )
        
        # Save JSON summary if requested
        if args.save_summary:
            import json
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
