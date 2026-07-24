"""CLI entrypoint for the Phase 3 closed loop: decision JSON -> rendered file.

    python -m cli.render_cli <vod_path> <decision_json_path> <output_path> [--fade-sec N] [--preset NAME]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.resolve_backend import RealResolveBackend  # noqa: E402
from execution.tools import DEFAULT_FADE_SEC, DEFAULT_PRESET, render_simple_cut  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a VOD->YT simple cut from a Mode A decision JSON")
    parser.add_argument("vod_path")
    parser.add_argument("decision_json_path")
    parser.add_argument("output_path")
    parser.add_argument("--fade-sec", type=float, default=DEFAULT_FADE_SEC)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    args = parser.parse_args()

    decision = json.loads(Path(args.decision_json_path).read_text())
    backend = RealResolveBackend()
    result = render_simple_cut(
        backend, args.vod_path, decision, args.output_path, fade_sec=args.fade_sec, preset=args.preset
    )
    print(f"Rendered {result['output_path']} ({result['duration']:.1f}s)")


if __name__ == "__main__":
    main()
