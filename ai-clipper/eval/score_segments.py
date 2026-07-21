"""Score a Mode A (segments) response against a manually-annotated ground truth file.

Usage: python eval/score_segments.py <mode_a_output.json> <expected.json>
"""
import json
import sys

BOUNDARY_TOLERANCE = 5.0  # seconds, per the build spec's Phase 2 acceptance criteria


def score(output: dict, expected: dict):
    got = output["segments"]
    want = [s for s in expected["segments"]]

    matched_want = set()
    matches = []
    for w_idx, w in enumerate(want):
        for g in got:
            if abs(g["start"] - w["start"]) <= BOUNDARY_TOLERANCE and abs(g["end"] - w["end"]) <= BOUNDARY_TOLERANCE:
                matched_want.add(w_idx)
                matches.append((w, g))
                break

    coverage = len(matched_want) / len(want) if want else 1.0

    print(f"Coverage: {len(matched_want)}/{len(want)} = {coverage:.0%}  (tolerance ±{BOUNDARY_TOLERANCE}s)\n")
    for w_idx, w in enumerate(want):
        status = "MATCHED" if w_idx in matched_want else "MISSED"
        print(f"  [{status}] expected [{w['start']:.0f}-{w['end']:.0f}] '{w['label']}'")

    print(f"\nModel returned {len(got)} segments total — precision needs a human read, not just this script:")
    for g in got:
        print(f"  [{g['start']:.0f}-{g['end']:.0f}] keep={g['keep']} '{g['label']}'")

    note = expected.get("segments_note")
    if note:
        print(f"\nNote: {note}")


if __name__ == "__main__":
    output = json.loads(open(sys.argv[1]).read())
    expected = json.loads(open(sys.argv[2]).read())
    score(output, expected)
