import hashlib
import json
import os
from pathlib import Path

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "eval" / "cache"


def vod_fingerprint(vod_path: str) -> str:
    """Cheap fingerprint: path + size + mtime, not a full content hash.

    Hashing the full bytes of an hours-long VOD (tens of GB) just to get a
    cache key defeats the purpose of caching. Size+mtime collisions are only
    a risk if a file is edited in place while keeping the same size and
    mtime, which doesn't happen in this pipeline's normal usage.
    """
    st = os.stat(vod_path)
    key = f"{os.path.abspath(vod_path)}:{st.st_size}:{int(st.st_mtime)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def cache_path(vod_path: str, model_size: str, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    fp = vod_fingerprint(vod_path)
    return cache_dir / f"{fp}_{model_size}.json"


def load_cached(vod_path: str, model_size: str, cache_dir: Path | None = None) -> dict | None:
    p = cache_path(vod_path, model_size, cache_dir)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def save_cache(vod_path: str, model_size: str, result: dict, cache_dir: Path | None = None) -> Path:
    p = cache_path(vod_path, model_size, cache_dir)
    with open(p, "w") as f:
        json.dump(result, f, indent=2)
    return p
