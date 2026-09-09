"""Offline comparison of extracted hymn text with CCLI lyrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

from .reconstruct import normalize_lyrics


_BOILERPLATE = re.compile(
    r"(?:^|\n)\s*(?:ccli\s+song\s*#?\s*\d+|"
    r"copyright\b.*|admin(?:istered)?\b.*|"
    r"used\s+by\s+permission\b.*)\s*(?=\n|$)",
    re.IGNORECASE,
)
_VERSE_LABEL = re.compile(r"^\s*(?:verse|chorus|v\d+)\s*\d*\s*:?\s*", re.I)
_CONTRACTIONS = {
    "off'rings": "offerings",
    "off’ rings": "offerings",
    "rev'rence": "reverence",
    "rev’ rence": "reverence",
    "o'er": "oer",
}


def normalize_for_compare(text: str) -> str:
    """Return comparable words, ignoring CCLI formatting and engraving marks."""
    text = _BOILERPLATE.sub("\n", text.replace("\r\n", "\n"))
    lines: list[str] = []
    for line in text.splitlines():
        if re.search(r"\(judson\)|songselect", line, re.I):
            continue
        line = _VERSE_LABEL.sub("", line)
        if re.fullmatch(r"\s*(?:chorus|verse\s*\d*)\s*:?\s*", line, re.I):
            continue
        lines.append(line)
    text = " ".join(lines).lower()
    for source, replacement in _CONTRACTIONS.items():
        text = text.replace(source, replacement)
    # Syllable hyphens and apostrophes are typography, not lyric changes.
    text = re.sub(r"(?<=[a-z])\s*[-‐‑]\s*(?=[a-z])", "", text)
    text = re.sub(r"[’']", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Comparison:
    score: float
    extracted: str
    reference: str
    diff: str

    @property
    def matches(self) -> bool:
        return self.score >= 0.92


def compare_text(extracted: str, reference: str) -> Comparison:
    left = normalize_for_compare(extracted)
    right = normalize_for_compare(reference)
    score = SequenceMatcher(None, left, right).ratio()
    diff = "\n".join(
        unified_diff(
            left.split(),
            right.split(),
            fromfile="extracted",
            tofile="reference",
            n=3,
            lineterm="",
        )
    )
    return Comparison(score, left, right, diff)


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("hymns", "songs", "items", "data"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        return [value]
    return []


def reference_from_hymns_json(path: Path, number: str) -> tuple[str, dict[str, Any]]:
    """Find a hymn by SheetImage filename, falling back to Number."""
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    records = _records(value)
    wanted = Path(number).stem.lower()
    sheet_matches = [
        item
        for item in records
        if Path(str(item.get("SheetImage", ""))).stem.lower() == wanted
    ]
    matches = sheet_matches or [
        item for item in records if str(item.get("Number", "")).strip() == number
    ]
    if not matches:
        raise KeyError(f"No hymn with SheetImage or Number {number!r} in {path}")
    record = matches[0]
    lyrics = record.get("cclilyrcs")
    if not isinstance(lyrics, str) or not lyrics.strip():
        raise ValueError(f"Hymn {number!r} has no non-empty cclilyrcs field")
    return lyrics, record
