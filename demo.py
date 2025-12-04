#!/usr/bin/env python3
"""
Quick demo script showing PDF editing capabilities
"""
import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python demo.py <input_pdf_path> [output_pdf_path]")
        print("\nExample:")
        print("  python demo.py document.pdf output.pdf")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else "output.pdf"
    
    if not os.path.exists(input_pdf):
        print(f"Error: File '{input_pdf}' not found")
        sys.exit(1)
    
    print(f"Processing PDF: {input_pdf}")
    print(f"Output will be saved to: {output_pdf}")
    print("-" * 50)
    
    try:
        from pdf_editor import PDFEditor
        from pdf_style_extractor import PDFStyleExtractor
        from container_scraper import ContainerScraper
        
        # Demonstrate style extraction
        print("\n1. Extracting style information...")
        extractor = PDFStyleExtractor(input_pdf)
        containers = extractor.extract_text_with_styles()
        print(f"   Found {len(containers)} text containers")
        
        if containers:
            print("\n   Sample styles found:")
            unique_styles = {}
            for container in containers[:20]:  # Check first 20
                style = container.style
                key = f"{style.font_name}_{style.font_size}_{style.bold}_{style.italic}"
                if key not in unique_styles:
                    unique_styles[key] = {
                        'style': style,
                        'sample': container.text[:30]
                    }
            
            for i, (key, info) in enumerate(list(unique_styles.items())[:5], 1):
                style = info['style']
                print(f"   {i}. Font: {style.font_name}, Size: {style.font_size}pt")
                print(f"      Bold: {style.bold}, Italic: {style.italic}")
                print(f"      Sample: {info['sample']}...")
        
        # Demonstrate container scraping
        print("\n2. Scraping containers...")
        scraper = ContainerScraper(extractor)
        scraper.load_containers()
        
        tables = scraper.find_tables()
        print(f"   Found {len(tables)} tables")
        
        # Show some container statistics
        all_containers = scraper.get_all_containers()
        if all_containers:
            bold_count = len(scraper.find_by_style(bold=True))
            italic_count = len(scraper.find_by_style(italic=True))
            print(f"   Bold text containers: {bold_count}")
            print(f"   Italic text containers: {italic_count}")
        
        extractor.close()
        
        # Demonstrate editing
        print("\n3. PDF Editor ready for modifications")
        print("   Use the PDFEditor class to make replacements:")
        print("   - editor.replace_text('old', 'new')")
        print("   - editor.replace_table(0, new_data)")
        print("   - editor.save('output.pdf')")
        
        print("\n" + "=" * 50)
        print("Demo completed successfully!")
        print("=" * 50)
        
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
