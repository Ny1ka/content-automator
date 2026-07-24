from typing import Protocol

from .types import AspectRatio, Corner, ExportResult, FadeDirection, ImportResult, KeepRange


class ResolveBackend(Protocol):
    """Everything the execution-layer tools need from a Resolve connection (or a stand-in).

    Deviation from the spec's tool list: it jumps straight from
    `resolve_import_media` to `resolve_cut_segments(timeline_id, ...)` without
    ever creating the timeline `cut_segments` operates on. Added
    `create_timeline` here to fill that gap — it's an unavoidable
    prerequisite step, not a new creative capability, so it's kept off the
    public MCP tool surface (server.py) and called internally by the CLI/
    pipeline glue instead.
    """

    def create_timeline(self, name: str) -> str: ...

    def import_media(self, path: str) -> ImportResult: ...

    def cut_segments(self, timeline_id: str, keep_ranges: list[KeepRange]) -> None: ...

    def add_fade(self, clip_id: str, position: FadeDirection, duration_sec: float) -> None: ...

    def reframe(self, clip_id: str, aspect_ratio: AspectRatio) -> None: ...

    def add_pip(self, timeline_id: str, source_clip_id: str, corner: Corner, start: float, end: float) -> None: ...

    def add_bw_effect(self, clip_id: str, start: float, end: float) -> None: ...

    def insert_media_at_cut(self, timeline_id: str, position: float, media_id: str) -> None: ...

    def add_sfx(self, timeline_id: str, sfx_file: str, position: float) -> None: ...

    def export(self, timeline_id: str, output_path: str, preset: str) -> ExportResult: ...
