"""Score a Mode B (clips) response against a manually-annotated ground truth file.

Ground truth here only lists topics the streamer named from memory with wide
approximate search windows — it's enough to check coverage (did the model find these
moments at all) but NOT precision (how many of the model's other candidates are actually
good) since it isn't an exhaustive list of every clip-worthy moment in the VOD. Precision
needs a human to read through the full candidate list below.

Usage: python eval/score_clips.py <mode_b_output.json> <expected.json>
"""
import json
import sys


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def score(output: dict, expected: dict):
    got = output["clips"]
    want = expected["clips"]

    matched = 0
    print("Coverage against named topics:\n")
    for w in want:
        candidates = [g for g in got if overlaps(g["start"], g["end"], w["approx_start"], w["approx_end"])]
        if candidates:
            matched += 1
            print(f"  [FOUND] '{w['topic']}' (search window {w['approx_start']}-{w['approx_end']}s)")
            for c in candidates:
                length = c["end"] - c["start"]
                print(f"      -> [{c['start']:.0f}-{c['end']:.0f}] ({length:.0f}s) type={c['type']} conf={c['confidence']:.2f}: {c['reason']}")
        else:
            print(f"  [MISSED] '{w['topic']}' (search window {w['approx_start']}-{w['approx_end']}s)")

    coverage = matched / len(want) if want else 1.0
    print(f"\nCoverage: {matched}/{len(want)} = {coverage:.0%}")

    over_cap = [c for c in got if c["end"] - c["start"] > 70]
    if over_cap:
        print(f"\nWARNING: {len(over_cap)} clip(s) exceed the 70s hard cap (should have failed schema validation):")
        for c in over_cap:
            print(f"  [{c['start']:.0f}-{c['end']:.0f}] ({c['end']-c['start']:.0f}s)")

    print(f"\nAll {len(got)} candidates the model returned — read every one and mark false positives yourself, this script can't:")
    for c in sorted(got, key=lambda c: -c["confidence"]):
        length = c["end"] - c["start"]
        print(f"  [{c['start']:.0f}-{c['end']:.0f}] ({length:.0f}s) type={c['type']} conf={c['confidence']:.2f}: {c['reason']}")

    note = expected.get("clips_note")
    if note:
        print(f"\nNote: {note}")


if __name__ == "__main__":
    output = json.loads(open(sys.argv[1]).read())
    expected = json.loads(open(sys.argv[2]).read())
    score(output, expected)
