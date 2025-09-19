import argparse
from pypdf import PdfReader

def main(pdf_in):
    r = PdfReader(pdf_in)
    fields = r.get_fields()
    for k, v in sorted((fields or {}).items()):
        print(k)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get fields from a PDF")
    parser.add_argument("pdf_in", help="Blank PDF file")

    args = parser.parse_args()
    main(args.pdf_in)