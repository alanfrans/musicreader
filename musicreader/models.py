"""Small data models shared by the extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class TextBox:
    """Recognized text and its coordinates within a crop."""

    text: str
    score: float
    points: np.ndarray

    @property
    def left(self) -> float:
        return float(np.min(self.points[:, 0]))

    @property
    def top(self) -> float:
        return float(np.min(self.points[:, 1]))

    @property
    def right(self) -> float:
        return float(np.max(self.points[:, 0]))

    @property
    def bottom(self) -> float:
        return float(np.max(self.points[:, 1]))

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class Staff:
    """Five detected staff-line y coordinates."""

    lines: tuple[float, float, float, float, float]

    @property
    def spacing(self) -> float:
        return float(np.median(np.diff(self.lines)))


@dataclass(frozen=True)
class LyricRegion:
    """Image rectangle expected to contain parallel verse rows."""

    page_number: int
    system_number: int
    left: int
    top: int
    right: int
    bottom: int


@dataclass
class ExtractionResult:
    """Output returned by :class:`LyricExtractor`."""

    verses: dict[int, str]
    chorus: str = ""
    warnings: list[str] = field(default_factory=list)
    debug_files: list[Path] = field(default_factory=list)

    @property
    def text(self) -> str:
        chunks = []
        show_numbers = len(self.verses) > 1 or next(iter(self.verses), 1) != 1
        for number, verse in sorted(self.verses.items()):
            prefix = f"{number}. " if show_numbers else ""
            chunks.append(f"{prefix}{verse}".strip())
        if self.chorus:
            chunks.append(f"Chorus: {self.chorus}")
        return "\n\n".join(chunks)
