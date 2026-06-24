from io import BytesIO

import pytest
from docx import Document
from fastapi import UploadFile

from app.services.attachments import extract_upload_text, format_attachments_for_prompt


def make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.anyio
async def test_docx_attachment_extraction_and_prompt_formatting():
    upload = UploadFile(filename="spec.docx", file=BytesIO(make_docx_bytes("Use HubSpot CRM integration.")))
    attachment = await extract_upload_text(upload)
    formatted = format_attachments_for_prompt([attachment])
    assert attachment.filename == "spec.docx"
    assert "HubSpot CRM integration" in attachment.text
    assert "--- attachment: spec.docx ---" in formatted
    assert "--- end attachment: spec.docx ---" in formatted


def test_prompt_formatter_uses_clear_delimiters():
    formatted = format_attachments_for_prompt([])
    assert formatted == ""
