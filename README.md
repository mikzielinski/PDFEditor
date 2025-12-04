# PDF Editor with Style Preservation

A Python program to edit PDF files by replacing text, tables, and other content while preserving the original font settings and styles.

## Features

- **Style Extraction**: Reads and extracts font settings (name, size, color, bold, italic) from PDF documents
- **Container Scraping**: Identifies and targets specific parts of documents (text blocks, tables, regions)
- **Style Preservation**: Maintains original formatting when replacing content
- **Flexible Targeting**: Find content by text, position, style, or regex patterns
- **Table Support**: Replace entire tables while preserving formatting

## Installation

1. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Components

### 1. PDFStyleExtractor (`pdf_style_extractor.py`)
Extracts style information from PDF documents:
- Font names, sizes, colors
- Bold/italic formatting
- Text positioning and bounding boxes
- Table extraction

### 2. ContainerScraper (`container_scraper.py`)
Identifies and targets specific document parts:
- Find text by content, regex, or position
- Find content by style criteria
- Extract tables
- Target specific regions on pages

### 3. PDFEditor (`pdf_editor.py`)
Main editor class that combines extraction and replacement:
- Replace text while preserving styles
- Replace tables
- Get style information
- List all unique styles in document

## Usage Examples

### Basic Text Replacement

```python
from pdf_editor import PDFEditor

# Create editor
editor = PDFEditor("input.pdf")

# Replace text (preserves original style)
editor.replace_text("Old Text", "New Text", preserve_style=True)

# Save edited PDF
editor.save("output.pdf")
editor.close()
```

### Replace Text in Specific Region

```python
editor = PDFEditor("input.pdf")

# Replace text in a bounding box on page 0
# bbox format: (x0, y0, x1, y1)
editor.replace_text_in_region(
    page_num=0,
    bbox=(100, 100, 500, 200),
    old_text="Date:",
    new_text="Date Updated:",
    preserve_style=True
)

editor.save("output.pdf")
editor.close()
```

### Extract Style Information

```python
from pdf_style_extractor import PDFStyleExtractor

extractor = PDFStyleExtractor("input.pdf")

# Get all text with styles
containers = extractor.extract_text_with_styles()

for container in containers[:5]:
    style = container.style
    print(f"Text: {container.text}")
    print(f"Font: {style.font_name}, Size: {style.font_size}")
    print(f"Bold: {style.bold}, Italic: {style.italic}")
    print(f"Color: RGB{style.font_color}")

extractor.close()
```

### Use Container Scraper

```python
from pdf_style_extractor import PDFStyleExtractor
from container_scraper import ContainerScraper

extractor = PDFStyleExtractor("input.pdf")
scraper = ContainerScraper(extractor)
scraper.load_containers()

# Find text by content
results = scraper.find_by_text("Invoice", exact_match=False)

# Find by style
bold_texts = scraper.find_by_style(bold=True)

# Find by regex
import re
emails = scraper.find_by_regex(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Find tables
tables = scraper.find_tables()

extractor.close()
```

### Replace Tables

```python
editor = PDFEditor("input.pdf")

# Replace first table
new_table_data = [
    ["Header1", "Header2", "Header3"],
    ["Row1Col1", "Row1Col2", "Row1Col3"],
    ["Row2Col1", "Row2Col2", "Row2Col3"],
]

editor.replace_table(0, new_table_data, preserve_style=True)
editor.save("output.pdf")
editor.close()
```

### Get Style for Specific Text

```python
editor = PDFEditor("input.pdf")

# Get style information
style = editor.get_style_info("Sample Text")
if style:
    print(f"Font: {style.font_name}")
    print(f"Size: {style.font_size}")
    print(f"Bold: {style.bold}")

# List all unique styles
styles_map = editor.list_all_text_styles()
for style_key, info in styles_map.items():
    print(f"Style: {info['style'].font_name} {info['style'].font_size}pt")

editor.close()
```

## API Reference

### PDFEditor

#### Methods

- `replace_text(old_text, new_text, preserve_style=True, match_case=False)`: Replace text in document
- `replace_text_in_region(page_num, bbox, old_text, new_text, preserve_style=True)`: Replace text in specific region
- `replace_table(table_index, new_table_data, preserve_style=True)`: Replace table by index
- `replace_table_by_content(search_text, new_table_data, preserve_style=True)`: Replace table containing text
- `get_style_info(text)`: Get style information for specific text
- `list_all_text_styles()`: List all unique text styles in document
- `save(output_path)`: Save edited PDF

### ContainerScraper

#### Methods

- `find_by_text(search_text, exact_match=False, case_sensitive=True)`: Find containers by text
- `find_by_regex(pattern, flags=0)`: Find containers by regex
- `find_by_position(bbox, tolerance=5.0)`: Find containers by position
- `find_by_style(font_name=None, font_size=None, bold=None, italic=None)`: Find by style
- `find_tables(page_num=None)`: Find tables
- `find_table_by_content(search_text)`: Find tables containing text
- `get_containers_in_region(page_num, bbox)`: Get containers in region

## Notes

- The current implementation provides style extraction and container identification
- PDF editing with full style preservation requires advanced PDF manipulation
- For production use with complex documents, consider using specialized PDF editing services or libraries
- The `save()` method currently preserves the original PDF structure; full replacement implementation may require additional PDF manipulation libraries

## Requirements

- Python 3.7+
- pdfplumber >= 0.10.0
- pikepdf >= 8.0.0
- reportlab >= 4.0.0
- Pillow >= 10.0.0
- pypdf >= 3.0.0

## License

This project is provided as-is for educational and development purposes.
