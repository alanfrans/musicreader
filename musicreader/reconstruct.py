"""Turn positioned OCR fragments into ordered hymn verses."""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

import numpy as np

from .models import TextBox


VERSE_NUMBER = re.compile(r"^\s*([1-9])\s*[\.\):]?\s*")
LETTER = re.compile(r"[A-Za-z]")


def rows_from_boxes(boxes: list[TextBox], minimum_confidence: float) -> list[str]:
    """Cluster OCR boxes by vertical position and read each row left-to-right."""

    def is_lyric_fragment(box: TextBox) -> bool:
        text = box.text.strip()
        letter_count = len(LETTER.findall(text))
        return (
            box.score >= minimum_confidence
            and (
                letter_count >= 2
                or text.upper() in {"A", "I", "O"}
                or re.fullmatch(r"[1-9][.\):]?", text) is not None
            )
        )

    usable = [
        box
        for box in boxes
        if is_lyric_fragment(box)
    ]
    if not usable:
        return []

    typical_height = max(8.0, float(np.median([box.height for box in usable])))
    tolerance = typical_height * 0.65
    rows: list[list[TextBox]] = []
    row_centers: list[float] = []

    for box in sorted(usable, key=lambda item: (item.center_y, item.left)):
        closest = (
            min(range(len(rows)), key=lambda i: abs(row_centers[i] - box.center_y))
            if rows
            else None
        )
        if closest is None or abs(row_centers[closest] - box.center_y) > tolerance:
            rows.append([box])
            row_centers.append(box.center_y)
        else:
            rows[closest].append(box)
            row_centers[closest] = float(
                np.mean([fragment.center_y for fragment in rows[closest]])
            )

    ordered = sorted(zip(row_centers, rows), key=lambda item: item[0])
    return [
        " ".join(fragment.text.strip() for fragment in sorted(row, key=lambda b: b.left))
        for _, row in ordered
    ]


def verse_label(text: str) -> int | None:
    match = VERSE_NUMBER.match(text)
    return int(match.group(1)) if match else None


def strip_verse_label(text: str) -> str:
    return VERSE_NUMBER.sub("", text, count=1).strip()


def estimate_verse_count(systems: list[list[str]], requested: int | None) -> int:
    if requested:
        return requested
    counts = Counter(len(rows) for rows in systems if 1 <= len(rows) <= 8)
    if not counts:
        return 1
    repeated = [count for count, frequency in counts.items() if frequency >= 2]
    return max(repeated) if repeated else counts.most_common(1)[0][0]


def reconstruct_page(
    systems: list[list[str]], requested_verses: int | None = None
) -> dict[int, str]:
    """Join corresponding lyric rows across all systems on one page."""

    systems = [rows for rows in systems if rows]
    if not systems:
        return {}

    verse_count = estimate_verse_count(systems, requested_verses)
    first_labels = [verse_label(row) for row in systems[0]]
    explicit = [label for label in first_labels if label is not None]

    if len(explicit) == len(systems[0]):
        row_labels = [int(label) for label in first_labels if label is not None]
    elif len(systems[0]) == 1 and explicit:
        row_labels = explicit
    else:
        row_labels = list(range(1, verse_count + 1))

    pieces: dict[int, list[str]] = {label: [] for label in row_labels}
    for rows in systems:
        if len(rows) == len(row_labels):
            labels = row_labels
        elif len(rows) == 1 and verse_label(rows[0]) is not None:
            labels = [int(verse_label(rows[0]))]  # type: ignore[arg-type]
        else:
            # OCR occasionally misses a row. Preserve deterministic ordering and
            # warn at a higher layer rather than guessing absent middle rows.
            labels = row_labels[: len(rows)]
        for label, row in zip(labels, rows):
            pieces.setdefault(label, []).append(strip_verse_label(row))

    return {
        label: normalize_lyrics(" ".join(parts))
        for label, parts in pieces.items()
        if any(parts)
    }


def normalize_lyrics(text: str, join_syllables: bool = True) -> str:
    """Normalize OCR spacing and optionally join music syllabification marks."""

    text = text.replace("•", "-").replace("·", "-")
    text = re.sub(r"\s+", " ", text).strip()
    # A standalone capital O is commonly read as zero in older hymn typefaces.
    text = re.sub(r"(?<!\w)0(?=\s+[a-z])", "O", text)
    if join_syllables:
        text = re.sub(r"(?<=[A-Za-z])\s*[-‐‑]\s*(?=[A-Za-z])", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[]) +", r"\1", text)
    return text


def merge_page_verses(page_results: list[dict[int, str]]) -> dict[int, str]:
    """Merge pages, preferring the most complete copy of repeated verses."""

    candidates: dict[int, list[str]] = {}
    for page in page_results:
        for label, text in page.items():
            candidates.setdefault(label, []).append(text)

    if not candidates:
        return {}

    output: dict[int, str] = {}
    for label, versions in sorted(candidates.items()):
        chosen = max(versions, key=lambda value: len(LETTER.findall(value)))
        # A repeated optional setting is a second rendering, not a continuation.
        # Only concatenate page fragments when they are genuinely different.
        distinct = [
            value
            for value in versions
            if value != chosen
            and SequenceMatcher(None, value.lower(), chosen.lower()).ratio() < 0.65
        ]
        output[label] = normalize_lyrics(" ".join([chosen, *distinct]))
    return output
