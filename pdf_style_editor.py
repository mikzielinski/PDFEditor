#!/usr/bin/env python3
"""PDF style-preserving text editor backed by PyMuPDF.

This utility offers two sub-commands:

inspect
    Extracts structured information about each page, listing blocks, lines,
    spans, and their associated style metadata (font, size, color, flags,
    bounding boxes). The output helps discover the "containers" that hold a
    piece of content, making it easier to target replacements.

replace
    Applies a list of operations defined in a JSON file. Each operation can
    target content via an exact text match, a container identifier reported by
    the inspector, or an explicit bounding box. The tool redacts the original
    region and inserts the replacement text using the captured style (or the
    user-provided overrides) so that the new content blends in with the
    surrounding layout.

Example operations file::

    [
      {
        "page": 0,
        "selector": {"type": "text", "query": "Draft", "occurrence": 0},
        "replacement": "Final",
        "align": "center"
      },
      {
        "page": 1,
        "selector": {"type": "container", "id": "1:3:0"},
        "replacement": "Updated table heading"
      }
    ]

Limitations:
    * Text matches are resolved within individual spans; multi-span phrases may
      require the bounding-box or container selector.
    * Using the exact embedded font depends on whether the font is accessible
      to PyMuPDF. If it is not, the tool falls back to Helvetica while keeping
      the original size and color.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import fitz  # PyMuPDF
except ModuleNotFoundError as exc:  # pragma: no cover - guarded at runtime
    raise SystemExit(
        "PyMuPDF (package 'pymupdf') is required. Install it with `pip install pymupdf`."
    ) from exc


LOGGER = logging.getLogger("pdf-style-editor")

Alignment = int
Color = Tuple[float, float, float]


def _default_color() -> Color:
    return (0.0, 0.0, 0.0)


def _normalize_color(raw: Any) -> Color:
    """Convert various color representations to float RGB tuples."""
    if raw is None:
        return _default_color()

    if isinstance(raw, (list, tuple)):
        vals = list(raw[:3])
        if any(v > 1 for v in vals):
            vals = [v / 255.0 for v in vals]
        return tuple(vals)  # type: ignore[return-value]

    if isinstance(raw, (int, float)):
        value = int(raw)
        return (
            ((value >> 16) & 0xFF) / 255.0,
            ((value >> 8) & 0xFF) / 255.0,
            (value & 0xFF) / 255.0,
        )

    raise TypeError(f"Unsupported color format: {raw!r}")


def _rect_from_bbox(bbox: Sequence[float], inflate: float = 0.0) -> fitz.Rect:
    rect = fitz.Rect(*bbox)
    if inflate:
        rect = rect + (-inflate, -inflate, inflate, inflate)
    return rect


def _align_value(name: str) -> Alignment:
    mapping = {
        "left": fitz.TEXT_ALIGN_LEFT,
        "right": fitz.TEXT_ALIGN_RIGHT,
        "center": fitz.TEXT_ALIGN_CENTER,
        "justify": fitz.TEXT_ALIGN_JUSTIFY,
    }
    try:
        return mapping[name.lower()]
    except KeyError as err:
        raise ValueError(f"Unsupported alignment '{name}'.") from err


@dataclass
class TextStyle:
    font: str = "helv"
    fontsize: float = 11.0
    color: Color = _default_color()
    flags: int = 0

    def override(self, overrides: Optional[Dict[str, Any]]) -> "TextStyle":
        if not overrides:
            return self
        new_style = self
        if "font" in overrides:
            new_style = replace(new_style, font=overrides["font"])
        if "fontsize" in overrides:
            new_style = replace(new_style, fontsize=float(overrides["fontsize"]))
        if "color" in overrides:
            new_style = replace(new_style, color=_normalize_color(overrides["color"]))
        return new_style

    def as_json(self) -> Dict[str, Any]:
        return {
            "font": self.font,
            "fontsize": self.fontsize,
            "color": list(self.color),
            "flags": self.flags,
        }


def _style_from_span(span: Dict[str, Any]) -> TextStyle:
    return TextStyle(
        font=span.get("font", "helv"),
        fontsize=float(span.get("size", 11.0)),
        color=_normalize_color(span.get("color")),
        flags=int(span.get("flags", 0)),
    )


def _style_from_block(block: Dict[str, Any]) -> TextStyle:
    if block.get("type") != 0:
        return TextStyle()
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            return _style_from_span(span)
    return TextStyle()


def _style_from_line(line: Dict[str, Any]) -> TextStyle:
    for span in line.get("spans", []):
        return _style_from_span(span)
    return TextStyle()


def _first_span_text(block: Dict[str, Any]) -> str:
    if block.get("type") != 0:
        return ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            return span.get("text", "")
    return ""


def _ensure_page_index(doc: fitz.Document, page_index: int) -> None:
    if page_index < 0 or page_index >= len(doc):
        raise ValueError(f"Page index {page_index} is out of range (0..{len(doc) - 1}).")


class PDFStyleEditor:
    def __init__(self, pdf_path: Path):
        self._path = Path(pdf_path)
        self.doc = fitz.open(str(self._path))

    def close(self) -> None:
        self.doc.close()

    def __enter__(self) -> "PDFStyleEditor":  # pragma: no cover - convenience
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()

    # ------------------------------------------------------------------ inspect
    def inspect(self, pages: Optional[Sequence[int]] = None) -> List[Dict[str, Any]]:
        indices = pages if pages else range(len(self.doc))
        payload: List[Dict[str, Any]] = []
        for page_index in indices:
            _ensure_page_index(self.doc, page_index)
            page = self.doc.load_page(page_index)
            page_dict = page.get_text("dict")
            page_payload: Dict[str, Any] = {
                "page": page_index,
                "width": page.rect.width,
                "height": page.rect.height,
                "blocks": [],
            }
            for block_index, block in enumerate(page_dict.get("blocks", [])):
                block_payload: Dict[str, Any] = {
                    "id": f"{page_index}:{block_index}",
                    "type": "text" if block.get("type") == 0 else "non-text",
                    "bbox": list(block.get("bbox", [])),
                    "text_sample": _first_span_text(block),
                }
                if block.get("type") == 0:
                    lines_out = []
                    for line_index, line in enumerate(block.get("lines", [])):
                        spans_out = []
                        for span_index, span in enumerate(line.get("spans", [])):
                            spans_out.append(
                                {
                                    "id": f"{page_index}:{block_index}:{line_index}:{span_index}",
                                    "text": span.get("text", ""),
                                    "bbox": list(span.get("bbox", [])),
                                    "style": _style_from_span(span).as_json(),
                                }
                            )
                        lines_out.append(
                            {
                                "id": f"{page_index}:{block_index}:{line_index}",
                                "bbox": list(line.get("bbox", [])),
                                "spans": spans_out,
                            }
                        )
                    block_payload["lines"] = lines_out
                page_payload["blocks"].append(block_payload)
            payload.append(page_payload)
        return payload

    # ------------------------------------------------------------------ replace
    def apply_operations(self, operations: Iterable[Dict[str, Any]]) -> None:
        for op_index, operation in enumerate(operations):
            LOGGER.info("Applying operation %s", op_index)
            self._apply_operation(operation, op_index)

    def save(self, output_path: Path, *, incremental: bool = False) -> None:
        kwargs = {"incremental": incremental} if incremental else {}
        self.doc.save(str(output_path), **kwargs)

    # ------------------------------------------------------------------ helpers
    def _apply_operation(self, operation: Dict[str, Any], op_index: int) -> None:
        required_fields = ("page", "selector", "replacement")
        for field in required_fields:
            if field not in operation:
                raise ValueError(f"Operation {op_index} missing '{field}'.")

        page_index = int(operation["page"])
        _ensure_page_index(self.doc, page_index)
        page = self.doc.load_page(page_index)
        selector = operation["selector"]
        page_dict = page.get_text("dict")

        rect, inferred_style = self._resolve_selector(
            page_index, selector, page, page_dict
        )
        overrides = operation.get("style")
        style = inferred_style.override(overrides) if overrides else inferred_style

        align = _align_value(operation.get("align", "left"))
        replacement = str(operation["replacement"])

        keep_background = bool(operation.get("keep_background", False))
        if not keep_background:
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        LOGGER.debug(
            "Inserting text at page %s rect %s with style %s", page_index, rect, style
        )
        page.insert_textbox(
            rect,
            replacement,
            fontname=style.font,
            fontsize=style.fontsize,
            color=style.color,
            align=align,
        )

    def _resolve_selector(
        self,
        page_index: int,
        selector: Dict[str, Any],
        page: fitz.Page,
        page_dict: Dict[str, Any],
    ) -> Tuple[fitz.Rect, TextStyle]:
        selector_type = selector.get("type")
        if selector_type == "text":
            return self._selector_text(page_index, selector, page, page_dict)
        if selector_type == "bbox":
            return self._selector_bbox(selector, page_dict)
        if selector_type == "container":
            return self._selector_container(page_index, selector, page_dict)
        raise ValueError(f"Unsupported selector type '{selector_type}'.")

    def _selector_text(
        self,
        page_index: int,
        selector: Dict[str, Any],
        page: fitz.Page,
        page_dict: Dict[str, Any],
    ) -> Tuple[fitz.Rect, TextStyle]:
        query = selector.get("query")
        if not query:
            raise ValueError("Text selector requires a 'query'.")
        occurrence = int(selector.get("occurrence", 0))
        hit_max = int(selector.get("hit_max", 256))
        flags = fitz.TEXT_DEHYPHENATE
        if not selector.get("match_case", True):
            flags |= fitz.TEXT_IGNORE_CASE
        rects = page.search_for(query, hit_max=hit_max, flags=flags)
        if not rects:
            raise ValueError(f"Text '{query}' not found on page {page_index}.")
        if occurrence >= len(rects):
            raise ValueError(
                f"Occurrence {occurrence} for text '{query}' not found "
                f"(only {len(rects)} matches)."
            )
        rect = rects[occurrence]
        style = self._style_for_occurrence(page_dict, query, occurrence)
        return rect, style

    def _selector_bbox(
        self, selector: Dict[str, Any], page_dict: Dict[str, Any]
    ) -> Tuple[fitz.Rect, TextStyle]:
        bbox = selector.get("bbox")
        if not bbox or len(bbox) != 4:
            raise ValueError("BBox selector requires a four-value 'bbox'.")
        inflate = float(selector.get("inflate", 0.0))
        rect = _rect_from_bbox(bbox, inflate=inflate)
        style_hint = selector.get("style")
        blocks = page_dict.get("blocks", []) if page_dict else []
        style_source = blocks[0] if blocks else {}
        style = _style_from_block(style_source) if style_source else TextStyle()
        return rect, style.override(style_hint)

    def _selector_container(
        self,
        page_index: int,
        selector: Dict[str, Any],
        page_dict: Dict[str, Any],
    ) -> Tuple[fitz.Rect, TextStyle]:
        container_id = selector.get("id")
        if not container_id:
            raise ValueError("Container selector requires an 'id'.")
        parts = container_id.split(":")
        if len(parts) < 2:
            raise ValueError(
                "Container id must follow 'page:block[:line[:span]]' pattern."
            )
        container_page = int(parts[0])
        if container_page != page_index:
            raise ValueError(
                f"Container page {container_page} does not match target page {page_index}."
            )
        block_index = int(parts[1])
        blocks = page_dict.get("blocks", [])
        if block_index >= len(blocks):
            raise ValueError(f"Block {block_index} not found on page {page_index}.")
        block = blocks[block_index]
        rect = fitz.Rect(*block.get("bbox", [0, 0, 0, 0]))
        style = _style_from_block(block)
        if len(parts) >= 3:
            line_index = int(parts[2])
            lines = block.get("lines", [])
            if line_index >= len(lines):
                raise ValueError(
                    f"Line {line_index} not found in block {block_index} on page {page_index}."
                )
            line = lines[line_index]
            rect = fitz.Rect(*line.get("bbox", rect))
            style = _style_from_line(line)
        if len(parts) == 4:
            span_index = int(parts[3])
            spans = line.get("spans", [])
            if span_index >= len(spans):
                raise ValueError(
                    f"Span {span_index} not found in line {line_index} of block {block_index}."
                )
            span = spans[span_index]
            rect = fitz.Rect(*span.get("bbox", rect))
            style = _style_from_span(span)
        if len(parts) > 4:
            raise ValueError("Container id supports up to span granularity.")
        return rect, style

    def _style_for_occurrence(
        self, page_dict: Dict[str, Any], query: str, occurrence: int
    ) -> TextStyle:
        seen = 0
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if query in span.get("text", ""):
                        if seen == occurrence:
                            return _style_from_span(span)
                        seen += 1
        LOGGER.warning(
            "Style for occurrence %s of '%s' not found; using default.",
            occurrence,
            query,
        )
        return TextStyle()


def _load_operations(path: Path) -> List[Dict[str, Any]]:
    content = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(content, dict) and "operations" in content:
        operations = content["operations"]
    else:
        operations = content
    if not isinstance(operations, list):
        raise ValueError("Operations must be a list.")
    return operations


def _handle_inspect(args: argparse.Namespace) -> None:
    with PDFStyleEditor(Path(args.pdf)) as editor:
        pages = args.pages if args.pages else None
        payload = editor.inspect(pages=pages)
    output = {
        "pdf": str(args.pdf),
        "page_count": len(payload),
        "pages": payload,
    }
    serialized = json.dumps(output, indent=2)
    if args.out:
        Path(args.out).write_text(serialized, encoding="utf-8")
        LOGGER.info("Inspection data written to %s", args.out)
    else:
        print(serialized)


def _handle_replace(args: argparse.Namespace) -> None:
    operations = _load_operations(Path(args.ops))
    with PDFStyleEditor(Path(args.pdf)) as editor:
        editor.apply_operations(operations)
        if args.dry_run:
            LOGGER.info("Dry run complete; no file written.")
            return
        editor.save(Path(args.output))
        LOGGER.info("Modified PDF saved to %s", args.output)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and edit PDF content while preserving typographic style."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Dump detailed style and container metadata."
    )
    inspect_parser.add_argument("pdf", help="Path to the PDF to inspect.")
    inspect_parser.add_argument(
        "--pages",
        type=int,
        nargs="+",
        help="Optional list of page indices to inspect. Defaults to all pages.",
    )
    inspect_parser.add_argument(
        "--out",
        type=Path,
        help="Optional path to write the JSON output. Defaults to stdout.",
    )
    inspect_parser.set_defaults(func=_handle_inspect)

    replace_parser = subparsers.add_parser(
        "replace", help="Apply replacement operations defined in a JSON file."
    )
    replace_parser.add_argument("pdf", help="Path to the PDF to modify.")
    replace_parser.add_argument(
        "--ops",
        required=True,
        help="Path to a JSON file describing the operations to apply.",
    )
    replace_parser.add_argument(
        "--output",
        required=True,
        help="Path to write the modified PDF.",
    )
    replace_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the operations without writing an output file.",
    )
    replace_parser.set_defaults(func=_handle_replace)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except Exception as exc:
        LOGGER.error("%s", exc)
        raise
