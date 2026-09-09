"""Offline comparison of extracted hymn text with CCLI lyrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

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
_OCR_SPLITS = {
    "glo ry": "glory",
    "redeem er": "redeemer",
    "devo tion": "devotion",
    "off rings": "offerings",
    "offrings": "offerings",
    "creyou are": "creator you are",
}
_SECTION_LABEL = re.compile(
    r"(?<![a-z0-9])(?:verse\s*([1-9]\d*)|([1-9]\d*)\s*[.):]|chorus)(?=\s|$)",
    re.IGNORECASE,
)


def normalize_for_compare(text: str) -> str:
    """Return comparable words, ignoring CCLI formatting and engraving marks."""
    text = _BOILERPLATE.sub("\n", text.replace("\r\n", "\n"))
    lines: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"\(judson\)|songselect|ccli\b|copyright|words?:|music:|"
            r"admin(?:istered)?\b|used\s+by\s+permission|"
            r"van\s+ness|lifeway|ascap|bmi",
            line,
            re.I,
        ) or re.match(r"\s*(?:©|\(c\)|\d{4}\b)", line, re.I):
            continue
        line = _VERSE_LABEL.sub("", line)
        if re.fullmatch(r"\s*(?:chorus|verse\s*\d*)\s*:?\s*", line, re.I):
            continue
        lines.append(line)
    text = " ".join(lines).lower()
    # Labels can occur inline in SongSelect exports, not only at line starts.
    text = _SECTION_LABEL.sub(" ", text)
    for source, replacement in _CONTRACTIONS.items():
        text = text.replace(source, replacement)
    for source, replacement in _OCR_SPLITS.items():
        text = text.replace(source, replacement)
    # Syllable hyphens and apostrophes are typography, not lyric changes.
    text = re.sub(r"(?<=[a-z])\s*[-‐‑]\s*(?=[a-z])", "", text)
    text = re.sub(r"[’']", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def section_order(text: str) -> list[str]:
    """Extract the displayed verse/chorus sequence from lyric text."""
    order: list[str] = []
    for match in _SECTION_LABEL.finditer(text.replace("\r\n", "\n")):
        label = "chorus" if match.group(0).lower().startswith("chorus") else (
            match.group(1) or match.group(2)
        )
        if not order or order[-1] != label:
            order.append(label)
    return order


@dataclass(frozen=True)
class Comparison:
    match: bool
    content_score: float
    verse_order_mismatch: bool
    extracted_order: list[str]
    reference_order: list[str]
    issues: list[dict[str, object]]
    extracted: str
    reference: str
    diff: str

    @property
    def matches(self) -> bool:
        return self.match

    @property
    def score(self) -> float:
        """Backward-compatible alias for callers using the old result."""
        return self.content_score


def compare_text(extracted: str, reference: str) -> Comparison:
    left = normalize_for_compare(extracted)
    right = normalize_for_compare(reference)
    ordered_score = SequenceMatcher(None, left, right, autojunk=False).ratio()
    score = max(ordered_score, _fuzzy_token_overlap(left.split(), right.split()))
    extracted_order = section_order(extracted)
    reference_order = section_order(reference)
    order_mismatch = bool(
        extracted_order and reference_order and extracted_order != reference_order
    )
    match = score >= 0.92
    issues: list[dict[str, object]] = []
    if order_mismatch:
        issues.append(
            {
                "type": "verse_order_mismatch",
                "severity": "high",
                "message": "The hymnal and reference arrange verses/chorus differently.",
                "extracted_order": extracted_order,
                "reference_order": reference_order,
            }
        )
    if not match:
        issues.append(
            {
                "type": "lyric_content_mismatch",
                "severity": "high",
                "message": f"Normalized lyric content similarity is {score:.3f}.",
                "content_score": score,
            }
        )
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
    return Comparison(
        match=match,
        content_score=score,
        verse_order_mismatch=order_mismatch,
        extracted_order=extracted_order,
        reference_order=reference_order,
        issues=issues,
        extracted=left,
        reference=right,
        diff=diff,
    )


def _fuzzy_token_overlap(left: list[str], right: list[str]) -> float:
    """Compare words without penalizing a chorus moved after the verses."""
    if not left or not right:
        return 0.0
    unused = set(range(len(right)))
    matched = 0
    for token in left:
        if not unused:
            break
        best = max(
            (
                (SequenceMatcher(None, token, right[index], autojunk=False).ratio(), index)
                for index in unused
            ),
            default=(0.0, -1),
        )
        threshold = 0.80 if len(token) <= 3 else 0.72
        if best[0] >= threshold:
            matched += 1
            unused.remove(best[1])
    return 2 * matched / (len(left) + len(right))


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
