"""
03_reframe.py — cut ONE clip's range onto its own timeline, then reframe it
from 16:9 to 1:1.

WHY IT CUTS FIRST (self-contained, not chained off 01_cut_segments)
    Reframing is a per-clip operation for the VOD->Clips workflow — one short
    highlight at a time, not the whole many-segment YT-cut timeline. Earlier
    version assumed a timeline was already open and reframed every clip on
    video track 1; if that timeline happened to be a 100+ range YT cut,
    SmartReframe() ran once per clip back to back and took forever. This
    version always builds its own single-clip timeline from CLIP_JSON_PATH
    first, so it only ever reframes exactly one clip.

** SmartReframe() itself is still UNVERIFIED — first run is a test. ** See
prior notes: Studio/AI feature, auto-tracks the subject, requires the
timeline's frame size to already be square (set via per-timeline custom
settings below). If it returns False, that's likely a system-requirements
gate (see "Studio and AI Scripting APIs" in the bundled Readme.txt), not
necessarily a script bug — tell me exactly what prints.

WHAT IT DOES
    1. Reads CLIP_JSON_PATH — must have exactly ONE range in keep_ranges (a
       single clip, not a multi-segment cut list; this script rejects more).
    2. Creates a fresh timeline, appends just that one range.
    3. Sets the timeline to TARGET_SIZE x TARGET_SIZE (1:1) and calls
       SmartReframe() on the single resulting clip.

PRECONDITIONS
    - Resolve open with a project loaded. No timeline needs to be open first.
    - Run from Workspace -> Scripts -> Edit -> 03_reframe.

INPUT
    CLIP_JSON_PATH (edit the constant below before each run) — same shape as
    01_cut_segments' decision file, but with exactly one keep_range:
        {"source_file": "/path/to/vod.mp4", "keep_ranges": [{"start": 2141.0, "end": 2193.0}]}

OUTPUT
    Prints cut + reframe success/failure to the Resolve console.
"""

import json
import os

CLIP_JSON_PATH = "/path/to/your/clip.json"
TARGET_SIZE = 1080


def fail(msg):
    print(f"[03_reframe] FAILED: {msg}")


def main():
    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        return fail("could not get Resolve app object — is this running from Workspace > Scripts?")

    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        return fail("no project open in Resolve")

    if not os.path.exists(CLIP_JSON_PATH):
        return fail(f"decision file not found: {CLIP_JSON_PATH}")
    with open(CLIP_JSON_PATH) as f:
        decision = json.load(f)

    vod_path = decision.get("source_file") or decision.get("vod_path")
    keep_ranges = decision.get("keep_ranges", [])
    if not vod_path or not os.path.exists(vod_path):
        return fail(f"source_file missing or does not exist: {vod_path}")
    if len(keep_ranges) != 1:
        return fail(
            f"expected exactly 1 range for a single-clip reframe, got {len(keep_ranges)} — "
            "this script is per-clip, not per-VOD. Use a decision file with one range."
        )

    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    media_item = None
    for clip in root_folder.GetClipList():
        if clip.GetClipProperty("File Path") == vod_path:
            media_item = clip
            break
    if media_item is None:
        imported = media_pool.ImportMedia([vod_path])
        if not imported:
            return fail(f"Resolve failed to import: {vod_path}")
        media_item = imported[0]

    fps = float(media_item.GetClipProperty("FPS"))
    if fps <= 0:
        return fail(f"could not read a valid FPS from the clip (got {fps})")

    r = keep_ranges[0]
    start_sec, end_sec = r["start"], r["end"]
    if end_sec <= start_sec:
        return fail(f"invalid range: {start_sec}-{end_sec}")

    base_name = os.path.splitext(os.path.basename(vod_path))[0]
    timeline_name = f"{base_name}_clip_{int(start_sec)}"
    existing_names = {project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)}
    n = 1
    while timeline_name in existing_names:
        n += 1
        timeline_name = f"{base_name}_clip_{int(start_sec)}_{n}"

    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    if timeline is None:
        return fail(f"Resolve refused to create timeline '{timeline_name}'")
    project.SetCurrentTimeline(timeline)

    start_frame = round(start_sec * fps)
    end_frame = round(end_sec * fps)
    appended = media_pool.AppendToTimeline([{"mediaPoolItem": media_item, "startFrame": start_frame, "endFrame": end_frame}])
    if not appended:
        return fail(f"failed to append clip range {start_sec}-{end_sec}s")
    print(f"[03_reframe] cut clip {start_sec:.2f}-{end_sec:.2f}s onto new timeline '{timeline_name}'")

    ok_custom = timeline.SetSetting("useCustomSettings", "1")
    ok_width = timeline.SetSetting("timelineResolutionWidth", str(TARGET_SIZE))
    ok_height = timeline.SetSetting("timelineResolutionHeight", str(TARGET_SIZE))
    print(f"[03_reframe] set timeline to {TARGET_SIZE}x{TARGET_SIZE} — useCustomSettings={ok_custom} width={ok_width} height={ok_height}")
    if not (ok_custom and ok_width and ok_height):
        print("[03_reframe] WARNING: one or more resolution settings were rejected — SmartReframe below may act on the wrong frame size")

    item = timeline.GetItemListInTrack("video", 1)[0]
    result = item.SmartReframe()
    if result:
        print(f"[03_reframe] DONE — SmartReframe OK on '{item.GetName()}'")
    else:
        print(f"[03_reframe] DONE WITH ERRORS — SmartReframe returned False for '{item.GetName()}' (may be a system-requirements gate, see header)")


main()
