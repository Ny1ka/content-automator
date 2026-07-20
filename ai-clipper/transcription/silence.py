import re
import subprocess

from .types import Silence

SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")

# Judgment call: -30dB noise floor and 1.5s minimum duration. Loud game audio
# bleeding through the mic during "silence" will push detected dead air
# shorter/rarer than a human would flag by ear; tune noise_db down (more
# negative) if this misses obvious dead air on noisy streams.
DEFAULT_NOISE_DB = -30
DEFAULT_MIN_DURATION = 1.5


def detect_silences(
    vod_path: str,
    noise_db: float = DEFAULT_NOISE_DB,
    min_duration: float = DEFAULT_MIN_DURATION,
) -> list[Silence]:
    proc = subprocess.run(
        [
            "ffmpeg", "-i", vod_path, "-af",
            f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    log = proc.stderr

    silences: list[Silence] = []
    pending_start: float | None = None
    for line in log.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            silences.append({"start": pending_start, "end": float(end_match.group(1))})
            pending_start = None

    return silences
