"""High-level offline lyric extraction pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
from rapidocr import RapidOCR

from .layout import load_pages, lyric_regions
from .models import ExtractionResult, TextBox
from .reconstruct import (
    merge_page_verses,
    normalize_lyrics,
    reconstruct_page_sections,
    rows_from_boxes,
)


ProgressCallback = Callable[[str], None]


def _write_image(path: Path, image: np.ndarray) -> None:
    extension = path.suffix or ".png"
    success, encoded = cv2.imencode(extension, image)
    if not success:
        raise ValueError(f"Could not encode debug image: {path}")
    encoded.tofile(path)


class LyricExtractor:
    """Detect lyric regions, OCR them locally, and rebuild parallel verses."""

    def __init__(
        self,
        *,
        dpi: int = 300,
        verses: int | None = None,
        minimum_confidence: float = 0.45,
        debug_directory: Path | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        if verses is not None and not 1 <= verses <= 9:
            raise ValueError("Verse count must be between 1 and 9.")
        self.dpi = dpi
        self.verses = verses
        self.minimum_confidence = minimum_confidence
        self.debug_directory = debug_directory
        self.progress = progress or (lambda _: None)
        self._ocr: RapidOCR | None = None

    @property
    def ocr(self) -> RapidOCR:
        if self._ocr is None:
            self.progress("Loading the local OCR model…")
            self._ocr = RapidOCR()
        return self._ocr

    def _recognize(self, image: np.ndarray) -> list[TextBox]:
        # The inter-staff band is often only 45–70 pixels high in a 300 DPI
        # scan.  Grayscale normalization and a larger scale preserve small
        # engraved glyphs without thresholding away antialiased strokes.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        enlarged = cv2.resize(
            gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC
        )
        result = self.ocr(enlarged)
        if result.boxes is None or result.txts is None or result.scores is None:
            return []
        scale = 2.5
        return [
            TextBox(
                text=str(text),
                score=float(score),
                points=np.asarray(points, dtype=np.float32) / scale,
            )
            for points, text, score in zip(result.boxes, result.txts, result.scores)
        ]

    def extract(self, source: Path | str) -> ExtractionResult:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source}")

        self.progress(f"Opening {source.name}…")
        pages = load_pages(source, self.dpi)
        warnings: list[str] = []
        debug_files: list[Path] = []
        page_results: list[dict[int, str]] = []
        page_choruses: list[str] = []

        if self.debug_directory:
            self.debug_directory.mkdir(parents=True, exist_ok=True)

        for page_number, image in enumerate(pages, start=1):
            self.progress(f"Finding lyric regions on page {page_number}…")
            regions, page_warnings = lyric_regions(image, page_number)
            warnings.extend(page_warnings)
            system_rows: list[list[str]] = []
            annotated = image.copy()

            for region in regions:
                self.progress(
                    f"Reading page {page_number}, system {region.system_number}…"
                )
                crop = image[region.top : region.bottom, region.left : region.right]
                boxes = self._recognize(crop)
                rows = rows_from_boxes(boxes, self.minimum_confidence)
                if not rows:
                    warnings.append(
                        f"Page {page_number}, system {region.system_number}: "
                        "no lyric text was recognized."
                    )
                else:
                    system_rows.append(rows)

                if self.debug_directory:
                    crop_path = self.debug_directory / (
                        f"page-{page_number:02d}-system-"
                        f"{region.system_number:02d}.png"
                    )
                    _write_image(crop_path, crop)
                    debug_files.append(crop_path)
                    cv2.rectangle(
                        annotated,
                        (region.left, region.top),
                        (region.right, region.bottom),
                        (0, 0, 255),
                        max(2, image.shape[1] // 1000),
                    )

            if self.debug_directory:
                page_path = self.debug_directory / f"page-{page_number:02d}.png"
                _write_image(page_path, annotated)
                debug_files.append(page_path)

            if system_rows:
                verses, chorus = reconstruct_page_sections(system_rows, self.verses)
                page_results.append(verses)
                if chorus:
                    page_choruses.append(chorus)

        verses = merge_page_verses(page_results)
        chorus = normalize_lyrics(" ".join(page_choruses))
        if not verses:
            warnings.append(
                "No lyrics were reconstructed. Try a 300–400 DPI scan with "
                "complete, straight staff lines."
            )
        self.progress("Finished.")
        return ExtractionResult(
            verses=verses,
            chorus=chorus,
            warnings=warnings,
            debug_files=debug_files,
        )
