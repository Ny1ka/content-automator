You are analyzing a full stream VOD transcript to identify contiguous segments describing
what the streamer was doing, for a VOD-to-YouTube-video edit.

## Task

Given the transcript below (timestamped text, word-level timing available on request),
produce a list of contiguous segments covering the *entire* VOD duration with no gaps and
no overlaps. Every second of the VOD must belong to exactly one segment.

For each segment, decide:
- `start`, `end`: timestamps in seconds
- `label`: a short human-readable description of what's happening (e.g. "Fortnite with
  friends", "talking / off-topic conversation", "AFK / bathroom break")
- `keep`: `true` if this segment should appear in the final edited video, `false` if it
  should be cut entirely (dead air, long AFK stretches, technical difficulties, awkward
  silences with nothing happening)

## What counts as a segment boundary

Start a new segment when the streamer's *activity* changes — switching games, switching
from gameplay to direct-camera talking, taking a break, etc. Do NOT create a new segment
for every topic change within the same activity (e.g. if the streamer is playing Fortnite
and talks about three different subjects between rounds, that's still one "Fortnite with
friends" segment, not three).

## What counts as `keep: false`

Mark a segment `keep: false` only when a reasonable YouTube editor would cut it entirely
— not just "less interesting," but actively not worth including: dead air with no
speech or action, AFK stretches, stream setup/technical issues, or long silences. When in
doubt, prefer `keep: true` — the execution layer already has separate silence-based dead-
air trimming (see the `silences` field), so this segment-level `keep` flag is for cutting
whole *stretches of activity*, not micro-trimming pauses within an otherwise good segment.

## Output

Call the `submit_segments` tool with your result. Do not return prose — only the tool call.

## Transcript

{transcript}
