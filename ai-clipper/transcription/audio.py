import subprocess
import tempfile
from pathlib import Path


def probe_duration(path: str) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_chunk_wav(vod_path: str, start: float, length: float, out_path: Path) -> None:
    """Extract [start, start+length) as 16kHz mono PCM WAV via ffmpeg.

    Decoding a bounded window at a time (rather than the whole file into a
    numpy array up front) keeps peak memory flat regardless of VOD length.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(start), "-t", str(length), "-i", vod_path,
            "-ac", "1", "-ar", "16000", "-vn", str(out_path),
        ],
        capture_output=True, check=True,
    )


def iter_chunks(duration: float, chunk_len: float, overlap: float):
    """Yield (index, start, length) windows covering [0, duration).

    Each chunk after the first extends `overlap` seconds past its
    authoritative region so the model has trailing context to transcribe
    boundary words correctly; the caller discards words that fall in that
    trailing overlap and lets the *next* chunk own them (it has full leading
    context instead). Step size is chunk_len - overlap.
    """
    step = chunk_len - overlap
    start = 0.0
    idx = 0
    while start < duration:
        length = min(chunk_len, duration - start)
        yield idx, start, length
        start += step
        idx += 1


class TempWav:
    def __init__(self):
        self._dir = tempfile.TemporaryDirectory(prefix="ai-clipper-audio-")

    def path(self, name: str) -> Path:
        return Path(self._dir.name) / name

    def cleanup(self):
        self._dir.cleanup()
