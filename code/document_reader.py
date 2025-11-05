import os
from pathlib import Path
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract

# Set path for Tesseract OCR (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class DocumentReader:
    def _init_(self):
        # Base paths
        self.base_dir = Path(_file_).resolve().parent        # code/
        self.repo_root = self.base_dir.parent                  # project root
        self.input_folder = self.repo_root / "data" / "raw documents"
        self.output_folder = self.repo_root / "data" / "extracted text"

        # Ensure folders exist
        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def is_scanned_pdf(self, file_path):
        """Check if the PDF is scanned (no readable text)."""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                if page.extract_text():
                    return False
            return True
        except Exception:
            # Some PDFs cause PyPDF2 errors → assume scanned
            return True

    def extract_text(self, file_name):
        """Extract text from PDF (auto detects digital vs scanned)."""
        file_path = self.input_folder / file_name
        output_path = self.output_folder / file_name.replace(".pdf", ".txt")

        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return

        try:
            if self.is_scanned_pdf(file_path):
                print(f"🔍 {file_name} is scanned — Using OCR...")
                text = self.extract_text_with_ocr(file_path)
            else:
                print(f"📄 {file_name} is digital — Extracting text directly...")
                text = self.extract_text_from_pdf(file_path)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"✅ Text saved to: {output_path}\n")

        except Exception as e:
            print(f"⚠ Error extracting {file_name}: {e}")

    def extract_text_from_pdf(self, file_path):
        """Extract text from digital PDF (non-scanned)."""
        text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        except Exception as e:
            print(f"❌ Failed to extract digital text: {e}")
        return text

    def extract_text_with_ocr(self, file_path):
        """Extract text using OCR from scanned PDF."""
        text = ""
        try:
            images = convert_from_path(file_path, 300)
            for i, img in enumerate(images):
                print(f"🖼 OCR processing page {i + 1}...")
                text += pytesseract.image_to_string(img)
        except Exception as e:
            print(f"❌ OCR failed (Poppler not found or corrupted PDF): {e}")
            print("➡ Install Poppler for OCR or use digital PDFs.")
        return text


if __name__ == "_main_":
    # Run this file directly for batch extraction
    reader = DocumentReader()
    print("📂 Starting batch extraction...\n")

    for file in os.listdir(reader.input_folder):
        if file.endswith(".pdf"):
            reader.extract_text(file)

    print("✅ All files processed successfully!")
