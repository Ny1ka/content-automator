"""FFmpeg-only render backend: cut a VOD down to its keep_ranges and render
directly with ffmpeg. No DaVinci Resolve install or scripting API required —
this is the alternative to execution/resolve_backend.py for people who just
want a finished MP4.

Accepts the same decision JSON shape as execution/resolve_scripts/01_cut_segments.py
({"source_file"/"vod_path": ..., "keep_ranges": [{"start", "end"}, ...]}), or a raw
Mode A decision ({"segments": [{"start", "end", "label", "keep"}, ...]}) — segments
with keep=false are dropped the same way execution/tools.py's render_simple_cut()
does for the Resolve backend, so both pipelines accept the same upstream artifacts.
"""
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_FADE_SEC = 1.0
DEFAULT_CRF = 16
DEFAULT_PRESET = "medium"


def _keep_ranges_from_decision(decision: dict[str, Any]) -> list[dict]:
    if "segments" in decision:
        return [{"start": s["start"], "end": s["end"]} for s in decision["segments"] if s["keep"]]
    return decision["keep_ranges"]


def render_ffmpeg_cut(
    vod_path: str,
    decision: dict[str, Any],
    output_path: str,
    fade_sec: float = DEFAULT_FADE_SEC,
    crf: int = DEFAULT_CRF,
    preset: str = DEFAULT_PRESET,
) -> dict:
    """Trim each keep_range with ffmpeg's trim/atrim filters, concat them back
    to back, optionally fade in/out, and encode to a single output file — the
    ffmpeg equivalent of what 01_cut_segments.py does inside Resolve.
    """
    keep_ranges = sorted(_keep_ranges_from_decision(decision), key=lambda r: r["start"])
    if not keep_ranges:
        raise ValueError("decision has no keep ranges — nothing to render")

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    trim_parts = []
    concat_inputs = []
    for i, r in enumerate(keep_ranges):
        if r["end"] <= r["start"]:
            raise ValueError(f"invalid range: {r}")
        trim_parts.append(
            f"[0:v]trim=start={r['start']}:end={r['end']},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={r['start']}:end={r['end']},asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs.append(f"[v{i}][a{i}]")
    concat_expr = f"{''.join(concat_inputs)}concat=n={len(keep_ranges)}:v=1:a=1[catv][cata]"

    total_duration = sum(r["end"] - r["start"] for r in keep_ranges)
    video_out, audio_out = "[catv]", "[cata]"
    fade_parts = []
    if fade_sec > 0:
        fade_out_start = max(0.0, total_duration - fade_sec)
        fade_parts = [
            f"{video_out}fade=t=in:st=0:d={fade_sec}[fv]",
            f"{audio_out}afade=t=in:st=0:d={fade_sec}[fa]",
            f"[fv]fade=t=out:st={fade_out_start}:d={fade_sec}:color=black[outv]",
            f"[fa]afade=t=out:st={fade_out_start}:d={fade_sec}[outa]",
        ]
        video_out, audio_out = "[outv]", "[outa]"

    filter_complex = ";".join(trim_parts + [concat_expr] + fade_parts)

    cmd = [
        "ffmpeg", "-y", "-i", vod_path,
        "-filter_complex", filter_complex,
        "-map", video_out, "-map", audio_out,
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-c:a", "aac",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    return {"output_path": str(out), "duration": total_duration}
