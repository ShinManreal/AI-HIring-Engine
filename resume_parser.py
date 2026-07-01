import os


def extract_text_from_pdf(file_path):
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

        return "\n".join(text_parts).strip()

    except Exception as error:
        return f"No readable resume text could be extracted from PDF. Error: {error}"


def extract_text_from_docx(file_path):
    try:
        import docx

        document = docx.Document(file_path)
        text_parts = []

        for paragraph in document.paragraphs:
            text_parts.append(paragraph.text)

        return "\n".join(text_parts).strip()

    except Exception as error:
        return f"No readable resume text could be extracted from DOCX. Error: {error}"


def extract_text_from_txt(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return file.read().strip()

    except Exception as error:
        return f"No readable resume text could be extracted from TXT. Error: {error}"


def extract_text_from_image(file_path):
    try:
        from PIL import Image
        import pytesseract

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        return text.strip()

    except Exception as error:
        return f"""
No readable resume text could be extracted from image resume.

Possible reason:
PNG/JPG OCR needs Pillow, pytesseract, and system Tesseract installed.

Error:
{error}
"""


def extract_resume_text(file_path, file_type=None):
    if not file_path:
        return ""

    if not os.path.exists(file_path):
        return "No readable resume text could be extracted because the file path does not exist."

    if file_type is None:
        file_type = file_path.split(".")[-1].lower()

    file_type = str(file_type).lower().replace(".", "").strip()

    if file_type == "pdf":
        return extract_text_from_pdf(file_path)

    if file_type == "docx":
        return extract_text_from_docx(file_path)

    if file_type == "txt":
        return extract_text_from_txt(file_path)

    if file_type in ["png", "jpg", "jpeg"]:
        return extract_text_from_image(file_path)

    return f"Unsupported resume file type: {file_type}"