"""Mechanical (non-LLM) silence-cutting per the VOD Highlight Cutter spec, §2-3/6-7.

DEVIATION from the spec as literally written: §2 describes the audio-energy
pass as ground truth that gates whether a transcript gap becomes a cut. In
practice that gated on amplitude, not speech — game audio/music playing under
a pause kept transcript-confirmed silences from ever clearing -40dB, so real
"streamer isn't talking" gaps were being rejected wholesale (13 cuts instead
of the expected much-higher count). Per explicit correction: the streamer
talking is what defines a highlight-worthy moment, not ambient loudness, so
transcript word-gaps are now the PRIMARY signal and are accepted on their own.
The audio-energy pass is downgraded to an optional boundary-refinement nudge
(snap the pad anchor to the energy-silence edge when one overlaps and
disagrees by more than `boundary_tolerance`) — it can no longer veto a cut.

Content-level (LLM) cutting from spec §4 is NOT implemented here — this module
only does the mechanical layer (§2, §3, §6, §7). §4 belongs with Layer 2
(analysis/), which already exists separately and would emit its own
content_cut candidates to be merged with this module's keep_ranges upstream of
Resolve, not inside this module.
"""
from dataclasses import dataclass, field

from transcription.silence import detect_silences
from transcription.types import Silence

# Judgment calls — all taken directly from the spec's stated defaults, not
# re-guessed. Flagging because these are exactly the "your taste, not mine"
# knobs the spec calls out:
GAP_THRESHOLD = 2.0          # spec §2: min transcript word-gap to even consider a cut
BOUNDARY_TOLERANCE = 0.3     # spec §2: disagreement with audio-energy beyond this snaps to audio-energy
TRAILING_PAD = 1.0           # spec §3: silence kept after the last word, default of the 0.8-1.2s range
LEADING_PAD = 0.4            # spec §3: silence kept before the next word, default of the 0.3-0.5s range
MIN_PAD = 0.2                # spec §3: floor when padding gets scaled down for a short gap
MIN_CUT = 1.5                # spec §3: don't bother cutting if less than this much is actually removed
MIN_KEEP = 1.0                # spec §6: reject/merge keep-ranges shorter than this (flicker-cut guard)
ENERGY_NOISE_DB = -40.0      # spec §2: "-40dB floor" for the audio-energy ground-truth pass
ENERGY_MIN_DURATION = 2.0    # spec §2: "sustained for 2s"
MAX_REMOVED_FRACTION = 0.40  # spec §7: flag rather than silently accept if more than this is cut


@dataclass
class CutCandidate:
    gap_start: float   # last_word.end
    gap_end: float     # next_word.start
    audio_start: float
    audio_end: float


def _flatten_words(transcript_segments, window_start: float, window_end: float) -> list[dict]:
    words = []
    for seg in transcript_segments:
        for w in seg.get("words", []):
            if w["end"] <= window_start or w["start"] >= window_end:
                continue
            words.append(w)
    words.sort(key=lambda w: w["start"])
    return words


def _find_overlapping_silence(gap_start: float, gap_end: float, silences: list[Silence]) -> Silence | None:
    best = None
    best_overlap = 0.0
    for s in silences:
        overlap = min(gap_end, s["end"]) - max(gap_start, s["start"])
        if overlap > best_overlap:
            best_overlap = overlap
            best = s
    return best if best_overlap > 0 else None


def _reconcile_anchor(word_boundary: float, audio_boundary: float, tolerance: float) -> float:
    return audio_boundary if abs(audio_boundary - word_boundary) > tolerance else word_boundary


def build_keep_ranges(
    transcript_segments: list[dict],
    vod_path: str,
    window_start: float,
    window_end: float,
    fps: float,
    gap_threshold: float = GAP_THRESHOLD,
    boundary_tolerance: float = BOUNDARY_TOLERANCE,
    trailing_pad: float = TRAILING_PAD,
    leading_pad: float = LEADING_PAD,
    min_pad: float = MIN_PAD,
    min_cut: float = MIN_CUT,
    min_keep: float = MIN_KEEP,
    energy_silences: list[Silence] | None = None,
) -> dict:
    if energy_silences is None:
        energy_silences = detect_silences(vod_path, noise_db=ENERGY_NOISE_DB, min_duration=ENERGY_MIN_DURATION)
    energy_silences = [s for s in energy_silences if s["end"] > window_start and s["start"] < window_end]

    words = _flatten_words(transcript_segments, window_start, window_end)

    accepted_cuts: list[tuple[float, float]] = []
    too_short_after_padding: list[dict] = []

    for i in range(len(words) - 1):
        last_word, next_word = words[i], words[i + 1]
        gap = next_word["start"] - last_word["end"]
        if gap < gap_threshold:
            continue

        # Audio-energy is a refinement, not a gate: a transcript gap is
        # cuttable on its own (the streamer isn't talking), regardless of
        # whether game audio/music keeps the track above the energy floor.
        silence = _find_overlapping_silence(last_word["end"], next_word["start"], energy_silences)
        if silence is not None:
            anchor_out = _reconcile_anchor(last_word["end"], silence["start"], boundary_tolerance)
            anchor_in = _reconcile_anchor(next_word["start"], silence["end"], boundary_tolerance)
        else:
            anchor_out = last_word["end"]
            anchor_in = next_word["start"]

        cut_out = anchor_out + trailing_pad
        cut_in = anchor_in - leading_pad
        available = anchor_in - anchor_out

        if cut_in <= cut_out:
            # padding would overlap or exceed the gap — scale both pads down proportionally
            if available <= 2 * min_pad:
                too_short_after_padding.append({"start": round(anchor_out, 3), "end": round(anchor_in, 3)})
                continue  # not even enough room for the floor padding on both sides
            scale = (available - 2 * min_pad) / (trailing_pad + leading_pad) if (trailing_pad + leading_pad) > 0 else 0
            scaled_trailing = min_pad + trailing_pad * scale
            scaled_leading = min_pad + leading_pad * scale
            cut_out = anchor_out + scaled_trailing
            cut_in = anchor_in - scaled_leading

        if cut_in - cut_out < min_cut:
            too_short_after_padding.append({"start": round(anchor_out, 3), "end": round(anchor_in, 3)})
            continue

        accepted_cuts.append((cut_out, cut_in))

    accepted_cuts.sort()

    keep_ranges = []
    cursor = window_start
    for cut_out, cut_in in accepted_cuts:
        if cut_out > cursor:
            keep_ranges.append({"start": round(cursor, 3), "end": round(cut_out, 3)})
        cursor = max(cursor, cut_in)
    if window_end > cursor:
        keep_ranges.append({"start": round(cursor, 3), "end": round(window_end, 3)})

    keep_ranges = _merge_short_ranges(keep_ranges, min_keep)
    _validate(keep_ranges, window_start, window_end)

    return {
        "source_file": vod_path,
        "fps": fps,
        "keep_ranges": keep_ranges,
        "flagged_for_review": [],
        "_diagnostics": {
            "too_short_after_padding": too_short_after_padding,
            "cuts_applied": len(accepted_cuts),
        },
    }


def _merge_short_ranges(keep_ranges: list[dict], min_keep: float) -> list[dict]:
    if not keep_ranges:
        return keep_ranges
    merged = [dict(keep_ranges[0])]
    for r in keep_ranges[1:]:
        if r["end"] - r["start"] < min_keep:
            merged[-1]["end"] = r["end"]  # absorb the short range into the previous one (undoes the cut before it)
        else:
            merged.append(dict(r))
    if merged[-1]["end"] - merged[-1]["start"] < min_keep and len(merged) > 1:
        last = merged.pop()
        merged[-1]["end"] = last["end"]
    return merged


def _validate(keep_ranges: list[dict], window_start: float, window_end: float) -> None:
    prev_end = window_start
    for r in keep_ranges:
        if r["end"] <= r["start"]:
            raise ValueError(f"invalid range: {r}")
        if r["start"] < prev_end:
            raise ValueError(f"ranges overlap or are out of order: {r} after end={prev_end}")
        prev_end = r["end"]

    total = window_end - window_start
    kept = sum(r["end"] - r["start"] for r in keep_ranges)
    removed_fraction = 1 - (kept / total) if total > 0 else 0
    if removed_fraction > MAX_REMOVED_FRACTION:
        print(
            f"[keep_ranges] WARNING: removed {removed_fraction:.0%} of the window "
            f"(> {MAX_REMOVED_FRACTION:.0%} threshold) — thresholds may be too aggressive, sanity check before using"
        )
