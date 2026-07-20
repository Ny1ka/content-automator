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

## What is NOT yet done — the actual spec acceptance test
The spec's Phase 1 gate requires: **1 VOD with clear speech + 1 with noisy game audio,
5 spot-checked segments each against real audio (~200ms tolerance), and silence detection
confirmed against the 3 longest dead-air stretches by ear.** You said you don't have test
VODs yet, so this hasn't run. Everything above is a mechanics check (the pipeline doesn't
crash and does roughly the right thing), not the accuracy acceptance test. Drop VOD files
in `eval/vods/` and I'll run this for real — that's the actual gate before Phase 2.

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

3. **Silence detection thresholds: -30dB noise floor, 1.5s minimum duration**
   (`silence.py`). Untested against real noisy game audio — a stream with loud game audio
   bleeding through the mic during "dead air" will likely under-detect versus what a human
   would flag by ear, since the noise floor won't dip to -30dB. This is exactly the
   parameter the real acceptance test (silences vs. 3 longest audible dead-air stretches)
   is meant to tune. Expect to lower `noise_db` (make it more negative, e.g. -35 to -40)
   or raise `min_duration` once real VODs are available.

4. **Model size default: `medium`.** Not benchmarked yet for speed/accuracy tradeoff on
   real content — `large-v3` would likely transcribe game/stream audio with cross-talk
   more accurately at a real cost in wall-clock time; `small`/`base` would be much faster
   for iteration. Worth deciding once you have a sense of how long a 3-hour VOD takes to
   transcribe on this machine at each size.

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

## Next step
Waiting on real VOD files in `eval/vods/` to run the actual accuracy acceptance test
before starting Layer 2 (analysis prompts). Everything above is ready to point at real
files as soon as you have them — just tell me the path(s).
