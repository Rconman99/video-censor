import logging
import sys
from pathlib import Path
from video_censor.config import Config
from video_censor.editing.renderer import extract_segment, AudioEdit

# Setup logging to see debug output
logging.basicConfig(level=logging.DEBUG)

def test_hardware_encoder():
    config = Config()
    config.output.hardware_acceleration = "auto"
    config.output.video_codec = "libx264"
    config.output.audio_codec = "aac"
    config.output.audio_bitrate = "192k"
    
    input_path = Path("/Volumes/20tb/temp_video_censor/test_clip.mkv")
    output_path = Path("/Volumes/20tb/temp_video_censor/test_clip_segment.mkv")
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        return

    print("Running extract_segment with hardware acceleration 'auto'...")
    
    # Create a dummy audio edit to force rendering logic
    # (Though now extract_segment re-encodes video if HW accel is on regardless of audio edits?)
    # Let's check logic: if hw_args: RE-ENCODE VIDEO. Yes.
    
    try:
        extract_segment(
            input_path=input_path,
            output_path=output_path,
            start=10.0,
            end=20.0,
            audio_edits=[], # No audio edits
            config=config
        )
        print("Success: extract_segment completed.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_hardware_encoder()
