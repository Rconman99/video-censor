# Video Censor App — Resource Mapping

> Which patterns from DEVELOPER_RESOURCES_INDEX.md apply to this project

---

## ✅ Applicable Patterns

### Zep Memory (Partial Fit)
**Use case:** Remembering user preferences across sessions
- Custom wordlists per user
- Threshold preferences per content type
- Recent projects and settings
- **Implementation:** Already have Supabase—could store user prefs there

### Performance Patterns
**Use case:** Video processing is compute-heavy
- Batch processing optimizations
- Progress tracking for long renders
- Hardware acceleration detection
- **Already doing:** FFmpeg HW accel, frame interval sampling

---

## ⚠️ Maybe Applicable (Future)

### LLM Integration
**Use case:** Smarter content understanding
- Context-aware profanity detection (quotes vs actual swearing)
- Scene understanding ("is this medical content or explicit?")
- Custom instructions ("censor violence but not language")
- **Trade-off:** Adds latency, may require cloud API

### Corrective RAG (Conceptually)
**Use case:** Detection validation
- Cross-reference audio + visual detections
- Reduce false positives by requiring multi-signal confirmation
- **Example:** Only blur if BOTH NudeNet detects AND transcript has explicit words

---

## ❌ Not Applicable

| Pattern | Why Not |
|---------|---------|
| Trustworthy RAG | No document retrieval |
| ColBERT RAG | No search/retrieval |
| RAG SQL Router | No multi-database queries |
| DeepTutor | Not educational |
| Hallow Patterns | Not devotional/meditation |
| Citation Systems | No sourcing needed |

---

## Recommended Enhancements (Priority Order)

### 1. Context-Aware Detection (High Value)
Add lightweight LLM to reduce false positives:
```python
# Example: Before censoring, check context
prompt = f"Is this profanity used as a swear or quoted/discussed? Text: '{segment}'"
# Only censor if actually swearing
```
**Model options:** Local (Ollama + small model) or API (Claude Haiku for speed)

### 2. Multi-Signal Confirmation (Medium Value)
Require agreement between detectors:
```python
# Explicit content = visual detection + audio detection
if nudity_score > 0.6 AND has_explicit_transcript:
    censor()
elif nudity_score > 0.9:  # Very high confidence, censor anyway
    censor()
```

### 3. User Preference Sync (Nice to Have)
Leverage existing Supabase:
- Wordlist sync across devices
- Preset sharing (conservative, moderate, permissive)
- Processing history

---

## Integration Points

If adding LLM capabilities, these files need modification:

| File | Change |
|------|--------|
| `video_censor/sexual_content/detector.py` | Add LLM context check |
| `video_censor/config.py` | Add LLM provider settings |
| `config.yaml.example` | Add LLM config section |
| `requirements.txt` | Add `anthropic` or `ollama` |

---

*This mapping helps agents understand which shared patterns to reference and which to ignore.*
