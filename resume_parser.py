from pypdf import PdfReader
from docx import Document


def extract_pdf_text(file_path):
    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text.strip()


def extract_docx_text(file_path):
    document = Document(file_path)
    text = ""

    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"

    return text.strip()


def extract_resume_text(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_text(file_path)

    if file_type == "docx":
        return extract_docx_text(file_path)

    if file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    return ""