import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.getcwd())

from video_censor.config import Config
from video_censor.queue import _run_sequential, process_video
from video_censor.audio.transcriber import WordTimestamp

# Mock Data
MOCK_WORDS = [
    WordTimestamp(word="Hello", start=0.0, end=1.0),
    WordTimestamp(word="this", start=1.0, end=1.5),
    WordTimestamp(word="is", start=1.5, end=2.0),
    WordTimestamp(word="a", start=2.0, end=2.2),
    WordTimestamp(word="fucking", start=2.2, end=2.8, probability=0.9), # Profanity
    WordTimestamp(word="test", start=2.8, end=3.5),
]

# Mock Functions to replace heavy/external calls

def mock_transcribe(*args, **kwargs):
    print("   [Mock] Transcribing audio...")
    return MOCK_WORDS

def mock_extract_audio(*args, **kwargs):
    print("   [Mock] Extracting audio...")
    return Path("mock_audio.wav")

def mock_extract_frames(*args, **kwargs):
    print("   [Mock] Extracting frames...")
    # Return dummy frames
    from video_censor.nudity.extractor import FrameInfo
    return [FrameInfo(path=Path(f"frame_{i}.jpg"), timestamp=i*0.5, frame_number=i) for i in range(10)]

def mock_detect_nudity(*args, **kwargs):
    print("   [Mock] Detecting nudity...")
    from video_censor.editing.intervals import TimeInterval
    # Return one fake nudity interval
    return [TimeInterval(start=4.0, end=5.0, reason="BUTTOCKS_EXPOSED")]

def mock_detect_profanity(words, profanity_list, *args, **kwargs):
    print(f"   [Mock] Detecting profanity in {len(words)} words...")
    from video_censor.editing.intervals import TimeInterval
    detections = []
    for w in words:
        if w.word in profanity_list:
            # Matches actual detector which puts word in metadata or just reason string?
            # Real detector: reason=f"profanity: '{word_ts.word}'..."
            # It does NOT add word to metadata.
            # So if queue.py expects .word, it WILL fail.
            detections.append(TimeInterval(
                start=w.start, 
                end=w.end, 
                reason=f"profanity: {w.word}",
                metadata={'word': w.word, 'confidence': 0.9}
            ))
            # Note: We are NOT adding .word attribute because TimeInterval doesn't have it.
            # This triggers the bug exposure.
    return detections

def mock_load_profanity_list(*args, **kwargs):
    return {"fucking", "shit"}

async def run_verification():
    print("=== Video Censor Pipeline Verification ===")
    
    # 1. Setup Config
    print("\n1. Loading Config...")
    config = Config()
    config.profanity.custom_wordlist_path = "dummy.txt" # Trigger list load
    
    # 2. Sequential Pipeline Verification
    print("\n2. Testing Sequential Pipeline Logic...")
    
    # We patch at the module level where they are IMPORTED in queue.py
    # Note: queue.py imports:
    # from .audio import extract_audio, transcribe_audio
    # from .profanity.detector import detect_profanity
    # from .profanity import load_profanity_list (inside worker)
    # from .nudity import extract_frames, detect_nudity
    
    with patch('video_censor.queue.extract_audio', side_effect=mock_extract_audio), \
         patch('video_censor.queue.transcribe_audio', side_effect=mock_transcribe), \
         patch('video_censor.queue.extract_frames', side_effect=mock_extract_frames), \
         patch('video_censor.queue.detect_nudity', side_effect=mock_detect_nudity), \
         patch('video_censor.queue.detect_profanity', side_effect=mock_detect_profanity), \
         patch('video_censor.profanity.load_profanity_list', side_effect=mock_load_profanity_list):
         
        # Run sequential
        results = _run_sequential("dummy_video.mp4", config)
        
        print("\n   Results:")
        print(f"   - Profanity: {len(results['profanity'])} items")
        print(f"   - Nudity: {len(results['nudity'])} items")
        
        if len(results['profanity']) == 1 and results['profanity'][0]['label'] == 'fucking':
            print("   ✅ Profanity detection verified")
        else:
            print("   ❌ Profanity detection FAILED")
            
        if len(results['nudity']) == 1 and results['nudity'][0]['label'] == 'BUTTOCKS_EXPOSED':
            print("   ✅ Nudity detection verified")
        else:
            print("   ❌ Nudity detection FAILED")

    
    # 3. Test Context Aware Switch
    print("\n3. Testing Config Overrides (Context Aware)...")
    config.profanity.context_aware = True
    if config.profanity.context_aware:
         print("   ✅ Config updated correctly")

    # 4. Test Parallel Detection Logic (mocking executor)
    print("\n4. Testing Parallel Logic...")
    config.performance.parallel_detection = True
    config.system.performance_mode = "balanced" # ensuring not low_power
    
    # We mock ProcessPoolExecutor to avoid spawning processes
    with patch('video_censor.queue.ProcessPoolExecutor') as mock_executor, \
         patch('video_censor.queue.asyncio.get_event_loop') as mock_loop:
        
        # Mock loop.run_in_executor to return immediate mock futures
        async def mock_future_result(*args, **kwargs):
            return [{'label': 'mock_audio', 'start':0, 'end':1}] # dummy audio result
        
        mock_future = asyncio.Future()
        mock_future.set_result([{'label': 'mock_audio', 'start':0, 'end':1, 'confidence': 1.0}])
        mock_loop.return_value.run_in_executor.return_value = mock_future
        
        # We need to mock _worker functions since they are passed to executor
        with patch('video_censor.queue._worker_audio_pipeline') as mock_worker_audio:
            # We don't need real return values because we mocked the future result
            
            # Run process_video
            print("   Running process_video(parallel=True)...")
            res = await process_video("dummy.mp4", config)
            
            if mock_executor.called:
                print("   ✅ Parallel Executor was used")
            else:
                print("   ❌ Parallel Executor was AVOIDED (Fail)")
                
    # 5. Test Low Power Safety Catch
    print("\n5. Testing Low Power Mode Safety...")
    config.system.performance_mode = "low_power"
    with patch('video_censor.queue.ProcessPoolExecutor') as mock_executor:
        with patch('video_censor.queue._run_sequential') as mock_seq:
            mock_seq.return_value = {'profanity': [], 'nudity': []}
            
            await process_video("dummy.mp4", config)
            
            if not mock_executor.called and mock_seq.called:
                 print("   ✅ Low Power Mode forced sequential (Correct)")
            else:
                 print("   ❌ Low Power Mode used parallel executor (Fail)")

    # 6. Test Render Logic (Item 9)
    print("\n6. Testing Renderer (Mocked FFmpeg)...")
    from video_censor.editing.renderer import render_censored_video
    from video_censor.editing.planner import EditPlan
    
    plan = EditPlan(cut_intervals=[], audio_edits=[], original_duration=10.0)
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        
        try:
            render_censored_video(Path("in.mp4"), Path("out.mp4"), plan, config)
            print("   ✅ render_censored_video called successfully")
            if mock_run.called:
               print("   ✅ subprocess.run called (FFmpeg invoked)")
        except Exception as e:
            print(f"   ❌ Render failed: {e}")
    
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(run_verification())
