# Phase 1 Report — Transcription + Silence Detection

## What was built
- `transcription/`: `transcribe()` entrypoint (faster-whisper), chunked audio extraction
  (`audio.py`), disk cache (`cache.py`), silence detection via ffmpeg `silencedetect`
  (`silence.py`), shared types (`types.py`).
- `cli/transcribe_cli.py`: run transcription from the command line, write JSON to a file
  or stdout.
- `eval/smoke_test_transcription.py`: mechanics test on synthetic fixtures (tone/silence
  WAV + macOS `say`-generated speech WAV, both in `eval/vods/`).

## What was tested
- Silence detection against a synthetic file with known silence windows at [8s,11s] and
  [19s,23s] — detected within ~70ms.
- Chunked transcription (12s chunks, 3s overlap, forcing 3+ chunks) on the same file:
  correctly reports zero speech segments on pure tone audio (no hallucinated text at
  chunk boundaries).
- Cache: second call for an identical (path, size, mtime, model_size) returns byte-identical
  output in <1s (no re-invocation of the model).
- Real speech (macOS `say` → 2 sentences, ~4.8s) transcribes with plausible word-level
  timestamps and monotonic, non-negative timings.

## PHASE 1 GATE: PASSED (2026-07-21)

Ran the real acceptance test against `eval/vods/stream_vod_2026-07-18.mp4` (real Twitch
VOD, 2h8m, `medium` model, ~61 min wall-clock — see judgment call #4 below for the speed
note this surfaced).

- **Word-timing spot check**: 6 timestamps spread across the VOD (1min, 15min, 30min,
  70min, 90min, 105min) were checked by the streamer against the real audio — confirmed
  accurate, including several plausible-looking mishears of gaming slang/names that turned
  out to be correct once checked by ear.
- **Silence detection**: confirmed accurate against the actual VOD — the top 5 longest
  detected silences (30.1s, 24.6s, 21.4s, 17.3s, 14.0s, all in the first ~29 minutes) match
  real dead air.
- **One gap in the original spec test as run here**: only one VOD (not the spec's
  "1 clear-speech + 1 noisy game audio" pair) was available, so this hasn't specifically
  stress-tested a *separate* noisy-game-audio-only case — this VOD already has game audio
  bleed throughout, which is likely representative, but flagging that the spec's two-VOD
  design wasn't followed exactly.
- Silence threshold was retuned as a direct result of this test — see judgment call #3
  (updated below), now closed.

Given this, Phase 1 gate is being treated as met and Layer 2 (Analysis) work has started.

## Judgment calls made (need your input)

1. **Cache key = path + size + mtime, not a content hash.** Hashing the full bytes of a
   multi-hour/multi-GB VOD just to get a cache key would be slow and largely defeats the
   point of caching. Risk: a file edited in place while keeping identical size and mtime
   won't invalidate the cache — not a realistic case in this pipeline's normal usage, but
   flagging it since it's a deliberate accuracy-for-speed tradeoff.

2. **Chunk length 20 min, overlap 15s** (`transcribe.py`). Long enough that Whisper's
   internal context still helps quality, short enough to bound per-chunk memory on a
   multi-hour VOD. Boundary handling: each chunk decodes `chunk_len` seconds but only
   "owns" words up to `chunk_len - overlap`; the next chunk re-transcribes the overlap
   with full leading context. 15s assumes no single spoken sentence runs longer than that
   uninterrupted — reasonable for stream commentary, could clip a very long monologue.
   Tune `DEFAULT_CHUNK_LEN` / `DEFAULT_OVERLAP` if you know your VODs skew differently.

3. **RESOLVED — silence detection thresholds.** Original -30dB/1.5s produced 568 silences
   over 2h8m (median 2.35s, 379 under 3s) — confirmed by the streamer as catching normal
   speech pauses, not dead air (this VOD had a lower-quality mic, which likely made short
   pauses register as "silence" more readily). Raised `min_duration` to 6.0s (noise floor
   left at -30dB, which held up fine); re-run produced 43 silences whose top candidates
   matched the same real dead-air stretches the streamer already confirmed. This is now a
   validated default, not a guess — but it came from one VOD, so keep an eye on it as more
   VODs run through the pipeline.

4. **Model size default: `medium`.** Now benchmarked: ~3x realtime on this machine (CPU
   only, no CUDA), so a 2h8m VOD took ~48 min to transcribe. A 3-4hr VOD would be
   ~55-75 min — workable but not instant, and this will dominate pipeline wall-clock time
   more than any other single step. Word-timing accuracy at `medium` was confirmed good
   by spot check, so no upgrade to `large-v3` seems needed on accuracy grounds, but it
   would cost real additional time if you want it for a harder case (heavy cross-talk,
   multiple simultaneous speakers).

5. **Deviation from spec:** the spec's `TranscriptResult` only listed `segments`; I added
   `silences`, `duration`, `vod_path`, and `model_size` fields since the spec's own text
   says silence detection should "attach a `silences` field to the result" and Layer 2/3
   need to know what VOD/model produced a given cached transcript. Flagging in case you'd
   rather keep the result type minimal and carry that metadata separately.

6. **`device`/`compute_type` are exposed but defaulted to `"auto"`/`"default"`** — on this
   Mac (Apple Silicon, no CUDA) that resolves to CPU float32. Fine for the tiny/small
   smoke tests here; worth revisiting once you're running `medium`/`large-v3` on real
   multi-hour VODs, where CPU-only transcription will be slow (this is a speed question,
   not a correctness one — no action needed unless throughput becomes a problem).

7. **Progress logging added retroactively** (`common/progress.py`) after you asked for
   it mid-Phase-1 — the ~48min transcription run that established the Phase 1 gate above
   predates this and had no incremental progress output (I inferred progress externally
   by watching temp chunk files). All runs from here on will show per-chunk/per-step
   progress with ETA.

## Next step
Phase 1 gate passed. Moving to Layer 2 (Analysis) — see `analysis/`, `config/prompts/`,
`eval/score_segments.py`, `eval/score_clips.py`. Blocked on an `ANTHROPIC_API_KEY`
(pay-as-you-go, separate from a Claude.ai/Claude Code subscription) to actually run Mode A
/ Mode B against the real VOD and score against `eval/expected/stream_vod_2026-07-18.json`.
