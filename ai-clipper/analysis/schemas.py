from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ClipType(str, Enum):
    FUNNY = "funny"
    INFORMATIONAL = "informational"
    WHOLESOME = "wholesome"
    SAD = "sad"
    SCARY = "scary"


class Segment(BaseModel):
    start: float
    end: float
    label: str
    keep: bool

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start")
        if start is not None and v <= start:
            raise ValueError(f"end ({v}) must be after start ({start})")
        return v


class SegmentsResponse(BaseModel):
    """Mode A output: VOD -> YT video segment identification."""
    segments: list[Segment]


# Judgment call: 20-40s target, 70s hard cap per the spec. Coverage/precision
# scoring (eval/score_clips.py) treats anything over 70s as an automatic
# schema violation, not just a soft warning, since the spec calls it a hard
# cap.
CLIP_MIN_SOFT = 20.0
CLIP_MAX_SOFT = 40.0
CLIP_MAX_HARD = 70.0


class Clip(BaseModel):
    start: float
    end: float
    type: ClipType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    sfx_points: list[float] = Field(default_factory=list)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start")
        if start is not None and v <= start:
            raise ValueError(f"end ({v}) must be after start ({start})")
        if start is not None and v - start > CLIP_MAX_HARD:
            raise ValueError(f"clip length {v - start:.1f}s exceeds the {CLIP_MAX_HARD}s hard cap")
        return v

    @field_validator("sfx_points")
    @classmethod
    def sfx_points_in_range(cls, v, info):
        start, end = info.data.get("start"), info.data.get("end")
        if start is not None and end is not None:
            for p in v:
                if not (start <= p <= end):
                    raise ValueError(f"sfx_point {p} falls outside clip window [{start}, {end}]")
        return v


class ClipsResponse(BaseModel):
    """Mode B output: VOD -> Clips candidate identification."""
    clips: list[Clip]


class NamedClip(BaseModel):
    """Mode C output: one clip located from a natural-language query."""
    query: str
    name: str  # short slug for the Resolve timeline name, e.g. "teammate_1hp"
    found: bool
    start: float | None = None
    end: float | None = None
    reason: str = ""

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start")
        if v is not None and start is not None and v <= start:
            raise ValueError(f"end ({v}) must be after start ({start})")
        return v

    @field_validator("name")
    @classmethod
    def name_is_slug(cls, v):
        import re
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError(f"name must be a lowercase_with_underscores slug, got '{v}'")
        return v


class NamedClipsResponse(BaseModel):
    clips: list[NamedClip]


# Flat (no $ref/$defs) tool schemas for providers whose function-calling schema support
# doesn't handle JSON Schema references (Gemini's does not). Anthropic's tool_use accepts
# pydantic's model_json_schema() with $defs directly, so it doesn't need these — kept here
# so both providers validate against the exact same field set without drifting apart.
SEGMENTS_SCHEMA_FLAT = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "label": {"type": "string"},
                    "keep": {"type": "boolean"},
                },
                "required": ["start", "end", "label", "keep"],
            },
        },
    },
    "required": ["segments"],
}

NAMED_CLIPS_SCHEMA_FLAT = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "name": {"type": "string"},
                    "found": {"type": "boolean"},
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["query", "name", "found"],
            },
        },
    },
    "required": ["clips"],
}

CLIPS_SCHEMA_FLAT = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "type": {"type": "string", "enum": [t.value for t in ClipType]},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                    "sfx_points": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["start", "end", "type", "confidence", "reason"],
            },
        },
    },
    "required": ["clips"],
}
