# Manual annotation — stream_vod_2026-07-18.mp4

Ground truth for scoring Layer 2 (Analysis) Mode A / Mode B output. Timestamps below are
as given by the streamer from memory, not yet frame-verified against the transcript —
treat as approximate until cross-checked once the transcript is in.

## Mode A — segments (VOD → YT video)

| start    | end      | label                        |
|----------|----------|------------------------------|
| 2:17     | 49:02    | Fortnite with Friends        |
| 1:05:11  | end      | Rainbow 6 Siege w/ Friends   |

Sub-structure noted by streamer (not necessarily separate top-level segments):
- Fortnite with Friends: warming up in Creative → 4 games of Fortnite → talking in between
- Rainbow 6 Siege: talking w/ friends → playing unranked

**Resolved:** the 49:02–1:05:11 gap is not a break — it's continued talking (Riot Games
internship / Valorant discussion, see Mode B below), between Fortnite ending and R6
starting. So Mode A ground truth should really be three segments, not two:

| start    | end      | label                                  |
|----------|----------|-----------------------------------------|
| 2:17     | 49:02    | Fortnite with Friends                   |
| 49:02    | 1:05:11  | Talking (Riot/Valorant conversation)    |
| 1:05:11  | end      | Rainbow 6 Siege w/ Friends              |

## Mode B — clip candidates (VOD → Clips)

Located in the transcript by keyword search (approximate — not frame-verified, and none
of these are yet trimmed to the 20-40s/70s-cap target window; that trimming is Layer 2's
job):

| topic                          | approx window     | note |
|---------------------------------|-------------------|------|
| OperaGX Browser                 | 18:20 – 19:45     | single contained exchange |
| Favorite Fortnite skin           | 29:40 – 34:10     | ~4.5min, spans multiple skins/tangents — needs trimming to the actual punchline moment(s), possibly multiple clips |
| Valorant agent ability (the guy who made it) | 56:50 – 58:30 | |
| Riot Games internships           | 53:00 – 59:25     | overlaps/interleaves with the Valorant ability discussion — same conversation, may need to be split or picked as one longer topic vs. two clips |

No `type` classification (funny/informational/wholesome/sad/scary) given yet per clip —
ask the streamer to tag each once Layer 2 proposes exact boundaries, or have Layer 2
classify and let the streamer correct it.
