from pathlib import Path

from faster_whisper import WhisperModel

from . import cache as cache_mod
from .audio import TempWav, extract_chunk_wav, iter_chunks, probe_duration
from .silence import detect_silences
from .types import TranscriptResult, TranscriptSegment, WordTiming

# Judgment call: 20-minute chunks with 15s overlap. Long enough that
# whisper's own context window still helps quality, short enough to keep
# per-chunk decode memory small on multi-hour VODs. The 15s overlap needs to
# comfortably exceed the longest realistic single utterance that could
# straddle a boundary.
DEFAULT_CHUNK_LEN = 20 * 60
DEFAULT_OVERLAP = 15.0


def _transcribe_chunk(model: WhisperModel, wav_path: Path, offset: float, step_end: float) -> list[TranscriptSegment]:
    segments, _info = model.transcribe(str(wav_path), word_timestamps=True)
    out: list[TranscriptSegment] = []
    for seg in segments:
        seg_start = seg.start + offset
        if seg_start >= step_end:
            # Entirely inside this chunk's trailing overlap; the next chunk
            # will re-transcribe it with full leading context.
            continue
        words: list[WordTiming] = []
        if seg.words:
            for w in seg.words:
                w_start = w.start + offset
                if w_start >= step_end:
                    continue
                words.append({
                    "word": w.word.strip(),
                    "start": w_start,
                    "end": w.end + offset,
                    "confidence": float(w.probability),
                })
        out.append({
            "start": seg_start,
            "end": min(seg.end + offset, step_end),
            "text": seg.text.strip(),
            "words": words,
        })
    return out


def transcribe(
    vod_path: str,
    model_size: str = "medium",
    force: bool = False,
    cache_dir: Path | None = None,
    chunk_len: float = DEFAULT_CHUNK_LEN,
    overlap: float = DEFAULT_OVERLAP,
    device: str = "auto",
    compute_type: str = "default",
) -> TranscriptResult:
    if not force:
        cached = cache_mod.load_cached(vod_path, model_size, cache_dir)
        if cached is not None:
            return cached  # type: ignore[return-value]

    duration = probe_duration(vod_path)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    all_segments: list[TranscriptSegment] = []
    tmp = TempWav()
    try:
        for idx, start, length in iter_chunks(duration, chunk_len, overlap):
            step_end = start + (chunk_len - overlap) if start + chunk_len < duration else duration
            wav_path = tmp.path(f"chunk_{idx}.wav")
            extract_chunk_wav(vod_path, start, length, wav_path)
            all_segments.extend(_transcribe_chunk(model, wav_path, start, step_end))
    finally:
        tmp.cleanup()

    silences = detect_silences(vod_path)

    result: TranscriptResult = {
        "segments": all_segments,
        "silences": silences,
        "duration": duration,
        "vod_path": str(Path(vod_path).resolve()),
        "model_size": model_size,
    }

    cache_mod.save_cache(vod_path, model_size, result, cache_dir)
    return result
