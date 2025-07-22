import fitz  # PyMuPDF

def extract_pages_from_pdf(file_path: str, batch_size: int = 3):
    doc = fitz.open(file_path)
    pages = [page.get_text().strip() for page in doc]  # extract all pages
    batches = []

    for i in range(0, len(pages), batch_size):
        chunk = pages[i : i + batch_size]
        # Optionally skip completely empty pages
        chunk = [text for text in chunk if text]
        combined = "\n\n".join(chunk)
        batches.append(combined)

    return batches