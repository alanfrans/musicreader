"""FastMCP bridge for Sunday hymn comparison on Windows.

Run with ``python -m musicreader.mcp_server`` and register that command as a
stdio MCP server in Sunday's existing ``sunday_mcp.py`` host.
"""

from __future__ import annotations

from pathlib import Path

from .compare import compare_text, reference_from_hymns_json
from .extractor import LyricExtractor

DEFAULT_HYMNS_JSON = Path(r"C:\hymnal\consolidatedmusic\hymns.json")
DEFAULT_IMAGE_DIR = Path(r"C:\hymnal\consolidatedmusic\jpg")


def _extract(image_path: str) -> dict[str, object]:
    result = LyricExtractor().extract(Path(image_path))
    return {
        "text": result.text,
        "verses": result.verses,
        "chorus": result.chorus,
        "warnings": result.warnings,
    }


def compare_hymn_lyrics(
    number: str,
    image_path: str | None = None,
    hymns_json: str = str(DEFAULT_HYMNS_JSON),
    image_dir: str = str(DEFAULT_IMAGE_DIR),
) -> dict[str, object]:
    """Extract and compare one hymn, returning Sunday-friendly issue data."""
    reference, record = reference_from_hymns_json(Path(hymns_json), number)
    selected_image = Path(image_path) if image_path else (
        Path(image_dir) / Path(str(record["SheetImage"])).name
    )
    extraction = _extract(str(selected_image))
    comparison = compare_text(str(extraction["text"]), reference)
    output = {
        "number": number,
        "image_path": str(selected_image),
        "title": record.get("Song") or record.get("Title"),
        "match": comparison.match,
        "content_score": comparison.content_score,
        "verse_order_mismatch": comparison.verse_order_mismatch,
        "extracted_order": comparison.extracted_order,
        "reference_order": comparison.reference_order,
        "issues": comparison.issues,
        "extracted_text": extraction["text"],
        "warnings": extraction["warnings"],
    }
    return output


def extract_hymn_lyrics(image_path: str) -> dict[str, object]:
    """Return raw locally extracted hymn lyrics."""
    return _extract(image_path)


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:  # pragma: no cover - exercised on setup only
        raise RuntimeError(
            "Install the optional MCP dependency with: pip install 'mcp>=2.2.0'"
        ) from error

    server = FastMCP("musicreader")
    server.tool()(compare_hymn_lyrics)
    server.tool()(extract_hymn_lyrics)
    return server


def main() -> None:
    _build_server().run()


if __name__ == "__main__":
    main()
