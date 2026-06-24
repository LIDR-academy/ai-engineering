from io import BytesIO

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services.attachments import extract_upload_text
from app.services.sessions import global_session_store


def tiny_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length "
        + str(len(stream)).encode("ascii")
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


@pytest.mark.anyio
async def test_pdf_attachment_extraction_reads_real_pdf_text():
    upload = UploadFile(
        filename="scope.pdf",
        file=BytesIO(tiny_pdf_bytes("Use Stripe Billing and HubSpot integration.")),
    )

    attachment = await extract_upload_text(upload)

    assert attachment.filename == "scope.pdf"
    assert "Stripe Billing" in attachment.text
    assert "HubSpot" in attachment.text


def setup_function():
    global_session_store.reset()


def test_pdf_attachment_text_reaches_session_estimation_context(monkeypatch):
    captured = {}

    def fake_estimate_product(request, **kwargs):
        captured["attachments_text"] = kwargs.get("attachments_text", "")
        return {
            "prompt_version": kwargs.get("prompt_version", "v1"),
            "text": "Estimate includes Stripe Billing and HubSpot integration.",
            "requested_tier": kwargs.get("tier") or "flash",
            "served_tier": kwargs.get("tier") or "flash",
            "fallback_used": False,
        }

    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)

    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": "Project: Atlas CRM. Build onboarding workflow."},
        files={
            "attachments": (
                "scope.pdf",
                tiny_pdf_bytes("Use Stripe Billing and HubSpot integration."),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert "--- attachment: scope.pdf ---" in captured["attachments_text"]
    assert "Stripe Billing" in captured["attachments_text"]
    assert "HubSpot" in captured["attachments_text"]
    assert "scope.pdf" in response.json()["project_metadata"]["attachments_seen"]
