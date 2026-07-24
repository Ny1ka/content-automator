"""Build a keep_ranges decision JSON for one VOD window, per the mechanical
(non-LLM) silence-cutting spec in cutting/keep_ranges.py.

    python -m cli.build_keep_ranges_cli <vod_path> <transcript_json> <start_sec> <end_sec> <output_json>

Caches the fine-grained audio-energy silence pass (-40dB/2s) to
eval/cache/energy_silences_<vod_hash>.json since it's a full-VOD ffmpeg decode
pass and re-running it per segment/window would be wasteful.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cutting.keep_ranges import build_keep_ranges  # noqa: E402
from transcription.silence import detect_silences  # noqa: E402


def _energy_cache_path(vod_path: str) -> Path:
    key = hashlib.sha256(vod_path.encode()).hexdigest()[:16]
    return Path(__file__).resolve().parent.parent / "eval" / "cache" / f"energy_silences_{key}.json"


def get_energy_silences(vod_path: str) -> list[dict]:
    cache_path = _energy_cache_path(vod_path)
    if cache_path.exists():
        print(f"[build_keep_ranges_cli] using cached energy silences: {cache_path}")
        return json.loads(cache_path.read_text())
    print("[build_keep_ranges_cli] running fine-grained audio-energy pass (-40dB/2.0s)... this decodes the full VOD")
    silences = detect_silences(vod_path, noise_db=-40.0, min_duration=2.0)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(silences, indent=2))
    print(f"[build_keep_ranges_cli] cached {len(silences)} energy silences to {cache_path}")
    return silences


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vod_path", type=lambda p: str(Path(p).resolve()))
    parser.add_argument("transcript_json")
    parser.add_argument("start_sec", type=float)
    parser.add_argument("end_sec", type=float)
    parser.add_argument("output_json")
    parser.add_argument("--fps", type=float, default=None, help="defaults to probing the VOD with ffprobe")
    args = parser.parse_args()

    transcript = json.loads(Path(args.transcript_json).read_text())
    energy_silences = get_energy_silences(args.vod_path)

    fps = args.fps or _probe_fps(args.vod_path)

    result = build_keep_ranges(
        transcript["segments"],
        args.vod_path,
        args.start_sec,
        args.end_sec,
        fps=fps,
        energy_silences=energy_silences,
    )

    diagnostics = result.pop("_diagnostics")
    print(f"[build_keep_ranges_cli] {diagnostics['cuts_applied']} cuts applied")
    if diagnostics["too_short_after_padding"]:
        print(f"[build_keep_ranges_cli] {len(diagnostics['too_short_after_padding'])} gaps were too short to cut after padding (left as KEEP):")
        for g in diagnostics["too_short_after_padding"]:
            print(f"    {g['start']:.2f}-{g['end']:.2f}s")

    kept = sum(r["end"] - r["start"] for r in result["keep_ranges"])
    total = args.end_sec - args.start_sec
    print(f"[build_keep_ranges_cli] kept {kept:.1f}s of {total:.1f}s ({kept / total:.1%}), {len(result['keep_ranges'])} ranges")

    Path(args.output_json).write_text(json.dumps(result, indent=2))
    print(f"[build_keep_ranges_cli] wrote {args.output_json}")


def _probe_fps(vod_path: str) -> float:
    import subprocess

    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", vod_path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    num, den = out.split("/")
    return float(num) / float(den)


if __name__ == "__main__":
    main()
