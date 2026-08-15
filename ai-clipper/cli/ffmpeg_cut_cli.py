"""CLI entrypoint for the FFmpeg-only render pipeline: decision JSON -> rendered file.

No DaVinci Resolve install or scripting API required — pure ffmpeg trim+concat+fade.
This is the ffmpeg equivalent of cli/render_cli.py (which drives Resolve instead).

    python -m cli.ffmpeg_cut_cli <decision_json_path> <output_path> [--fade-sec N] [--crf N] [--preset NAME]

decision_json_path accepts either a keep_ranges decision
({"source_file": "...", "keep_ranges": [{"start", "end"}, ...]}, e.g. from
cli/build_keep_ranges_cli.py) or a raw Mode A decision
({"segments": [{"start", "end", "label", "keep"}, ...]}, e.g. from
`python -m cli.analyze_cli ... a`).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.ffmpeg_backend import DEFAULT_CRF, DEFAULT_FADE_SEC, DEFAULT_PRESET, render_ffmpeg_cut  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a VOD->YT simple cut with ffmpeg only (no DaVinci Resolve)")
    parser.add_argument("decision_json_path")
    parser.add_argument("output_path")
    parser.add_argument("--fade-sec", type=float, default=DEFAULT_FADE_SEC)
    parser.add_argument("--crf", type=int, default=DEFAULT_CRF)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    args = parser.parse_args()

    decision = json.loads(Path(args.decision_json_path).read_text())
    vod_path = decision.get("source_file") or decision.get("vod_path")
    if not vod_path:
        raise SystemExit("decision JSON must include a 'source_file' or 'vod_path' key")

    result = render_ffmpeg_cut(
        vod_path, decision, args.output_path, fade_sec=args.fade_sec, crf=args.crf, preset=args.preset
    )
    print(f"Rendered {result['output_path']} ({result['duration']:.1f}s)")


if __name__ == "__main__":
    main()
