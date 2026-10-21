import io
from typing import List
import PIL.Image


def convert_upload_to_images(
    file_bytes: bytes, filename: str, max_pages: int = None
) -> List[PIL.Image.Image]:
    """
    Convert an uploaded file (image or PDF) into a list of PIL Images.
    PDFs are split page-by-page up to max_pages. Images are returned as-is (in a list).
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return _pdf_to_images(file_bytes, max_pages=max_pages)
    else:
        # Treat as image
        img = PIL.Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return [img]


def _pdf_to_images(file_bytes: bytes, max_pages: int = None) -> List[PIL.Image.Image]:
    """Convert PDF bytes to a list of PIL Images using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        images = []
        for idx, page in enumerate(doc):
            if max_pages is not None and idx >= max_pages:
                break
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR quality
            pix = page.get_pixmap(matrix=mat)
            img = PIL.Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except Exception:
        # Fallback: return a blank image to avoid crashing
        img = PIL.Image.new("RGB", (800, 600), color="white")
        return [img]
