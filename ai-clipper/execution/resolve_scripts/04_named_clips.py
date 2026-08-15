"""
04_named_clips.py — cut each clip in a named-clips JSON onto its own,
correctly-named timeline. No effects, no reframe — pure cut-and-name so you
can export and edit each one by hand afterward.

WHAT IT DOES
    Reads NAMED_CLIPS_JSON_PATH: {"source_file": "...", "clips": [{"name",
    "start", "end", ...}, ...]}. For each entry, creates a timeline named
    after that clip's `name` field (not a generic counter) and appends just
    that one range. Skips a clip if a timeline with that exact name already
    exists, so re-running after adding new queries doesn't re-cut ones you've
    already reviewed/exported.

PRECONDITIONS
    - Resolve open with a project loaded. No timeline needs to be open first.
    - Run from Workspace -> Scripts -> Edit -> 04_named_clips.

INPUT
    NAMED_CLIPS_JSON_PATH (edit the constant below before each run) — produced
    by `python -m cli.find_clips_cli` (see that file's docstring):
        {
          "source_file": "/absolute/path/to/vod.mp4",
          "clips": [
            {"name": "teammate_1hp", "start": 2141.3, "end": 2168.9, "query": "...", "reason": "..."}
          ]
        }

OUTPUT
    One timeline per clip, named exactly after `name` (so it's obvious which
    exported file is which once you get to Deliver). Prints a per-clip and
    summary report to the Resolve console.
"""

import json
import os

NAMED_CLIPS_JSON_PATH = "/path/to/your/named_clips.json"


def fail(msg):
    print(f"[04_named_clips] FAILED: {msg}")


def main():
    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        return fail("could not get Resolve app object — is this running from Workspace > Scripts?")

    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        return fail("no project open in Resolve")

    if not os.path.exists(NAMED_CLIPS_JSON_PATH):
        return fail(f"named-clips file not found: {NAMED_CLIPS_JSON_PATH}")
    with open(NAMED_CLIPS_JSON_PATH) as f:
        data = json.load(f)

    vod_path = data.get("source_file")
    clips = data.get("clips", [])
    if not vod_path or not os.path.exists(vod_path):
        return fail(f"source_file missing or does not exist: {vod_path}")
    if not clips:
        return fail("no clips in the named-clips file")

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
        print(f"[04_named_clips] imported {vod_path}")

    fps = float(media_item.GetClipProperty("FPS"))
    if fps <= 0:
        return fail(f"could not read a valid FPS from the clip (got {fps})")

    existing_names = {project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)}

    created, skipped, errored = 0, 0, 0
    for c in clips:
        name = c["name"]
        start_sec, end_sec = c["start"], c["end"]

        if name in existing_names:
            print(f"[04_named_clips]   skipping '{name}' — timeline already exists")
            skipped += 1
            continue
        if end_sec <= start_sec:
            print(f"[04_named_clips]   FAILED '{name}': invalid range {start_sec}-{end_sec}")
            errored += 1
            continue

        timeline = media_pool.CreateEmptyTimeline(name)
        if timeline is None:
            print(f"[04_named_clips]   FAILED '{name}': Resolve refused to create the timeline")
            errored += 1
            continue
        project.SetCurrentTimeline(timeline)

        start_frame = round(start_sec * fps)
        end_frame = round(end_sec * fps)
        appended = media_pool.AppendToTimeline([{"mediaPoolItem": media_item, "startFrame": start_frame, "endFrame": end_frame}])
        if not appended:
            print(f"[04_named_clips]   FAILED '{name}': append rejected for {start_sec}-{end_sec}s")
            errored += 1
            continue

        existing_names.add(name)
        created += 1
        print(f"[04_named_clips]   created '{name}': {start_sec:.2f}-{end_sec:.2f}s ({end_sec - start_sec:.1f}s)")

    print(f"[04_named_clips] DONE — {created} created, {skipped} skipped (already existed), {errored} failed")


main()
