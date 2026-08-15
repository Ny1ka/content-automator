"""Find one or more clips by natural-language description and accumulate them
into a named-clips JSON that execution/resolve_scripts/04_named_clips.py reads.

    python -m cli.find_clips_cli eval/cache/stream_vod_2026-07-18_transcript.json \\
        eval/decisions/named_clips.json \\
        --query "the clip where my teammate said the guy was 1hp" \\
        --query "the OperaGX conversation"

Re-running with the same query text reuses the cached Claude/Gemini response
(keyed on the exact set of queries in one call) rather than re-spending API
credits. Appends to the output file rather than overwriting — a name collision
with an existing entry gets overwritten (treated as "redo this one"), anything
else accumulates.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import run_mode_c  # noqa: E402
from transcription.cache import vod_fingerprint  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript_json")
    parser.add_argument("output_json", help="Accumulating named-clips file for the Resolve script to read")
    parser.add_argument("--query", action="append", required=True, dest="queries", help="Repeatable: one natural-language clip description per --query")
    parser.add_argument("--provider", choices=["anthropic", "gemini"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    transcript = json.loads(Path(args.transcript_json).read_text())
    fp = vod_fingerprint(transcript["vod_path"])

    result = run_mode_c(fp, transcript["segments"], args.queries, force=args.force, provider=args.provider, model=args.model)

    out_path = Path(args.output_json)
    existing = json.loads(out_path.read_text()) if out_path.exists() else {"source_file": transcript["vod_path"], "clips": []}
    by_name = {c["name"]: c for c in existing["clips"]}

    for clip in result.clips:
        if not clip.found:
            print(f"[find_clips_cli] NOT FOUND: \"{clip.query}\" — {clip.reason}")
            continue
        by_name[clip.name] = {"name": clip.name, "start": clip.start, "end": clip.end, "query": clip.query, "reason": clip.reason}
        print(f"[find_clips_cli] {clip.name}: {clip.start:.2f}-{clip.end:.2f}s — {clip.reason}")

    existing["clips"] = sorted(by_name.values(), key=lambda c: c["start"])
    out_path.write_text(json.dumps(existing, indent=2))
    print(f"[find_clips_cli] wrote {out_path} ({len(existing['clips'])} clips total)")


if __name__ == "__main__":
    main()
