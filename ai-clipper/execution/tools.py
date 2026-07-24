"""VOD->YT simple-cut pipeline: Mode A decision JSON -> rendered file.

This is deliberately the smallest closed loop from the Phase 3 spec (cut +
fade only). The clip-specific tools (reframe, SFX, PIP, B&W, insert) come in
later phases and aren't wired in here yet.
"""
from pathlib import Path
from typing import Any

from .backend import ResolveBackend
from .types import ExportResult

DEFAULT_FADE_SEC = 1.0
DEFAULT_PRESET = "YouTube - 1080p"


def render_simple_cut(
    backend: ResolveBackend,
    vod_path: str,
    decision: dict[str, Any],
    output_path: str,
    fade_sec: float = DEFAULT_FADE_SEC,
    preset: str = DEFAULT_PRESET,
) -> ExportResult:
    """Cut a VOD down to its `keep: true` segments, fade in at the start and to
    black at the end, and render. `decision` is Mode A's schema
    (`{"segments": [{"start", "end", "label", "keep"}, ...]}`).
    """
    keep_ranges = [
        {"start": s["start"], "end": s["end"]} for s in decision["segments"] if s["keep"]
    ]
    if not keep_ranges:
        raise ValueError("decision has no segments with keep=true — nothing to render")

    backend.import_media(vod_path)
    timeline_id = backend.create_timeline(Path(vod_path).stem)
    backend.cut_segments(timeline_id, keep_ranges)
    backend.add_fade(timeline_id, "in", fade_sec)
    backend.add_fade(timeline_id, "out", fade_sec)
    return backend.export(timeline_id, output_path, preset)
