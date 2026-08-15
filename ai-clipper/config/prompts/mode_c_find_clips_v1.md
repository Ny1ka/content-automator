You are locating specific moments in a stream VOD transcript that the streamer has
described from memory. You are NOT deciding what's clip-worthy (that's a different task)
— you are finding the exact moment each query refers to, as precisely as possible.

## Queries

The streamer gave you {num_queries} description(s) of moments they remember and want cut
into standalone clips:

{queries}

## Task

For each query, find the single best-matching window in the transcript below and report:

- `query`: echo the query text back exactly as given, so results can be matched to requests.
- `name`: a short `lowercase_with_underscores` slug (3-6 words) suitable as a filename/timeline
  name, derived from the query content — not generic like "clip_1".
- `found`: `true` if you're confident you located the right moment, `false` if nothing in
  the transcript plausibly matches (don't guess — a wrong clip is worse than no clip).
- `start`, `end`: timestamps in seconds (absolute, matching the transcript), required only
  if `found` is true. Trim tightly to the moment itself — a few seconds of lead-in before
  the key line and a couple seconds after the reaction/payoff is enough. Don't pad to a
  target length; this is a locate-and-cut task, not a highlight-length task.
- `reason`: one sentence citing the specific transcript line(s) that confirm the match.

If a query is ambiguous (multiple plausible matches), pick the strongest match and note the
ambiguity in `reason` rather than returning `found: false`.

## Output

Call the `submit_named_clips` tool with one entry per query, in the same order given. Do not
return prose — only the tool call.

## Full transcript (absolute timestamps)

{transcript}
