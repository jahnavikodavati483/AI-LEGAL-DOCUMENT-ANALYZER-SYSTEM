import os
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract

# Set path for Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class DocumentReader:
    def _init_(self, input_folder, output_folder):
        self.input_folder = input_folder
        self.output_folder = output_folder

    def is_scanned_pdf(self, file_path):
        """Check if the PDF is scanned (no readable text)."""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                if page.extract_text():
                    return False
            return True
        except:
            return True

    def extract_text(self, file_name):
        """Extract text from PDF (OCR if needed)."""
        file_path = os.path.join(self.input_folder, file_name)
        output_path = os.path.join(self.output_folder, file_name.replace('.pdf', '.txt'))

        if self.is_scanned_pdf(file_path):
            print(f"🔍 {file_name} is a scanned document — Using OCR...")
            text = self.extract_text_with_ocr(file_path)
        else:
            print(f"📄 {file_name} is digital — Extracting text directly...")
            text = self.extract_text_from_pdf(file_path)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✅ Text saved to: {output_path}\n")

    def extract_text_from_pdf(self, file_path):
        """Extract text from digital PDF."""
        text = ""
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    def extract_text_with_ocr(self, file_path):
        """Extract text using OCR from scanned PDF."""
        text = ""
        images = convert_from_path(file_path, 300)
        for i, img in enumerate(images):
            print(f"🖼 OCR processing page {i + 1}...")
            text += pytesseract.image_to_string(img)
        return text


if __name__ == "_main_":
    input_folder = "../data/raw documents"
    output_folder = "../data/extracted text"

    os.makedirs(output_folder, exist_ok=True)
    reader = DocumentReader(input_folder, output_folder)

    for file in os.listdir(input_folder):
        if file.endswith(".pdf"):
            reader.extract_text(file)
