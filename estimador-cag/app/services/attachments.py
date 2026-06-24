from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import UploadFile
from pypdf import PdfReader

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_PROMPT_CHARS = 8_000
SUPPORTED_SUFFIXES = {".pdf", ".docx"}


class AttachmentExtractionError(ValueError):
    """Raised when an uploaded file cannot be used as estimation context."""


@dataclass(frozen=True)
class ExtractedAttachment:
    filename: str
    text: str


def _suffix_for(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def _reject_unsupported(filename: str | None) -> None:
    suffix = _suffix_for(filename)
    if suffix not in SUPPORTED_SUFFIXES:
        raise AttachmentExtractionError(
            f"Unsupported attachment type for {filename}. Supported: .pdf, .docx"
        )


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    content = await upload.read()
    if len(content) > MAX_FILE_BYTES:
        raise AttachmentExtractionError(
            f"Attachment {upload.filename} is too large. Max size is {MAX_FILE_BYTES} bytes."
        )
    return content


def _extract_pdf_text(content: bytes, filename: str) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise AttachmentExtractionError(f"Could not extract PDF text from {filename}") from exc

    text = "\n\n".join(page for page in pages if page)
    if not text:
        raise AttachmentExtractionError(f"No extractable text found in {filename}")
    return text


def _extract_docx_text(content: bytes, filename: str) -> str:
    try:
        document = Document(BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    except Exception as exc:
        raise AttachmentExtractionError(f"Could not extract DOCX text from {filename}") from exc

    text = "\n".join(paragraphs)
    if not text:
        raise AttachmentExtractionError(f"No extractable text found in {filename}")
    return text


async def extract_upload_text(upload: UploadFile) -> ExtractedAttachment:
    filename = upload.filename or "attachment"
    _reject_unsupported(filename)

    content = await _read_upload_bytes(upload)
    suffix = _suffix_for(filename)

    if suffix == ".pdf":
        text = _extract_pdf_text(content, filename)
    elif suffix == ".docx":
        text = _extract_docx_text(content, filename)
    else:
        raise AttachmentExtractionError(f"Unsupported attachment type for {filename}")

    return ExtractedAttachment(filename=filename, text=text)


async def extract_uploads_text(uploads: list[UploadFile] | None) -> list[ExtractedAttachment]:
    if not uploads:
        return []
    return [await extract_upload_text(upload) for upload in uploads]


def format_attachments_for_prompt(attachments: list[ExtractedAttachment | dict]) -> str:
    if not attachments:
        return ""

    blocks: list[str] = []
    for attachment in attachments:
        if isinstance(attachment, dict):
            filename = str(attachment.get("filename", "attachment"))
            text = str(attachment.get("text", ""))
        else:
            filename = attachment.filename
            text = attachment.text

        truncated = len(text) > MAX_ATTACHMENT_PROMPT_CHARS
        if truncated:
            text = text[:MAX_ATTACHMENT_PROMPT_CHARS]

        suffix = "\n[truncated attachment text]" if truncated else ""
        blocks.append(
            f"--- attachment: {filename} ---\n"
            f"{text}{suffix}\n"
            f"--- end attachment: {filename} ---"
        )

    return "\n\n".join(blocks)
