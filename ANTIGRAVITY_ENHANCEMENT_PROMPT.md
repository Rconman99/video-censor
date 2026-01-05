# Video Censor App — Antigravity Enhancement Prompt

Copy everything below the line into Antigravity:

---

## Context

Read these files first to understand the project:
- `CLAUDE.md` — Project architecture, stack, and conventions
- `RESOURCE_MAPPING.md` — Which enhancement patterns apply
- `DEVELOPER_RESOURCES_INDEX.md` — Shared patterns library

## Mission

Enhance the video-censor app to be best-in-class for automatic video censoring. Focus on: detection accuracy, false positive reduction, user experience, and performance.

---

## Enhancement Tasks (Priority Order)

### 1. Context-Aware Profanity Detection (High Priority)

**Problem:** Current detection flags ALL instances of profanity, including quotes, song lyrics, educational content, and sarcastic usage.

**Solution:** Add lightweight LLM check before censoring audio segments.

**Implementation:**
1. Create `video_censor/profanity/context_analyzer.py`
2. When a profanity word is detected, extract surrounding transcript context (±10 words)
3. Send to local LLM (Ollama) or fast API (Claude Haiku) with prompt:
   ```
   You are a content moderation assistant. Determine if this profanity should be censored.
   
   Context: "{surrounding_text}"
   Detected word: "{word}"
   
   Should censor if: genuine swearing, insults, explicit intent
   Should NOT censor if: quoting someone, song lyrics, educational discussion, sarcasm, movie title
   
   Respond with only: CENSOR or SKIP
   ```
4. Add config option: `profanity.context_aware: true/false`
5. Add config option: `profanity.llm_provider: ollama|anthropic|openai`
6. Update `video_censor/profanity/wordlist.py` to call context analyzer

**Files to modify:**
- Create: `video_censor/profanity/context_analyzer.py`
- Modify: `video_censor/audio/transcriber.py` (pass full transcript for context)
- Modify: `video_censor/config.py` (add LLM settings)
- Modify: `config.yaml.example` (add context_aware section)
- Modify: `requirements.txt` (add `anthropic` or `ollama`)

---

### 2. Multi-Signal Confirmation (High Priority)

**Problem:** Single-detector decisions cause false positives. A beach scene triggers nudity detection. The word "ass" in "class" triggers profanity detection.

**Solution:** Require multiple signals before censoring, with confidence weighting.

**Implementation:**
1. Create `video_censor/detection/confidence_merger.py`
2. Implement confidence scoring:
   ```python
   class DetectionConfidence:
       def should_censor(self, signals: dict) -> bool:
           # Audio profanity alone: needs high confidence OR context confirmation
           # Visual nudity alone: needs very high confidence (>0.9)
           # Audio + Visual together: lower threshold acceptable
           # Explicit transcript + nudity: definitely censor
           
           score = 0
           if signals.get('profanity_detected'):
               score += 0.4
           if signals.get('nudity_score', 0) > 0.75:
               score += 0.4
           if signals.get('explicit_dialog'):
               score += 0.3
           if signals.get('context_confirmed'):  # From LLM check
               score += 0.2
               
           return score >= 0.6  # Threshold for censoring
   ```
3. Add config: `detection.require_multi_signal: true/false`
4. Add config: `detection.confidence_threshold: 0.6`

**Files to modify:**
- Create: `video_censor/detection/confidence_merger.py`
- Modify: `video_censor/editing/renderer.py` (use merger before applying effects)
- Modify: `video_censor/config.py`
- Modify: `config.yaml.example`

---

### 3. Smart Frame Sampling (Medium Priority)

**Problem:** Fixed frame interval (0.15s) either misses fast cuts or wastes processing on static scenes.

**Solution:** Adaptive sampling based on scene changes.

**Implementation:**
1. Create `video_censor/nudity/scene_detector.py`
2. Use frame differencing to detect scene changes
3. Sample more frequently during high-motion/scene-change moments
4. Sample less frequently during static scenes (talking heads, landscapes)
   ```python
   def get_sample_frames(video_path: str) -> list[float]:
       # Base interval: 0.5s for static scenes
       # Reduce to 0.1s when scene change detected
       # Always sample first frame of new scene
   ```
5. Add config: `nudity.adaptive_sampling: true/false`

**Files to modify:**
- Create: `video_censor/nudity/scene_detector.py`
- Modify: `video_censor/nudity/detector.py`
- Modify: `video_censor/config.py`

---

### 4. Detection Review UX Improvements (Medium Priority)

**Problem:** Users need to efficiently review and override detections before final render.

**Solution:** Enhance detection_browser.py with better UX.

**Implementation:**
1. Add keyboard shortcuts:
   - `Space` = play/pause at current detection
   - `←/→` = previous/next detection
   - `K` = keep (confirm censor)
   - `S` = skip (remove censor)
   - `E` = expand region
   - `R` = reduce region

2. Add detection type icons (audio 🔊, visual 👁, both ⚠️)

3. Add confidence indicator (color-coded: red=high, yellow=medium, green=low)

4. Add batch actions:
   - "Skip all low confidence"
   - "Skip all audio-only"
   - "Confirm all high confidence"

5. Add detection preview: thumbnail + 2-second clip on hover

**Files to modify:**
- Modify: `ui/detection_browser.py`
- Modify: `ui/timeline.py` (show detection markers)
- Create: `ui/detection_card.py` (reusable detection display component)

---

### 5. Preset System (Medium Priority)

**Problem:** Users have to manually configure for different use cases (family movie night vs. YouTube upload vs. broadcast).

**Solution:** Built-in presets with one-click application.

**Implementation:**
1. Create `video_censor/presets.py`:
   ```python
   PRESETS = {
       "family_friendly": {
           "profanity": {"enabled": True, "context_aware": True},
           "nudity": {"threshold": 0.6, "blur_intensity": "heavy"},
           "violence": {"enabled": True},
       },
       "youtube_safe": {
           "profanity": {"enabled": True, "bleep_style": "tone"},
           "nudity": {"threshold": 0.75},
           "violence": {"enabled": False},
       },
       "broadcast": {
           "profanity": {"enabled": True, "context_aware": True, "strict": True},
           "nudity": {"threshold": 0.5, "blur_intensity": "black"},
       },
       "minimal": {
           "profanity": {"enabled": True, "only_severe": True},
           "nudity": {"threshold": 0.9},
       }
   }
   ```
2. Add preset selector dropdown in UI
3. Allow "Save as custom preset"
4. Sync presets to Supabase for cross-device access

**Files to modify:**
- Create: `video_censor/presets.py`
- Modify: `ui/main_window.py` (add preset selector)
- Modify: `video_censor/config.py` (load from preset)

---

### 6. Performance Optimizations (Lower Priority)

**Implementation:**
1. **Parallel detection:** Run audio transcription and visual detection simultaneously
   ```python
   async def detect_all(video_path):
       audio_task = asyncio.create_task(transcribe_audio(video_path))
       visual_task = asyncio.create_task(detect_nudity(video_path))
       audio_results, visual_results = await asyncio.gather(audio_task, visual_task)
   ```

2. **GPU batching:** Process multiple frames through NudeNet in batches
   
3. **Caching:** Cache detection results by video hash, skip re-detection on re-opens

4. **Progress granularity:** More detailed progress reporting for long videos

**Files to modify:**
- Modify: `video_censor/queue.py` (parallel execution)
- Modify: `video_censor/nudity/detector.py` (batch processing)
- Create: `video_censor/cache.py` (detection caching)

---

### 7. User Preference Sync (Lower Priority)

**Problem:** Custom wordlists and settings don't sync across devices.

**Solution:** Use existing Supabase integration.

**Implementation:**
1. Create `video_censor/sync.py`:
   - `sync_wordlist()` — Push/pull custom words
   - `sync_presets()` — Push/pull custom presets
   - `sync_settings()` — Push/pull config overrides

2. Add UI toggle: "Sync settings to cloud"

3. Handle conflicts (last-write-wins or merge)

**Files to modify:**
- Create: `video_censor/sync.py`
- Modify: `ui/main_window.py` (add sync toggle)
- Modify: `video_censor/profanity/wordlist.py` (load from sync)

---

## Code Standards

Follow these conventions (from CLAUDE.md):
- snake_case for files/functions, PascalCase for classes
- Type hints throughout (Python 3.10+ syntax)
- Config options go in config.yaml, not hardcoded
- UI logic in `ui/`, business logic in `video_censor/`
- Add tests for new functionality in `tests/`

---

## Testing Requirements

For each enhancement:
1. Add unit tests in `tests/`
2. Test edge cases:
   - Very long videos (2+ hours)
   - Videos with no audio
   - Videos with no detectable content
   - Rapid scene changes
   - Multiple simultaneous detections

---

## Deliverables

After implementing, provide:
1. Summary of changes made
2. New/modified files list
3. New config options added
4. Any new dependencies
5. Testing instructions

---

## Start Here

Begin with Enhancement #1 (Context-Aware Profanity Detection) as it provides the highest value improvement. Then proceed through the list in order. Ask clarifying questions before implementing if anything is unclear.
