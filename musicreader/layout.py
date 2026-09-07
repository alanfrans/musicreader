"""Page loading and deterministic sheet-music layout detection."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import pymupdf
import numpy as np

from .models import LyricRegion, Staff


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def load_pages(path: Path, dpi: int = 300) -> list[np.ndarray]:
    """Load an image or rasterize every PDF page as BGR arrays."""

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        document = pymupdf.open(path)
        scale = dpi / 72
        matrix = pymupdf.Matrix(scale, scale)
        pages: list[np.ndarray] = []
        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                pages.append(cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR))
        finally:
            document.close()
        return pages

    if suffix not in IMAGE_SUFFIXES:
        supported = ", ".join(sorted(IMAGE_SUFFIXES | {".pdf"}))
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: {supported}")

    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return [image]


def _runs(values: Iterable[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for value in values:
        if not groups or value > groups[-1][-1] + 1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return groups


def detect_staff_line_centers(image: np.ndarray) -> list[float]:
    """Locate long horizontal rules likely to be staff lines."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]
    width = image.shape[1]
    kernel_width = max(35, width // 28)
    horizontal = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1)),
    )
    coverage = np.count_nonzero(horizontal, axis=1)
    candidate_rows = np.flatnonzero(coverage >= width * 0.20)
    centers = [float(np.mean(run)) for run in _runs(candidate_rows.tolist())]

    # Note stems and symbols can interrupt the middle of a thick staff rule,
    # producing two nearby horizontal-mask peaks for one printed line.
    duplicate_distance = max(3.0, width / 350)
    consolidated: list[list[float]] = []
    for center in centers:
        if not consolidated or center - consolidated[-1][-1] > duplicate_distance:
            consolidated.append([center])
        else:
            consolidated[-1].append(center)
    return [float(np.mean(group)) for group in consolidated]


def group_staves(line_centers: list[float]) -> list[Staff]:
    """Group candidate rules into non-overlapping five-line staves."""

    staves: list[Staff] = []
    index = 0
    while index <= len(line_centers) - 5:
        lines = line_centers[index : index + 5]
        gaps = np.diff(lines)
        median_gap = float(np.median(gaps))
        regular = (
            3 <= median_gap <= 80
            and float(np.max(np.abs(gaps - median_gap))) <= max(2.5, median_gap * 0.35)
        )
        separated_after = (
            index + 5 == len(line_centers)
            or line_centers[index + 5] - lines[-1] > median_gap * 1.7
        )
        if regular and separated_after:
            staves.append(Staff(tuple(lines)))  # type: ignore[arg-type]
            index += 5
        else:
            index += 1
    return staves


def lyric_regions(
    image: np.ndarray, page_number: int = 1
) -> tuple[list[LyricRegion], list[str]]:
    """Return regions between paired treble and bass staves."""

    warnings: list[str] = []
    staves = group_staves(detect_staff_line_centers(image))
    if len(staves) < 2:
        return [], [f"Page {page_number}: no paired music staves were detected."]
    if len(staves) % 2:
        warnings.append(
            f"Page {page_number}: detected an odd number of staves; "
            "the last staff was ignored."
        )

    height, width = image.shape[:2]
    margin_x = max(4, round(width * 0.025))
    regions: list[LyricRegion] = []
    for pair_index in range(0, len(staves) - 1, 2):
        treble, bass = staves[pair_index : pair_index + 2]
        spacing = float(np.median([treble.spacing, bass.spacing]))
        top = max(0, round(treble.lines[-1] + spacing * 0.65))
        bottom = min(height, round(bass.lines[0] - spacing * 0.65))
        if bottom - top < spacing * 1.5:
            warnings.append(
                f"Page {page_number}, system {pair_index // 2 + 1}: "
                "the lyric gap was too small and was skipped."
            )
            continue
        regions.append(
            LyricRegion(
                page_number=page_number,
                system_number=pair_index // 2 + 1,
                left=margin_x,
                top=top,
                right=width - margin_x,
                bottom=bottom,
            )
        )
    return regions, warnings
