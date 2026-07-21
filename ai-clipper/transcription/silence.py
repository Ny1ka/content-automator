import re
import subprocess

from .types import Silence

SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")

# Judgment call, tuned against a real 2h8m stream VOD on 2026-07-21: -30dB
# noise floor held up fine (confirmed by ear), but 1.5s min duration caught
# ordinary speech pauses instead of real dead air (568 silences, median 2.35s,
# 379 under 3s). Raised to 6s so only genuine dead-air stretches (the
# streamer confirmed 5 real ones in the 10-30s range) get flagged. Revisit if
# a future VOD has meaningfully different pacing.
DEFAULT_NOISE_DB = -30
DEFAULT_MIN_DURATION = 6.0


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
