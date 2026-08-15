import hashlib
import json
import os
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

import common.env  # noqa: F401 - loads .env before any os.environ lookups below
from common.progress import ProgressReporter
from . import cache as analysis_cache
from .anthropic_backend import DEFAULT_ANTHROPIC_MODEL, call_tool_anthropic
from .gemini_backend import DEFAULT_GEMINI_MODEL, call_tool_gemini
from .schemas import CLIPS_SCHEMA_FLAT, NAMED_CLIPS_SCHEMA_FLAT, SEGMENTS_SCHEMA_FLAT, ClipsResponse, NamedClipsResponse, SegmentsResponse
from .transcript_format import format_transcript

PROMPT_DIR = Path(__file__).resolve().parent.parent / "config" / "prompts"
FAILURE_LOG_DIR = Path(__file__).resolve().parent.parent / "eval" / "cache" / "analysis_failures"

MAX_RETRIES = 2

# Judgment call: 20-minute windows, 2-minute overlap, matching the spec's
# suggestion. Long enough to give the model context on a topic thread, short
# enough that a 2+ hour VOD stays comfortably inside a single context window
# per call and doesn't risk quality degradation from a huge transcript.
WINDOW_MINUTES = 20.0
OVERLAP_MINUTES = 2.0


def _resolve_provider(provider: str | None) -> str:
    if provider:
        return provider
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    raise RuntimeError(
        "No provider available: set ANTHROPIC_API_KEY or GEMINI_API_KEY (env or .env), "
        "or pass provider='anthropic'|'gemini' explicitly."
    )


def _default_model(provider: str) -> str:
    return DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_GEMINI_MODEL


def _log_failure(tool_name: str, raw: dict, error: str):
    FAILURE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = FAILURE_LOG_DIR / f"{tool_name}_{int(time.time()*1000)}.json"
    with open(p, "w") as f:
        json.dump({"raw": raw, "error": error}, f, indent=2)


def _call_tool(provider: str, prompt: str, tool_name: str, pydantic_cls: type[BaseModel], flat_schema: dict, model: str) -> dict:
    schema = pydantic_cls.model_json_schema() if provider == "anthropic" else flat_schema
    backend = call_tool_anthropic if provider == "anthropic" else call_tool_gemini

    last_error = None
    for _attempt in range(MAX_RETRIES + 1):
        raw = backend(prompt, tool_name, schema, model=model)
        try:
            pydantic_cls.model_validate(raw)
            return raw
        except ValidationError as e:
            last_error = str(e)
            _log_failure(tool_name, raw, last_error)
    raise RuntimeError(f"'{tool_name}' failed schema validation after {MAX_RETRIES + 1} attempts: {last_error}")


def run_mode_a(
    vod_fingerprint: str,
    segments: list[dict],
    prompt_version: str = "v1",
    force: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> SegmentsResponse:
    provider = _resolve_provider(provider)
    model = model or _default_model(provider)
    cache_key = f"mode_a_{prompt_version}_{provider}_{model}"

    if not force:
        cached = analysis_cache.load(vod_fingerprint, cache_key)
        if cached is not None:
            return SegmentsResponse.model_validate(cached)

    prompt_template = (PROMPT_DIR / f"mode_a_segments_{prompt_version}.md").read_text()
    prompt = prompt_template.format(transcript=format_transcript(segments))

    raw = _call_tool(provider, prompt, "submit_segments", SegmentsResponse, SEGMENTS_SCHEMA_FLAT, model)
    result = SegmentsResponse.model_validate(raw)

    analysis_cache.save(vod_fingerprint, cache_key, result.model_dump())
    return result


def run_mode_c(
    vod_fingerprint: str,
    segments: list[dict],
    queries: list[str],
    prompt_version: str = "v1",
    force: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> NamedClipsResponse:
    """Locate one clip per natural-language query against the full transcript.

    Unlike Mode A/B, this isn't windowed — a locate-a-specific-moment task
    benefits from full-transcript context and is a single-shot ask, not an
    exhaustive scan, so there's no chunking/dedup step here.
    """
    provider = _resolve_provider(provider)
    model = model or _default_model(provider)
    cache_key = f"mode_c_{prompt_version}_{provider}_{model}"
    window_key = hashlib.sha256("\n".join(sorted(queries)).encode()).hexdigest()[:16]

    if not force:
        cached = analysis_cache.load(vod_fingerprint, cache_key, window_key)
        if cached is not None:
            return NamedClipsResponse.model_validate(cached)

    prompt_template = (PROMPT_DIR / f"mode_c_find_clips_{prompt_version}.md").read_text()
    prompt = prompt_template.format(
        num_queries=len(queries),
        queries="\n".join(f"{i + 1}. {q}" for i, q in enumerate(queries)),
        transcript=format_transcript(segments),
    )

    raw = _call_tool(provider, prompt, "submit_named_clips", NamedClipsResponse, NAMED_CLIPS_SCHEMA_FLAT, model)
    result = NamedClipsResponse.model_validate(raw)

    analysis_cache.save(vod_fingerprint, cache_key, result.model_dump(), window_key)
    return result


def _dedupe_clips(clips: list[dict]) -> list[dict]:
    """Merge near-duplicate clips flagged by adjacent overlapping windows.

    Deterministic overlap-based dedup rather than a second LLM pass: two
    candidates are considered duplicates if their time ranges overlap by more
    than half of the shorter clip's length, in which case the higher-
    confidence one wins. Chosen over an extra model call for this step since
    it's a mechanical "which one is bigger" decision, not a judgment call
    that needs the model's understanding of content — keeps this step free,
    deterministic, and easy to unit test.
    """
    clips = sorted(clips, key=lambda c: c["start"])
    kept: list[dict] = []
    for c in clips:
        merged = False
        for k in kept:
            overlap = min(c["end"], k["end"]) - max(c["start"], k["start"])
            shorter = min(c["end"] - c["start"], k["end"] - k["start"])
            if overlap > 0 and overlap / shorter > 0.5:
                if c["confidence"] > k["confidence"]:
                    kept[kept.index(k)] = c
                merged = True
                break
        if not merged:
            kept.append(c)
    return sorted(kept, key=lambda c: c["start"])


def run_mode_b(
    vod_fingerprint: str,
    segments: list[dict],
    duration: float,
    prompt_version: str = "v1",
    window_minutes: float = WINDOW_MINUTES,
    overlap_minutes: float = OVERLAP_MINUTES,
    force: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> ClipsResponse:
    provider = _resolve_provider(provider)
    model = model or _default_model(provider)
    cache_key = f"mode_b_{prompt_version}_{provider}_{model}"

    if not force:
        cached = analysis_cache.load(vod_fingerprint, cache_key)
        if cached is not None:
            return ClipsResponse.model_validate(cached)

    prompt_template = (PROMPT_DIR / f"mode_b_clips_{prompt_version}.md").read_text()

    step = window_minutes * 60 - overlap_minutes * 60
    windows = []
    t = 0.0
    while t < duration:
        w_end = min(t + window_minutes * 60, duration)
        windows.append((t, w_end))
        t += step

    progress = ProgressReporter("analysis-mode-b", total=len(windows))
    all_clips: list[dict] = []
    for w_start, w_end in windows:
        window_key = f"{w_start:.0f}_{w_end:.0f}"
        cached_window = None if force else analysis_cache.load(vod_fingerprint, f"{cache_key}_window", window_key)
        if cached_window is not None:
            raw = cached_window
        else:
            window_transcript = format_transcript(segments, start=w_start, end=w_end)
            prompt = prompt_template.format(
                window_minutes=f"{window_minutes:.0f}",
                window_start=f"{w_start:.0f}",
                window_end=f"{w_end:.0f}",
                transcript=window_transcript,
            )
            raw = _call_tool(provider, prompt, "submit_clips", ClipsResponse, CLIPS_SCHEMA_FLAT, model)
            analysis_cache.save(vod_fingerprint, f"{cache_key}_window", raw, window_key)
        all_clips.extend(raw.get("clips", []))
        progress.step(f"window {w_start:.0f}s-{w_end:.0f}s")
    progress.finish()

    deduped = _dedupe_clips(all_clips)
    result = ClipsResponse.model_validate({"clips": deduped})

    analysis_cache.save(vod_fingerprint, cache_key, result.model_dump())
    return result
