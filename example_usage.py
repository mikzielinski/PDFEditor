"""
Example usage of the PDF Editor
"""
from pdf_editor import PDFEditor
from pdf_style_extractor import PDFStyleExtractor
from container_scraper import ContainerScraper


def example_basic_text_replacement():
    """Example: Replace text while preserving style"""
    print("Example 1: Basic Text Replacement")
    print("-" * 50)
    
    # Create editor
    editor = PDFEditor("input.pdf")
    
    # Replace text (preserves original style)
    editor.replace_text("Old Text", "New Text", preserve_style=True)
    
    # Save edited PDF
    editor.save("output.pdf")
    editor.close()
    
    print("✓ Text replaced and saved to output.pdf\n")


def example_find_and_replace_specific_region():
    """Example: Replace text in a specific region"""
    print("Example 2: Replace Text in Specific Region")
    print("-" * 50)
    
    editor = PDFEditor("input.pdf")
    
    # Replace text in a specific bounding box on page 0
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
    
    print("✓ Text in region replaced\n")


def example_table_replacement():
    """Example: Replace a table"""
    print("Example 3: Table Replacement")
    print("-" * 50)
    
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
    
    print("✓ Table replaced\n")


def example_style_extraction():
    """Example: Extract and display style information"""
    print("Example 4: Style Extraction")
    print("-" * 50)
    
    extractor = PDFStyleExtractor("input.pdf")
    
    # Get all text with styles
    containers = extractor.extract_text_with_styles()
    
    print(f"Found {len(containers)} text containers")
    print("\nFirst 5 containers:")
    for i, container in enumerate(containers[:5]):
        style = container.style
        print(f"\nContainer {i+1}:")
        print(f"  Text: {container.text[:50]}...")
        print(f"  Font: {style.font_name}")
        print(f"  Size: {style.font_size}")
        print(f"  Bold: {style.bold}")
        print(f"  Italic: {style.italic}")
        print(f"  Color: RGB{style.font_color}")
        print(f"  Position: {container.bbox}")
    
    extractor.close()
    print("\n✓ Style information extracted\n")


def example_container_scraping():
    """Example: Use container scraper to find specific content"""
    print("Example 5: Container Scraping")
    print("-" * 50)
    
    extractor = PDFStyleExtractor("input.pdf")
    scraper = ContainerScraper(extractor)
    scraper.load_containers()
    
    # Find text by content
    results = scraper.find_by_text("Invoice", exact_match=False)
    print(f"Found {len(results)} containers containing 'Invoice'")
    
    # Find by style
    bold_texts = scraper.find_by_style(bold=True)
    print(f"Found {len(bold_texts)} containers with bold text")
    
    # Find by regex
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = scraper.find_by_regex(email_pattern)
    print(f"Found {len(emails)} potential email addresses")
    
    # Find tables
    tables = scraper.find_tables()
    print(f"Found {len(tables)} tables")
    
    extractor.close()
    print("\n✓ Container scraping completed\n")


def example_get_style_for_text():
    """Example: Get style information for specific text"""
    print("Example 6: Get Style for Specific Text")
    print("-" * 50)
    
    editor = PDFEditor("input.pdf")
    
    # Get style for a specific text
    style = editor.get_style_info("Sample Text")
    
    if style:
        print(f"Font Name: {style.font_name}")
        print(f"Font Size: {style.font_size}")
        print(f"Bold: {style.bold}")
        print(f"Italic: {style.italic}")
        print(f"Color: RGB{style.font_color}")
    else:
        print("Text not found")
    
    # List all unique styles
    print("\nAll unique styles in document:")
    styles_map = editor.list_all_text_styles()
    for style_key, info in list(styles_map.items())[:5]:
        style = info['style']
        print(f"\nStyle: {style.font_name} {style.font_size}pt")
        print(f"  Bold: {style.bold}, Italic: {style.italic}")
        print(f"  Sample texts: {info['samples'][:3]}")
    
    editor.close()
    print("\n✓ Style information retrieved\n")


if __name__ == "__main__":
    print("PDF Editor Examples")
    print("=" * 50)
    print("\nNote: Make sure you have an 'input.pdf' file in the current directory")
    print("=" * 50)
    print()
    
    # Uncomment the example you want to run:
    
    # example_basic_text_replacement()
    # example_find_and_replace_specific_region()
    # example_table_replacement()
    # example_style_extraction()
    # example_container_scraping()
    # example_get_style_for_text()
    
    print("Uncomment an example function above to run it!")
