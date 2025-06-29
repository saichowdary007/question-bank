import fitz  # PyMuPDF

def extract_pages_from_pdf(file_path: str):
    doc = fitz.open(file_path)
    return [page.get_text().strip() for page in doc if page.get_text().strip()]