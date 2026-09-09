"""Command-line and desktop entry points."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_compare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="musicreader compare",
        description="Compare image-extracted lyrics with a reference or hymns JSON.",
    )
    parser.add_argument("--image", type=Path, required=True, help="hymnal image or PDF")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference", help="reference lyric text")
    source.add_argument("--hymns-json", type=Path, help="hymns JSON containing cclilyrcs")
    parser.add_argument(
        "--number",
        help="SheetImage stem (or Number fallback) when using --hymns-json",
    )
    parser.add_argument("--verses", type=int, choices=range(1, 10), metavar="N")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--confidence", type=float, default=0.45)
    parser.add_argument("--debug-dir", type=Path)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="musicreader",
        description="Reconstruct parallel hymn verses from sheet-music images or PDFs.",
    )
    parser.add_argument("input", nargs="?", type=Path, help="JPG, PNG, TIFF, or PDF")
    parser.add_argument("-o", "--output", type=Path, help="write lyrics to this file")
    parser.add_argument(
        "--verses",
        type=int,
        choices=range(1, 10),
        metavar="N",
        help="expected parallel verse count (default: detect automatically)",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="PDF rendering DPI (default: 300)"
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.45,
        help="minimum OCR confidence from 0 to 1 (default: 0.45)",
    )
    parser.add_argument(
        "--debug-dir",
        type=Path,
        help="save detected lyric crops and marked-up pages",
    )
    parser.add_argument(
        "--gui", action="store_true", help="open the Windows desktop interface"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "compare":
        return compare_main(argv[1:])
    args = build_parser().parse_args(argv)
    if args.gui or args.input is None:
        try:
            from .gui import run_gui

            run_gui()
            return 0
        except Exception as error:
            print(f"Could not open the desktop interface: {error}", file=sys.stderr)
            return 1

    if not 0 <= args.confidence <= 1:
        print("--confidence must be between 0 and 1.", file=sys.stderr)
        return 2
    if not 150 <= args.dpi <= 600:
        print("--dpi must be between 150 and 600.", file=sys.stderr)
        return 2

    try:
        from .extractor import LyricExtractor

        extractor = LyricExtractor(
            dpi=args.dpi,
            verses=args.verses,
            minimum_confidence=args.confidence,
            debug_directory=args.debug_dir,
            progress=lambda message: print(message, file=sys.stderr),
        )
        result = extractor.extract(args.input)
    except Exception as error:
        print(f"Extraction failed: {error}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.text + "\n", encoding="utf-8")
        print(f"Saved lyrics to {args.output}", file=sys.stderr)
    else:
        print(result.text)

    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return 0 if result.verses else 1


def compare_main(argv: list[str]) -> int:
    args = build_compare_parser().parse_args(argv)
    if args.hymns_json and not args.number:
        print("--number is required with --hymns-json.", file=sys.stderr)
        return 2
    if not 0 <= args.confidence <= 1 or not 150 <= args.dpi <= 600:
        print("--confidence must be 0..1 and --dpi must be 150..600.", file=sys.stderr)
        return 2

    try:
        from .compare import compare_text, reference_from_hymns_json
        from .extractor import LyricExtractor

        if args.reference is not None:
            reference = args.reference
        else:
            reference, _ = reference_from_hymns_json(args.hymns_json, args.number)
        result = LyricExtractor(
            dpi=args.dpi,
            verses=args.verses,
            minimum_confidence=args.confidence,
            debug_directory=args.debug_dir,
            progress=lambda message: print(message, file=sys.stderr),
        ).extract(args.image)
        comparison = compare_text(result.text, reference)
    except Exception as error:
        print(f"Comparison failed: {error}", file=sys.stderr)
        return 1

    status = "MATCH" if comparison.matches else "DIFFER"
    print(f"{status} score={comparison.score:.3f}")
    if comparison.diff:
        print(comparison.diff)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return 0 if comparison.matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
