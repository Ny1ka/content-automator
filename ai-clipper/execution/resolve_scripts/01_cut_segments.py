"""
01_cut_segments.py — cut a VOD down to its keep_ranges on a fresh timeline.

WHAT IT DOES
    Reads a decision JSON file (DECISION_JSON_PATH below), imports the VOD it
    names into the media pool if not already present, creates a new empty
    timeline, and appends each keep_range as a frame-accurate clip in order.
    Ranges outside keep_ranges (dead air, cut content) are simply never added.

PRECONDITIONS
    - Resolve is open with a project loaded (any project — this script
      doesn't care which, it just uses whatever GetCurrentProject() returns).
    - No timeline needs to be open first — this script creates its own.
    - Run from Workspace -> Scripts -> Edit -> 01_cut_segments (this only
      works run this way, inside Resolve's own Python interpreter, which
      injects the `bmd` global — it will NOT run as a plain `python` script
      from the terminal).

INPUT
    DECISION_JSON_PATH (edit the constant below before each run):
        {
          "vod_path": "/absolute/path/to/vod.mp4",
          "keep_ranges": [{"start": 0.0, "end": 8.0}, {"start": 16.0, "end": 25.0}]
        }
    keep_ranges are in seconds, source-file-relative (not timeline-relative).

OUTPUT
    A new timeline named "<vod filename>_cut_<N>" (auto-numbered to avoid
    clobbering a timeline from a previous run), containing the keep_ranges
    back to back in order. Prints a per-range and summary report to the
    Resolve console (Workspace -> Console, or the script window's own output).
"""

import json
import os

DECISION_JSON_PATH = "/Users/nyikawachira/nyikacode/content-automator/ai-clipper/eval/decisions/rainbow6_segment.json"


def fail(msg):
    print(f"[01_cut_segments] FAILED: {msg}")


def main():
    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        return fail("could not get Resolve app object — is this running from Workspace > Scripts?")

    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        return fail("no project open in Resolve")

    if not os.path.exists(DECISION_JSON_PATH):
        return fail(f"decision file not found: {DECISION_JSON_PATH}")
    with open(DECISION_JSON_PATH) as f:
        decision = json.load(f)

    vod_path = decision.get("source_file") or decision.get("vod_path")
    keep_ranges = decision.get("keep_ranges", [])
    if not vod_path or not os.path.exists(vod_path):
        return fail(f"vod_path missing or does not exist: {vod_path}")
    if not keep_ranges:
        return fail("decision has no keep_ranges — nothing to cut")

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
        print(f"[01_cut_segments] imported {vod_path}")
    else:
        print(f"[01_cut_segments] reusing already-imported clip for {vod_path}")

    fps = float(media_item.GetClipProperty("FPS"))
    if fps <= 0:
        return fail(f"could not read a valid FPS from the clip (got {fps})")

    base_name = os.path.splitext(os.path.basename(vod_path))[0]
    timeline_name = f"{base_name}_cut"
    existing_names = {project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)}
    n = 1
    while timeline_name in existing_names:
        n += 1
        timeline_name = f"{base_name}_cut_{n}"

    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    if timeline is None:
        return fail(f"Resolve refused to create timeline '{timeline_name}'")
    project.SetCurrentTimeline(timeline)

    ordered_ranges = sorted(keep_ranges, key=lambda r: r["start"])
    appended = 0
    total_kept_sec = 0.0
    for r in ordered_ranges:
        start_sec, end_sec = r["start"], r["end"]
        if end_sec <= start_sec:
            print(f"[01_cut_segments]   skipping invalid range {start_sec}-{end_sec} (end <= start)")
            continue
        start_frame = round(start_sec * fps)
        end_frame = round(end_sec * fps)
        clip_info = {"mediaPoolItem": media_item, "startFrame": start_frame, "endFrame": end_frame}
        result = media_pool.AppendToTimeline([clip_info])
        if not result:
            print(f"[01_cut_segments]   FAILED to append range {start_sec}-{end_sec}s (frames {start_frame}-{end_frame})")
            continue
        appended += 1
        total_kept_sec += end_sec - start_sec
        print(f"[01_cut_segments]   appended {start_sec:.2f}-{end_sec:.2f}s (frames {start_frame}-{end_frame})")

    print(
        f"[01_cut_segments] DONE — timeline '{timeline_name}': "
        f"{appended}/{len(ordered_ranges)} ranges appended, "
        f"{total_kept_sec:.1f}s kept out of original ranges requested"
    )


main()
