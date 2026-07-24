"""Real DaVinci Resolve Studio backend, driven through the scripting API.

Judgment calls / deviations worth flagging (see also backend.py's docstring on
create_timeline):

1. Fades are NOT implemented via the Resolve scripting API. TimelineItem has no
   documented AddFade/AddTransition call, and SetProperty's accepted keys (Pan,
   ZoomX, CropLeft, Opacity, ...) don't include anything fade-related — confirmed
   by probing a live TimelineItem's property surface, not just docs. The only
   reliable way to get a fade with the scripting API alone is an undocumented
   Fusion-node hack, which is fragile across Resolve versions. Instead, `export()`
   renders the cut timeline via Resolve's render queue, then runs a single ffmpeg
   pass over the rendered file to apply `fade`/`afade`. This still respects the
   spec's "LLM never touches pixels" rule (fades are deterministic ffmpeg filters,
   not model output) and keeps Resolve as the one doing the actual cutting, which
   is the part that benefits most from Resolve's frame-accurate edit tools.

2. `cut_segments` operates on the most recently imported media (single source
   clip per timeline). The spec's tool signature has no explicit media_id
   parameter, so multi-source timelines aren't supported yet — fine for the
   VOD->YT simple-cut workflow, which is single-source by definition.

3. `add_fade`'s `clip_id` is expected to equal the `timeline_id` for this
   workflow (there's no per-clip id returned by cut_segments to fade
   individual clips) — it registers a fade against the whole timeline's
   rendered output, applied at the very start/end of the export.
"""
import itertools
import subprocess
import time
from pathlib import Path

from .resolve_env import ensure_resolve_env
from .types import AspectRatio, Corner, ExportResult, FadeDirection, ImportResult, KeepRange

ensure_resolve_env()
import DaVinciResolveScript as dvr  # noqa: E402


class RealResolveBackend:
    def __init__(self):
        self.resolve = dvr.scriptapp("Resolve")
        if self.resolve is None:
            raise RuntimeError(
                "Could not connect to DaVinci Resolve. Make sure Resolve Studio is "
                "running and 'External scripting using' is enabled in "
                "Preferences > General."
            )
        self.project = self.resolve.GetProjectManager().GetCurrentProject()
        if self.project is None:
            raise RuntimeError("No project open in Resolve — open or create one first.")

        self._id_counter = itertools.count(1)
        self._timelines: dict[str, object] = {}
        self._media: dict[str, object] = {}
        self._last_media_id: str | None = None
        self._fades: dict[str, list[tuple[FadeDirection, float]]] = {}

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._id_counter)}"

    def create_timeline(self, name: str) -> str:
        media_pool = self.project.GetMediaPool()
        timeline = media_pool.CreateEmptyTimeline(name)
        if timeline is None:
            raise RuntimeError(f"Resolve refused to create timeline '{name}'")
        tid = self._next_id("timeline")
        self._timelines[tid] = timeline
        self._fades[tid] = []
        return tid

    def import_media(self, path: str) -> ImportResult:
        abs_path = str(Path(path).resolve())
        media_pool = self.project.GetMediaPool()
        items = media_pool.ImportMedia([abs_path])
        if not items:
            raise RuntimeError(f"Resolve failed to import media: {abs_path}")
        mid = self._next_id("media")
        self._media[mid] = items[0]
        self._last_media_id = mid
        return {"media_pool_item_id": mid}

    def cut_segments(self, timeline_id: str, keep_ranges: list[KeepRange]) -> None:
        timeline = self._require(self._timelines, timeline_id, "timeline_id")
        if self._last_media_id is None:
            raise RuntimeError("cut_segments called before any import_media call")
        media_item = self._media[self._last_media_id]
        fps = float(media_item.GetClipProperty("FPS"))

        media_pool = self.project.GetMediaPool()
        self.project.SetCurrentTimeline(timeline)
        for r in keep_ranges:
            if r["end"] <= r["start"]:
                raise ValueError(f"keep_range end ({r['end']}) must be after start ({r['start']})")
            start_frame = round(r["start"] * fps)
            end_frame = round(r["end"] * fps)
            clip_info = {"mediaPoolItem": media_item, "startFrame": start_frame, "endFrame": end_frame}
            appended = media_pool.AppendToTimeline([clip_info])
            if not appended:
                raise RuntimeError(f"Resolve rejected append for range {r}")

    def add_fade(self, clip_id: str, position: FadeDirection, duration_sec: float) -> None:
        if position not in ("in", "out"):
            raise ValueError(f"invalid fade position: {position}")
        if duration_sec <= 0:
            raise ValueError(f"fade duration must be positive, got {duration_sec}")
        self._require(self._timelines, clip_id, "clip_id (expected a timeline_id, see module docstring)")
        self._fades[clip_id].append((position, duration_sec))

    def reframe(self, clip_id: str, aspect_ratio: AspectRatio) -> None:
        raise NotImplementedError("reframe is Phase 4 — not built yet")

    def add_pip(self, timeline_id: str, source_clip_id: str, corner: Corner, start: float, end: float) -> None:
        raise NotImplementedError("add_pip is Phase 5 — not built yet")

    def add_bw_effect(self, clip_id: str, start: float, end: float) -> None:
        raise NotImplementedError("add_bw_effect is Phase 5 — not built yet")

    def insert_media_at_cut(self, timeline_id: str, position: float, media_id: str) -> None:
        raise NotImplementedError("insert_media_at_cut is Phase 5 — not built yet")

    def add_sfx(self, timeline_id: str, sfx_file: str, position: float) -> None:
        raise NotImplementedError("add_sfx is Phase 4 — not built yet")

    def export(self, timeline_id: str, output_path: str, preset: str) -> ExportResult:
        timeline = self._require(self._timelines, timeline_id, "timeline_id")
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        fades = self._fades.get(timeline_id, [])
        render_target = out_path.with_name(out_path.stem + "_prefade" + out_path.suffix) if fades else out_path

        self._render(timeline, render_target)

        if fades:
            self._apply_fades(render_target, out_path, fades)
            render_target.unlink()

        duration = sum(r["end"] - r["start"] for r in self._keep_ranges_of(timeline_id))
        return {"output_path": str(out_path), "duration": duration}

    def _keep_ranges_of(self, timeline_id: str) -> list[KeepRange]:
        timeline = self._timelines[timeline_id]
        items = timeline.GetItemListInTrack("video", 1) or []
        fps = self.project.GetSetting("timelineFrameRate")
        fps = float(fps) if fps else 30.0
        return [{"start": item.GetStart() / fps, "end": item.GetEnd() / fps} for item in items]

    def _render(self, timeline, render_target: Path) -> None:
        self.project.SetCurrentTimeline(timeline)
        if not self.project.LoadRenderPreset("YouTube - 1080p"):
            raise RuntimeError("Resolve render preset 'YouTube - 1080p' not found")
        ok = self.project.SetRenderSettings(
            {
                "SelectAllFrames": True,
                "TargetDir": str(render_target.parent),
                "CustomName": render_target.stem,
                "ExportVideo": True,
                "ExportAudio": True,
            }
        )
        if not ok:
            raise RuntimeError("Resolve rejected render settings")

        job_id = self.project.AddRenderJob()
        if not job_id:
            raise RuntimeError("Resolve failed to queue render job")

        self.project.StartRendering([job_id])
        while self.project.IsRenderingInProgress():
            time.sleep(1)

        status = self.project.GetRenderJobStatus(job_id)
        if status.get("JobStatus") != "Complete":
            raise RuntimeError(f"Resolve render job did not complete: {status}")

        rendered = list(render_target.parent.glob(f"{render_target.stem}.*"))
        if not rendered:
            raise RuntimeError(f"Expected rendered file at {render_target} but found none")
        rendered[0].rename(render_target)

    def _apply_fades(self, src: Path, dst: Path, fades: list[tuple[FadeDirection, float]]) -> None:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
            capture_output=True,
            text=True,
            check=True,
        )
        total_duration = float(probe.stdout.strip())

        video_filters, audio_filters = [], []
        for position, duration_sec in fades:
            if position == "in":
                video_filters.append(f"fade=t=in:st=0:d={duration_sec}")
                audio_filters.append(f"afade=t=in:st=0:d={duration_sec}")
            else:
                start = max(0.0, total_duration - duration_sec)
                video_filters.append(f"fade=t=out:st={start}:d={duration_sec}:color=black")
                audio_filters.append(f"afade=t=out:st={start}:d={duration_sec}")

        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", ",".join(video_filters),
            "-af", ",".join(audio_filters),
            "-c:v", "libx264", "-crf", "16", "-preset", "medium",
            "-c:a", "aac",
            str(dst),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def _require(self, registry: dict, key: str, label: str):
        if key not in registry:
            raise ValueError(f"unknown {label}: {key}")
        return registry[key]
