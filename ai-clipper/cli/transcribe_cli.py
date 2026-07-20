import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transcription import transcribe


def main():
    parser = argparse.ArgumentParser(description="Transcribe a VOD with word-level timestamps and silence detection.")
    parser.add_argument("vod_path")
    parser.add_argument("--model-size", default="medium")
    parser.add_argument("--force", action="store_true", help="Ignore cache and re-transcribe.")
    parser.add_argument("--out", help="Write result JSON to this path (default: print to stdout).")
    args = parser.parse_args()

    t0 = time.time()
    result = transcribe(args.vod_path, model_size=args.model_size, force=args.force)
    elapsed = time.time() - t0

    print(
        f"segments={len(result['segments'])} silences={len(result['silences'])} "
        f"duration={result['duration']:.1f}s elapsed={elapsed:.1f}s",
        file=sys.stderr,
    )

    payload = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(payload)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
