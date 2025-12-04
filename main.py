import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence, Tuple

from pdf_style_editor import ContainerSelector, PDFStyleAwareEditor


RectTuple = Tuple[float, float, float, float]


def _parse_bbox(values: Optional[Sequence[str]]) -> Optional[RectTuple]:
    if not values:
        return None
    if len(values) != 4:
        raise argparse.ArgumentTypeError("Bounding box requires four numbers.")
    return tuple(float(v) for v in values)  # type: ignore[return-value]


def _build_selector(args: argparse.Namespace) -> ContainerSelector:
    return ContainerSelector(
        page=args.page,
        text=args.text,
        regex=args.regex,
        bbox=_parse_bbox(args.bbox),
        block_id=args.block_id,
        tolerance=args.tolerance,
        case_sensitive=args.case_sensitive,
    )


def _cmd_inspect(args: argparse.Namespace) -> None:
    editor = PDFStyleAwareEditor(args.input)
    selector = _build_selector(args)
    matches = editor.scraper.find(selector)
    limit = args.limit or len(matches)
    for match in matches[:limit]:
        payload = {
            "page": match.page_number,
            "block": match.block_id,
            "line": match.line_id,
            "span": match.span_id,
            "rect": match.rect,
            "text": match.text.strip(),
            "style": asdict(match.style),
        }
        print(payload)
    editor.close()


def _cmd_replace(args: argparse.Namespace) -> None:
    editor = PDFStyleAwareEditor(args.input)
    selector = _build_selector(args)
    editor.replace_text(
        selector,
        args.replacement,
        padding=args.padding,
    )
    output = args.output or _default_output_path(args.input)
    editor.save(output)
    print(f"Wrote updated PDF to {output}")
    editor.close()


def _default_output_path(input_path: str) -> str:
    path = Path(input_path)
    return str(path.with_name(f"{path.stem}_edited{path.suffix}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and edit PDFs while preserving span-level styles."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--input", required=True, help="Path to the source PDF.")
    shared.add_argument("--page", type=int, help="Zero-based page number to inspect.")
    shared.add_argument("--text", help="Literal text to search for.")
    shared.add_argument("--regex", help="Regex pattern to target spans.")
    shared.add_argument(
        "--bbox",
        nargs=4,
        metavar=("X0", "Y0", "X1", "Y1"),
        help="Bounding box coordinates for container targeting.",
    )
    shared.add_argument("--block-id", type=int, help="Exact block ID to match.")
    shared.add_argument(
        "--tolerance",
        type=float,
        default=1.5,
        help="Bounding box tolerance (in points).",
    )
    shared.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive text matching.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        parents=[shared],
        help="List matching containers and their styles.",
    )
    inspect_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of matches to print.",
    )
    inspect_parser.set_defaults(func=_cmd_inspect)

    replace_parser = subparsers.add_parser(
        "replace",
        parents=[shared],
        help="Replace matching text while preserving style.",
    )
    replace_parser.add_argument(
        "--replacement",
        required=True,
        help="Text that should replace the first match.",
    )
    replace_parser.add_argument(
        "--padding",
        type=float,
        default=0.75,
        help="Inset (points) applied before writing replacement text.",
    )
    replace_parser.add_argument(
        "--output",
        help="Destination PDF (defaults to *_edited.pdf next to input).",
    )
    replace_parser.set_defaults(func=_cmd_replace)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
