"""In-memory stand-in for a real Resolve connection.

Lets execution/tools.py be built and unit-tested without a running DaVinci
Resolve instance. Records every call so tests can assert on what happened,
and does the same validation a real backend implementation would need
(unknown IDs, out-of-range positions, etc.) so tool-level tests catch
interface bugs before they ever touch the real Resolve API.
"""
import itertools

from .types import AspectRatio, Corner, ExportResult, FadeDirection, ImportResult, KeepRange


class MockResolveBackend:
    def __init__(self):
        self._id_counter = itertools.count(1)
        self.timelines: dict[str, dict] = {}
        self.media: dict[str, dict] = {}
        self.clips: dict[str, dict] = {}
        self.calls: list[tuple] = []

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._id_counter)}"

    def create_timeline(self, name: str) -> str:
        tid = self._next_id("timeline")
        self.timelines[tid] = {"name": name, "keep_ranges": [], "pips": [], "sfx": [], "bw_ranges": [], "inserts": []}
        self.calls.append(("create_timeline", name))
        return tid

    def import_media(self, path: str) -> ImportResult:
        mid = self._next_id("media")
        self.media[mid] = {"path": path}
        self.calls.append(("import_media", path))
        return {"media_pool_item_id": mid}

    def cut_segments(self, timeline_id: str, keep_ranges: list[KeepRange]) -> None:
        self._require_timeline(timeline_id)
        for r in keep_ranges:
            if r["end"] <= r["start"]:
                raise ValueError(f"keep_range end ({r['end']}) must be after start ({r['start']})")
        self.timelines[timeline_id]["keep_ranges"] = list(keep_ranges)
        self.calls.append(("cut_segments", timeline_id, keep_ranges))

    def add_fade(self, clip_id: str, position: FadeDirection, duration_sec: float) -> None:
        if position not in ("in", "out"):
            raise ValueError(f"invalid fade position: {position}")
        if duration_sec <= 0:
            raise ValueError(f"fade duration must be positive, got {duration_sec}")
        self.clips.setdefault(clip_id, {}).setdefault("fades", []).append((position, duration_sec))
        self.calls.append(("add_fade", clip_id, position, duration_sec))

    def reframe(self, clip_id: str, aspect_ratio: AspectRatio) -> None:
        if aspect_ratio not in ("1:1", "16:9", "9:16"):
            raise ValueError(f"invalid aspect_ratio: {aspect_ratio}")
        self.clips.setdefault(clip_id, {})["aspect_ratio"] = aspect_ratio
        self.calls.append(("reframe", clip_id, aspect_ratio))

    def add_pip(self, timeline_id: str, source_clip_id: str, corner: Corner, start: float, end: float) -> None:
        self._require_timeline(timeline_id)
        if corner not in ("top-left", "top-right"):
            raise ValueError(f"invalid corner: {corner}")
        if end <= start:
            raise ValueError(f"pip end ({end}) must be after start ({start})")
        self.timelines[timeline_id]["pips"].append((source_clip_id, corner, start, end))
        self.calls.append(("add_pip", timeline_id, source_clip_id, corner, start, end))

    def add_bw_effect(self, clip_id: str, start: float, end: float) -> None:
        if end <= start:
            raise ValueError(f"bw range end ({end}) must be after start ({start})")
        self.clips.setdefault(clip_id, {}).setdefault("bw_ranges", []).append((start, end))
        self.calls.append(("add_bw_effect", clip_id, start, end))

    def insert_media_at_cut(self, timeline_id: str, position: float, media_id: str) -> None:
        self._require_timeline(timeline_id)
        if media_id not in self.media:
            raise ValueError(f"unknown media_id: {media_id}")
        self.timelines[timeline_id]["inserts"].append((position, media_id))
        self.calls.append(("insert_media_at_cut", timeline_id, position, media_id))

    def add_sfx(self, timeline_id: str, sfx_file: str, position: float) -> None:
        self._require_timeline(timeline_id)
        if position < 0:
            raise ValueError(f"sfx position must be non-negative, got {position}")
        self.timelines[timeline_id]["sfx"].append((sfx_file, position))
        self.calls.append(("add_sfx", timeline_id, sfx_file, position))

    def export(self, timeline_id: str, output_path: str, preset: str) -> ExportResult:
        self._require_timeline(timeline_id)
        keep_ranges = self.timelines[timeline_id]["keep_ranges"]
        duration = sum(r["end"] - r["start"] for r in keep_ranges) if keep_ranges else 0.0
        self.calls.append(("export", timeline_id, output_path, preset))
        return {"output_path": output_path, "duration": duration}

    def _require_timeline(self, timeline_id: str):
        if timeline_id not in self.timelines:
            raise ValueError(f"unknown timeline_id: {timeline_id}")
