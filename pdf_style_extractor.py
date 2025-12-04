"""
PDF Style Extractor - Extracts font and style information from PDF documents
"""
import pdfplumber
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TextStyle:
    """Represents text style information"""
    font_name: str
    font_size: float
    font_color: Tuple[float, float, float]  # RGB values 0-1
    bold: bool = False
    italic: bool = False
    char_spacing: float = 0.0
    word_spacing: float = 0.0
    line_height: float = 1.0


@dataclass
class TextContainer:
    """Represents a text container with style and position"""
    text: str
    style: TextStyle
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int


class PDFStyleExtractor:
    """Extracts style information from PDF documents"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf = pdfplumber.open(pdf_path)
        self._style_cache: Dict[int, List[TextContainer]] = {}
    
    def extract_text_with_styles(self, page_num: Optional[int] = None) -> List[TextContainer]:
        """
        Extract text with style information from PDF
        
        Args:
            page_num: Specific page to extract (None for all pages)
        
        Returns:
            List of TextContainer objects with text and style info
        """
        if page_num is not None:
            return self._extract_page_styles(page_num)
        
        all_containers = []
        for page_idx in range(len(self.pdf.pages)):
            all_containers.extend(self._extract_page_styles(page_idx))
        
        return all_containers
    
    def _extract_page_styles(self, page_num: int) -> List[TextContainer]:
        """Extract styles from a specific page"""
        if page_num in self._style_cache:
            return self._style_cache[page_num]
        
        page = self.pdf.pages[page_num]
        containers = []
        
        # Extract characters with style information
        chars = page.chars
        
        # Group characters by style to form text runs
        current_run = []
        current_style = None
        
        for char in chars:
            # Extract style information
            style = TextStyle(
                font_name=char.get('fontname', 'Unknown'),
                font_size=char.get('size', 12.0),
                font_color=self._extract_color(char),
                bold='Bold' in char.get('fontname', ''),
                italic='Italic' in char.get('fontname', ''),
                char_spacing=char.get('adv', 0) - char.get('width', 0),
            )
            
            # Check if style changed
            if current_style is None or not self._styles_match(current_style, style):
                # Save previous run
                if current_run:
                    containers.append(self._create_container(current_run, current_style, page_num))
                
                # Start new run
                current_run = [char]
                current_style = style
            else:
                current_run.append(char)
        
        # Save last run
        if current_run:
            containers.append(self._create_container(current_run, current_style, page_num))
        
        self._style_cache[page_num] = containers
        return containers
    
    def _extract_color(self, char: Dict) -> Tuple[float, float, float]:
        """Extract RGB color from character"""
        # Try to get color from various possible fields
        if 'ncolor' in char:
            return tuple(char['ncolor'][:3]) if len(char['ncolor']) >= 3 else (0.0, 0.0, 0.0)
        elif 'stroking_color' in char:
            color = char['stroking_color']
            if isinstance(color, (list, tuple)) and len(color) >= 3:
                return tuple(color[:3])
        return (0.0, 0.0, 0.0)  # Default to black
    
    def _styles_match(self, style1: TextStyle, style2: TextStyle) -> bool:
        """Check if two styles match"""
        return (style1.font_name == style2.font_name and
                abs(style1.font_size - style2.font_size) < 0.1 and
                style1.bold == style2.bold and
                style1.italic == style2.italic)
    
    def _create_container(self, chars: List[Dict], style: TextStyle, page_num: int) -> TextContainer:
        """Create a TextContainer from a list of characters"""
        if not chars:
            return TextContainer("", style, (0, 0, 0, 0), page_num)
        
        text = ''.join(char.get('text', '') for char in chars)
        
        # Calculate bounding box
        x0 = min(char.get('x0', 0) for char in chars)
        y0 = min(char.get('y0', 0) for char in chars)
        x1 = max(char.get('x1', 0) for char in chars)
        y1 = max(char.get('y1', 0) for char in chars)
        
        return TextContainer(
            text=text,
            style=style,
            bbox=(x0, y0, x1, y1),
            page_num=page_num
        )
    
    def extract_tables(self, page_num: Optional[int] = None) -> List[Dict]:
        """
        Extract tables from PDF pages
        
        Args:
            page_num: Specific page to extract (None for all pages)
        
        Returns:
            List of table dictionaries with data and style info
        """
        tables = []
        pages = [self.pdf.pages[page_num]] if page_num is not None else self.pdf.pages
        
        for idx, page in enumerate(pages):
            page_tables = page.extract_tables()
            for table in page_tables:
                tables.append({
                    'data': table,
                    'page_num': page_num if page_num is not None else idx,
                    'bbox': page.bbox if hasattr(page, 'bbox') else None
                })
        
        return tables
    
    def get_page_dimensions(self, page_num: int) -> Tuple[float, float]:
        """Get page width and height"""
        page = self.pdf.pages[page_num]
        return (page.width, page.height)
    
    def close(self):
        """Close the PDF file"""
        if self.pdf:
            self.pdf.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
