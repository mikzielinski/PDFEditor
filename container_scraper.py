"""
Container Scraper - Identifies and targets specific parts of PDF documents
"""
from typing import List, Dict, Optional, Callable, Tuple
from pdf_style_extractor import TextContainer, PDFStyleExtractor
import re


class ContainerScraper:
    """Scrapes and identifies containers (text blocks, tables) in PDF documents"""
    
    def __init__(self, style_extractor: PDFStyleExtractor):
        self.extractor = style_extractor
        self._containers: List[TextContainer] = []
        self._tables: List[Dict] = []
    
    def load_containers(self):
        """Load all containers from the PDF"""
        self._containers = self.extractor.extract_text_with_styles()
        self._tables = self.extractor.extract_tables()
    
    def find_by_text(self, search_text: str, exact_match: bool = False, 
                    case_sensitive: bool = True) -> List[TextContainer]:
        """
        Find containers containing specific text
        
        Args:
            search_text: Text to search for
            exact_match: If True, text must match exactly
            case_sensitive: If False, search is case-insensitive
        
        Returns:
            List of matching TextContainer objects
        """
        matches = []
        search_pattern = search_text if case_sensitive else search_text.lower()
        
        for container in self._containers:
            container_text = container.text if case_sensitive else container.text.lower()
            
            if exact_match:
                if container_text == search_pattern:
                    matches.append(container)
            else:
                if search_pattern in container_text:
                    matches.append(container)
        
        return matches
    
    def find_by_regex(self, pattern: str, flags: int = 0) -> List[TextContainer]:
        """
        Find containers matching a regex pattern
        
        Args:
            pattern: Regular expression pattern
            flags: Regex flags (e.g., re.IGNORECASE)
        
        Returns:
            List of matching TextContainer objects
        """
        matches = []
        regex = re.compile(pattern, flags)
        
        for container in self._containers:
            if regex.search(container.text):
                matches.append(container)
        
        return matches
    
    def find_by_position(self, bbox: Tuple[float, float, float, float], 
                        tolerance: float = 5.0) -> List[TextContainer]:
        """
        Find containers by position/bbox
        
        Args:
            bbox: (x0, y0, x1, y1) bounding box
            tolerance: Tolerance for position matching
        
        Returns:
            List of containers within the bbox
        """
        matches = []
        x0, y0, x1, y1 = bbox
        
        for container in self._containers:
            c_x0, c_y0, c_x1, c_y1 = container.bbox
            
            # Check if container overlaps with target bbox
            if (c_x1 >= x0 - tolerance and c_x0 <= x1 + tolerance and
                c_y1 >= y0 - tolerance and c_y0 <= y1 + tolerance):
                matches.append(container)
        
        return matches
    
    def find_by_style(self, font_name: Optional[str] = None,
                      font_size: Optional[float] = None,
                      bold: Optional[bool] = None,
                      italic: Optional[bool] = None) -> List[TextContainer]:
        """
        Find containers matching specific style criteria
        
        Args:
            font_name: Font name to match
            font_size: Font size to match
            bold: Bold style filter
            italic: Italic style filter
        
        Returns:
            List of matching containers
        """
        matches = []
        
        for container in self._containers:
            style = container.style
            
            match = True
            if font_name and style.font_name != font_name:
                match = False
            if font_size and abs(style.font_size - font_size) > 0.1:
                match = False
            if bold is not None and style.bold != bold:
                match = False
            if italic is not None and style.italic != italic:
                match = False
            
            if match:
                matches.append(container)
        
        return matches
    
    def find_tables(self, page_num: Optional[int] = None) -> List[Dict]:
        """
        Find tables in the document
        
        Args:
            page_num: Specific page number (None for all pages)
        
        Returns:
            List of table dictionaries
        """
        if page_num is not None:
            return [t for t in self._tables if t['page_num'] == page_num]
        return self._tables
    
    def find_table_by_content(self, search_text: str) -> List[Dict]:
        """
        Find tables containing specific text
        
        Args:
            search_text: Text to search for in table cells
        
        Returns:
            List of matching tables
        """
        matches = []
        
        for table in self._tables:
            for row in table.get('data', []):
                for cell in row:
                    if cell and search_text in str(cell):
                        matches.append(table)
                        break
                else:
                    continue
                break
        
        return matches
    
    def get_containers_in_region(self, page_num: int, 
                                 bbox: Tuple[float, float, float, float]) -> List[TextContainer]:
        """
        Get all containers in a specific region on a page
        
        Args:
            page_num: Page number
            bbox: Bounding box (x0, y0, x1, y1)
        
        Returns:
            List of containers in the region
        """
        return [c for c in self.find_by_position(bbox) if c.page_num == page_num]
    
    def get_all_containers(self) -> List[TextContainer]:
        """Get all loaded containers"""
        return self._containers
    
    def get_all_tables(self) -> List[Dict]:
        """Get all loaded tables"""
        return self._tables
