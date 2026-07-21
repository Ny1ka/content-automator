import hashlib
import json
from pathlib import Path

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "eval" / "cache" / "analysis"


def _key(vod_fingerprint: str, prompt_version: str, window_key: str) -> str:
    raw = f"{vod_fingerprint}:{prompt_version}:{window_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def load(vod_fingerprint: str, prompt_version: str, window_key: str = "full", cache_dir: Path | None = None):
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    p = cache_dir / f"{_key(vod_fingerprint, prompt_version, window_key)}.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def save(vod_fingerprint: str, prompt_version: str, result: dict, window_key: str = "full", cache_dir: Path | None = None):
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{_key(vod_fingerprint, prompt_version, window_key)}.json"
    with open(p, "w") as f:
        json.dump(result, f, indent=2)
    return p
