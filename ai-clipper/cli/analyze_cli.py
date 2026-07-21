import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import run_mode_a, run_mode_b
from transcription.cache import vod_fingerprint


def main():
    parser = argparse.ArgumentParser(description="Run Layer 2 analysis (Mode A segments or Mode B clips) on a transcript.")
    parser.add_argument("transcript_json", help="Path to a transcript JSON produced by transcribe_cli.py")
    parser.add_argument("mode", choices=["a", "b"], help="a = segment identification, b = clip candidates")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--provider", choices=["anthropic", "gemini"], default=None, help="Defaults to whichever API key is set (ANTHROPIC_API_KEY preferred).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    transcript = json.loads(Path(args.transcript_json).read_text())
    fp = vod_fingerprint(transcript["vod_path"])

    if args.mode == "a":
        result = run_mode_a(fp, transcript["segments"], prompt_version=args.prompt_version, force=args.force, provider=args.provider, model=args.model)
    else:
        result = run_mode_b(fp, transcript["segments"], transcript["duration"], prompt_version=args.prompt_version, force=args.force, provider=args.provider, model=args.model)

    payload = json.dumps(result.model_dump(), indent=2)
    if args.out:
        Path(args.out).write_text(payload)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
