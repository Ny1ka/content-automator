from typing import TypedDict


class WordTiming(TypedDict):
    word: str
    start: float
    end: float
    confidence: float


class TranscriptSegment(TypedDict):
    start: float
    end: float
    text: str
    words: list[WordTiming]


class Silence(TypedDict):
    start: float
    end: float


class TranscriptResult(TypedDict):
    segments: list[TranscriptSegment]
    silences: list[Silence]
    duration: float
    vod_path: str
    model_size: str
