def format_transcript(segments: list[dict], start: float | None = None, end: float | None = None) -> str:
    """Render transcript segments as compact timestamped lines for a prompt.

    Word-level timing is deliberately left out here — it roughly doubles
    token count for information Layer 2 doesn't need (segment-level text is
    enough to judge "what's happening" and "is this funny"); Layer 3 is what
    consumes word-level timestamps for frame-accurate cuts.
    """
    lines = []
    for seg in segments:
        if start is not None and seg["end"] < start:
            continue
        if end is not None and seg["start"] > end:
            continue
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
    return "\n".join(lines)
