You are analyzing a window of a stream VOD transcript to find short clip-worthy moments
for vertical short-form content (TikTok/Shorts/Reels).

## Window context

This is a ~{window_minutes}-minute slice of a longer VOD, from {window_start}s to
{window_end}s. The transcript below only covers this slice; timestamps are absolute
(seconds from the start of the full VOD, not from the start of this window). A short
overlap with the neighboring windows is included on purpose — a later deduplication pass
merges near-duplicate candidates found in the overlap, so it's fine (expected, even) if
the same moment gets flagged by two adjacent windows.

## Task

Identify clip candidates: short, self-contained moments that would work as a standalone
vertical clip without extra setup, for a viewer with no context on the stream. For each:

- `start`, `end`: timestamps in seconds (absolute, matching the transcript). Target 20-40
  seconds. 70 seconds is a hard cap — never exceed it. Prefer trimming tighter over
  including dead setup/wind-down around the actual moment.
- `type`: exactly one of `funny | informational | wholesome | sad | scary`
- `confidence`: 0.0-1.0, your estimate of how clip-worthy this actually is (see below)
- `reason`: one sentence — what specifically makes this moment work (not a plot summary)
- `sfx_points`: absolute timestamps within [start, end] for sound-effect placement. Only
  flag a point if it aligns with a punchline, a reveal, or a visible/audible reaction —
  never place points at even intervals as a guess. Most clips will have 0-2 sfx_points,
  not one per sentence.

## What counts as clip-worthy (read carefully — this encodes a judgment call)

A moment is a candidate if it has a clear beginning and payoff within the length target —
not just "on topic" or "the streamer said something." Concretely:

- `funny`: a joke, a bit, or a reaction that lands — you should be able to point to the
  specific line that's the punchline. General banter is not enough on its own.
- `informational`: the streamer explains or reveals something a viewer would plausibly
  want to know, learn, or repeat elsewhere (a fact, a strong opinion, advice, insider
  knowledge) — not just any factual statement made in passing.
- `wholesome`: a genuine, unironic moment of warmth, gratitude, or connection with friends
  or chat.
- `sad` / `scary`: a genuine emotional or tense moment, not just a serious tone shift.

Do not flag a moment just because it is topically interesting — a long, meandering,
well-informed answer to a question is not automatically an `informational` clip unless it
also has a tight, punchy self-contained window inside it. If the interesting part runs
longer than the target, find the sub-window that captures the payoff, not the whole
explanation.

Confidence should reflect actual clip-worthiness, not transcription certainty — a 0.9
means "I would put this in a clips compilation," a 0.4 means "borderline, include only if
we're short on candidates."

## Output

Call the `submit_clips` tool with your result. Do not return prose — only the tool call.

## Transcript (this window only, absolute timestamps)

{transcript}
