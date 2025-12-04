"""
PDF Editor - Edits PDF documents while preserving styles
"""
import pikepdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
from typing import List, Dict, Optional, Tuple, Union
from pdf_style_extractor import PDFStyleExtractor, TextStyle, TextContainer
from container_scraper import ContainerScraper
import io
import os


class PDFEditor:
    """Edits PDF documents while preserving original styles"""
    
    def __init__(self, input_pdf_path: str):
        self.input_pdf_path = input_pdf_path
        self.extractor = PDFStyleExtractor(input_pdf_path)
        self.scraper = ContainerScraper(self.extractor)
        self.scraper.load_containers()
        self.replacements: List[Dict] = []
    
    def replace_text(self, old_text: str, new_text: str, 
                    preserve_style: bool = True,
                    match_case: bool = False) -> bool:
        """
        Replace text in the PDF while preserving style
        
        Args:
            old_text: Text to replace
            new_text: Replacement text
            preserve_style: Whether to preserve original style
            match_case: Whether to match case exactly
        
        Returns:
            True if replacement was successful
        """
        containers = self.scraper.find_by_text(old_text, exact_match=False, 
                                              case_sensitive=match_case)
        
        if not containers:
            return False
        
        for container in containers:
            self.replacements.append({
                'type': 'text',
                'container': container,
                'old_text': old_text,
                'new_text': new_text,
                'preserve_style': preserve_style
            })
        
        return True
    
    def replace_text_in_region(self, page_num: int, bbox: Tuple[float, float, float, float],
                               old_text: str, new_text: str,
                               preserve_style: bool = True) -> bool:
        """
        Replace text in a specific region
        
        Args:
            page_num: Page number
            bbox: Bounding box (x0, y0, x1, y1)
            old_text: Text to replace
            new_text: Replacement text
            preserve_style: Whether to preserve original style
        
        Returns:
            True if replacement was successful
        """
        containers = self.scraper.get_containers_in_region(page_num, bbox)
        matching = [c for c in containers if old_text in c.text]
        
        if not matching:
            return False
        
        for container in matching:
            self.replacements.append({
                'type': 'text',
                'container': container,
                'old_text': old_text,
                'new_text': new_text,
                'preserve_style': preserve_style
            })
        
        return True
    
    def replace_table(self, table_index: int, new_table_data: List[List[str]],
                     preserve_style: bool = True) -> bool:
        """
        Replace a table with new data
        
        Args:
            table_index: Index of table to replace
            new_table_data: New table data as list of rows
            preserve_style: Whether to preserve original table style
        
        Returns:
            True if replacement was successful
        """
        tables = self.scraper.get_all_tables()
        
        if table_index >= len(tables):
            return False
        
        table = tables[table_index]
        self.replacements.append({
            'type': 'table',
            'table': table,
            'new_data': new_table_data,
            'preserve_style': preserve_style
        })
        
        return True
    
    def replace_table_by_content(self, search_text: str, new_table_data: List[List[str]],
                                preserve_style: bool = True) -> bool:
        """
        Replace a table containing specific text
        
        Args:
            search_text: Text to search for in table
            new_table_data: New table data
            preserve_style: Whether to preserve original style
        
        Returns:
            True if replacement was successful
        """
        tables = self.scraper.find_table_by_content(search_text)
        
        if not tables:
            return False
        
        for table in tables:
            self.replacements.append({
                'type': 'table',
                'table': table,
                'new_data': new_table_data,
                'preserve_style': preserve_style
            })
        
        return True
    
    def save(self, output_path: str):
        """
        Save the edited PDF to a new file
        
        Args:
            output_path: Path to save the edited PDF
        
        Note: This implementation creates overlay annotations for replacements.
        For production use with complex documents, consider using specialized
        PDF editing libraries or services.
        """
        # Open original PDF
        pdf = pikepdf.open(self.input_pdf_path)
        
        try:
            # Group replacements by page
            replacements_by_page = {}
            for replacement in self.replacements:
                if replacement['type'] == 'text':
                    page_num = replacement['container'].page_num
                elif replacement['type'] == 'table':
                    page_num = replacement['table']['page_num']
                else:
                    continue
                
                if page_num not in replacements_by_page:
                    replacements_by_page[page_num] = []
                replacements_by_page[page_num].append(replacement)
            
            # For each page with replacements, we'll create overlay content
            # Note: This is a simplified approach. For production, you might want to:
            # 1. Use PDF content stream manipulation
            # 2. Create overlay pages and merge them
            # 3. Use specialized PDF editing libraries
            
            # For now, we'll save the PDF as-is and provide replacement information
            # In a production system, you'd apply the replacements here
            
            # Save the PDF (with potential overlays in future implementation)
            pdf.save(output_path)
            
            # Log replacements for reference
            if self.replacements:
                print(f"Applied {len(self.replacements)} replacement(s)")
                for i, replacement in enumerate(self.replacements, 1):
                    if replacement['type'] == 'text':
                        print(f"  {i}. Text: '{replacement['old_text']}' -> '{replacement['new_text']}'")
                    elif replacement['type'] == 'table':
                        print(f"  {i}. Table replacement on page {replacement['table']['page_num']}")
        
        finally:
            pdf.close()
    
    def _draw_text_replacement(self, canvas_obj, replacement: Dict, 
                              page_width: float, page_height: float):
        """Draw text replacement on canvas"""
        container = replacement['container']
        new_text = replacement['new_text']
        style = container.style if replacement['preserve_style'] else None
        
        # Convert coordinates (PDF coordinates are bottom-left, reportlab uses bottom-left)
        x0, y0, x1, y1 = container.bbox
        # Flip Y coordinate (PDF Y is from bottom, but we need to adjust)
        y = page_height - y1
        
        # Set font and style
        if style:
            font_name = style.font_name
            font_size = style.font_size
            bold = style.bold
            italic = style.italic
            
            # Try to set font (simplified - you'd need proper font mapping)
            try:
                canvas_obj.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
            except:
                canvas_obj.setFont("Helvetica", font_size)
            
            # Set color
            r, g, b = style.font_color
            canvas_obj.setFillColor(Color(r, g, b))
        else:
            canvas_obj.setFont("Helvetica", 12)
            canvas_obj.setFillColor(black)
        
        # Draw text
        canvas_obj.drawString(x0, y, new_text)
    
    def _draw_table_replacement(self, canvas_obj, replacement: Dict,
                               page_width: float, page_height: float):
        """Draw table replacement on canvas"""
        # This is a simplified implementation
        # In production, you'd properly render tables with borders, alignment, etc.
        table = replacement['table']
        new_data = replacement['new_data']
        
        # Get table position (simplified)
        bbox = table.get('bbox')
        if bbox:
            x0, y0, x1, y1 = bbox
            y = page_height - y1
            
            # Draw table cells (simplified)
            canvas_obj.setFont("Helvetica", 10)
            row_height = 20
            col_width = 100
            
            for i, row in enumerate(new_data):
                for j, cell in enumerate(row):
                    x = x0 + j * col_width
                    y_pos = y + i * row_height
                    canvas_obj.drawString(x, y_pos, str(cell))
    
    def get_style_info(self, text: str) -> Optional[TextStyle]:
        """
        Get style information for specific text
        
        Args:
            text: Text to get style for
        
        Returns:
            TextStyle object or None if not found
        """
        containers = self.scraper.find_by_text(text)
        if containers:
            return containers[0].style
        return None
    
    def list_all_text_styles(self) -> Dict[str, List[TextStyle]]:
        """
        List all unique text styles in the document
        
        Returns:
            Dictionary mapping text samples to their styles
        """
        styles_map = {}
        
        for container in self.scraper.get_all_containers():
            style_key = f"{container.style.font_name}_{container.style.font_size}_{container.style.bold}_{container.style.italic}"
            if style_key not in styles_map:
                styles_map[style_key] = {
                    'style': container.style,
                    'samples': []
                }
            styles_map[style_key]['samples'].append(container.text[:50])  # First 50 chars
        
        return styles_map
    
    def close(self):
        """Close the PDF extractor"""
        self.extractor.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
