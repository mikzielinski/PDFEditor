"""
Utilities for scraping PDF containers (text spans, table cells, etc.) and
performing style-aware replacements without sacrificing the original look.

The module uses PyMuPDF (fitz) to read the document structure, capture style
metadata, and write new content back into the same bounding boxes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple
import re

import fitz


Color = Tuple[float, float, float]
RectTuple = Tuple[float, float, float, float]


@dataclass(frozen=True)
class StyleSnapshot:
    """Captures the style of a PDF span so it can be re-used later."""

    font: str
    size: float
    color: Color
    bold: bool
    italic: bool


@dataclass(frozen=True)
class ContainerMatch:
    """Holds metadata for a matched PDF container/span."""

    page_number: int
    block_id: int
    line_id: int
    span_id: int
    text: str
    rect: RectTuple
    style: StyleSnapshot


@dataclass
class ContainerSelector:
    """
    Criteria used to target PDF containers.

    Attributes:
        page: zero-based page index to search, or None for all pages.
        text: literal text that must be contained inside the span.
        regex: pattern that must match the span's text content.
        bbox: bounding box (x0, y0, x1, y1) to match within a tolerance.
        block_id: block identifier to match from PyMuPDF's layout.
        tolerance: acceptable leeway in points when matching by bbox.
        case_sensitive: controls literal and regex comparisons.
    """

    page: Optional[int] = None
    text: Optional[str] = None
    regex: Optional[str] = None
    bbox: Optional[RectTuple] = None
    block_id: Optional[int] = None
    tolerance: float = 1.5
    case_sensitive: bool = False

    def compiled_regex(self) -> Optional[re.Pattern[str]]:
        if not self.regex:
            return None
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(self.regex, flags)


def _normalize_color(raw_color: object) -> Color:
    """
    PyMuPDF may return colors either as floats 0-1, ints 0-255, or tuples.
    Normalize everything to an RGB triple with floats between 0 and 1.
    """

    def _clamp(value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value

    if isinstance(raw_color, (list, tuple)):
        if len(raw_color) == 3:
            return tuple(_clamp(float(c) if c <= 1 else float(c) / 255.0) for c in raw_color)  # type: ignore[return-value]
        if len(raw_color) == 1:
            value = raw_color[0]
            normalized = _clamp(float(value) if value <= 1 else float(value) / 255.0)
            return (normalized, normalized, normalized)
    if isinstance(raw_color, (int, float)):
        value = float(raw_color)
        normalized = _clamp(value if value <= 1 else value / 255.0)
        return (normalized, normalized, normalized)
    # Fallback to black
    return (0.0, 0.0, 0.0)


def _rects_close(a: RectTuple, b: RectTuple, tolerance: float) -> bool:
    return all(abs(av - bv) <= tolerance for av, bv in zip(a, b))


class PDFContainerScraper:
    """Inspects a PDF document and yields individual spans with styling info."""

    def __init__(self, document: fitz.Document):
        self.document = document

    def iter_spans(self, page_index: Optional[int] = None) -> Iterator[ContainerMatch]:
        page_indices = range(len(self.document)) if page_index is None else [page_index]
        for page_number in page_indices:
            page = self.document[page_number]
            text_dict = page.get_text("dict")
            for block_id, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                for line_id, line in enumerate(block.get("lines", [])):
                    for span_id, span in enumerate(line.get("spans", [])):
                        style = StyleSnapshot(
                            font=span.get("font", "helv"),
                            size=float(span.get("size", 12)),
                            color=_normalize_color(span.get("color", 0)),
                            bold=bool(span.get("flags", 0) & 2),  # PyMuPDF flag bit for bold
                            italic=bool(span.get("flags", 0) & 1),
                        )
                        rect = tuple(span.get("bbox"))  # type: ignore[arg-type]
                        yield ContainerMatch(
                            page_number=page_number,
                            block_id=block_id,
                            line_id=line_id,
                            span_id=span_id,
                            text=span.get("text", ""),
                            rect=rect,  # type: ignore[arg-type]
                            style=style,
                        )

    def find(self, selector: ContainerSelector) -> List[ContainerMatch]:
        matches: List[ContainerMatch] = []
        regex = selector.compiled_regex()
        for match in self.iter_spans(selector.page):
            if selector.block_id is not None and match.block_id != selector.block_id:
                continue
            if selector.text is not None:
                haystack = match.text if selector.case_sensitive else match.text.lower()
                needle = selector.text if selector.case_sensitive else selector.text.lower()
                if needle not in haystack:
                    continue
            if regex and not regex.search(match.text):
                continue
            if selector.bbox and not _rects_close(match.rect, selector.bbox, selector.tolerance):
                continue
            matches.append(match)
        return matches


class PDFStyleAwareEditor:
    """High-level API for replacing PDF content while preserving styles."""

    def __init__(self, input_path: str):
        self.document = fitz.open(input_path)
        self.scraper = PDFContainerScraper(self.document)
        self._known_fonts = self._collect_fonts()

    def _collect_fonts(self) -> Sequence[str]:
        collected = []
        for font_info in self.document.get_fonts():
            name = font_info[3]  # 4th entry is font name
            if name not in collected:
                collected.append(name)
        return collected

    def _ensure_font(self, font_name: str) -> str:
        if font_name in self._known_fonts:
            return font_name
        # Fallback to default Helvetica if the original font is not embedded
        return "helv"

    def replace_text(
        self,
        selector: ContainerSelector,
        replacement: str,
        *,
        align: int = fitz.TEXT_ALIGN_LEFT,
        padding: float = 1.0,
        stroke: Optional[Color] = None,
    ) -> ContainerMatch:
        """
        Replace the first container matching the selector with new text
        rendered using the old span's style metadata.
        """

        matches = self.scraper.find(selector)
        if not matches:
            raise ValueError("No containers matched the given selector.")
        target = matches[0]
        page = self.document[target.page_number]
        rect = fitz.Rect(target.rect)
        rect.x0 += padding
        rect.y0 += padding
        rect.x1 -= padding
        rect.y1 -= padding
        self._clear_region(page, rect)
        self._write_text(
            page,
            rect,
            replacement,
            target.style,
            align=align,
            stroke=stroke,
        )
        return target

    def replace_region(
        self,
        page_number: int,
        rect: RectTuple,
        text: str,
        style: StyleSnapshot,
        *,
        align: int = fitz.TEXT_ALIGN_LEFT,
    ) -> None:
        """
        Replace any content inside the provided rectangle using the supplied
        style. This helper is useful for table cells where the bounding box
        is known ahead of time.
        """

        page = self.document[page_number]
        fitz_rect = fitz.Rect(rect)
        self._clear_region(page, fitz_rect)
        self._write_text(page, fitz_rect, text, style, align=align)

    def save(self, output_path: str) -> None:
        self.document.save(output_path)

    def close(self) -> None:
        self.document.close()

    def _clear_region(self, page: fitz.Page, rect: fitz.Rect) -> None:
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=None, fill=(1, 1, 1), fill_opacity=1)
        shape.commit()

    def _write_text(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        style: StyleSnapshot,
        *,
        align: int,
        stroke: Optional[Color],
    ) -> None:
        font_name = self._ensure_font(style.font)
        color = style.color
        if stroke is None:
            stroke = color
        result = page.insert_textbox(
            rect,
            text,
            fontname=font_name,
            fontsize=style.size,
            fontfile=None,
            color=color,
            stroke_color=stroke,
            align=align,
        )
        if result == 0:
            raise ValueError(
                "Replacement text did not fit inside the container. "
                "Increase the rectangle or provide shorter content."
            )
