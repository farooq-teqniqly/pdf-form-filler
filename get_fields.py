"""Utility script to extract and list field names from PDF forms."""

import argparse
from pypdf import PdfReader

def main(pdf_in):
    """Extract and print all field names from a PDF form.

    Args:
        pdf_in (str): Path to the input PDF file.
    """
    r = PdfReader(pdf_in)
    fields = r.get_fields()
    for k, v in sorted((fields or {}).items()):
        print(k)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get fields from a PDF")
    parser.add_argument("pdf_in", help="Blank PDF file")

    args = parser.parse_args()
    main(args.pdf_in)
