from enum import Enum
from typing import Literal, TypedDict

Corner = Literal["top-left", "top-right"]
AspectRatio = Literal["1:1", "16:9", "9:16"]
FadeDirection = Literal["in", "out"]


class KeepRange(TypedDict):
    start: float
    end: float


class ImportResult(TypedDict):
    media_pool_item_id: str


class ExportResult(TypedDict):
    output_path: str
    duration: float
