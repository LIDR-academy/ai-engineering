from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 260


def tiny_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
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


def ensure_pdf() -> Path:
    existing = Path("atlas_scope.pdf")
    if existing.exists():
        return existing

    generated = Path("/tmp/atlas_scope_live_smoke.pdf")
    generated.write_bytes(
        tiny_pdf_bytes("Use Stripe Billing, HubSpot integration, and admin approval workflow.")
    )
    return generated


def create_session() -> str:
    response = requests.post(f"{BASE_URL}/sessions", timeout=20)
    response.raise_for_status()
    return response.json()["session_id"]


def estimate(session_id: str, prompt_version: str, transcript: str, pdf: Path | None = None) -> dict:
    data = {
        "transcript": transcript,
        "project_type": "internal_tool",
        "detail_level": "summary",
        "output_format": "narrative",
        "tier": "flash",
        "prompt_version": prompt_version,
    }

    files = None
    opened = None

    try:
        if pdf is not None:
            opened = pdf.open("rb")
            files = {"attachments": (pdf.name, opened, "application/pdf")}

        try:
            response = requests.post(
                f"{BASE_URL}/sessions/{session_id}/estimate",
                data=data,
                files=files,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.exceptions.ReadTimeout as exc:
            return {
                "status_code": None,
                "ok": False,
                "body": {
                    "detail": f"Client timed out after {TIMEOUT_SECONDS}s",
                    "exception": repr(exc),
                },
            }
        except requests.exceptions.RequestException as exc:
            return {
                "status_code": None,
                "ok": False,
                "body": {
                    "detail": "HTTP request failed",
                    "exception": repr(exc),
                },
            }

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:1000]}

        return {
            "status_code": response.status_code,
            "ok": response.status_code == 200,
            "body": body,
        }
    finally:
        if opened is not None:
            opened.close()


def main() -> int:
    pdf = ensure_pdf()

    turns = [
        (
            "turn1",
            "Project: Atlas CRM. Build a FastAPI and PostgreSQL onboarding platform with role based admin approval for a team of 3 engineers.",
            None,
        ),
        (
            "turn2",
            "Keep the same Atlas CRM project. Add reporting dashboards for operations managers and keep authentication in scope.",
            None,
        ),
        (
            "turn3_pdf",
            "Based on the existing Atlas CRM scope, estimate the extra work from the uploaded PDF and mention whether Stripe Billing and HubSpot change the risk profile.",
            pdf,
        ),
    ]

    report = []

    for prompt_version in ("v1", "v2"):
        session_id = create_session()
        print(f"\n=== flash {prompt_version} session {session_id} ===")

        version_report = {
            "prompt_version": prompt_version,
            "tier": "flash",
            "session_id": session_id,
            "turns": [],
        }

        for name, transcript, maybe_pdf in turns:
            result = estimate(session_id, prompt_version, transcript, maybe_pdf)
            body = result["body"] if isinstance(result["body"], dict) else {}

            turn_report = {
                "name": name,
                "status_code": result["status_code"],
                "ok": result["ok"],
                "detail": body.get("detail"),
                "project_name": (body.get("project_metadata") or {}).get("project_name"),
                "attachments_seen": (body.get("project_metadata") or {}).get("attachments_seen"),
                "history_turns": body.get("history_turns"),
            }

            print(json.dumps(turn_report, ensure_ascii=False))
            version_report["turns"].append(turn_report)

            if not result["ok"]:
                break

        report.append(version_report)

    Path("/tmp/session05_flash_matrix.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    all_ok = all(
        len(version["turns"]) == 3 and all(turn["ok"] for turn in version["turns"])
        for version in report
    )

    print("\nReport: /tmp/session05_flash_matrix.json")

    if not all_ok:
        print("FAIL: flash v1 or flash v2 workflow is still broken.")
        return 1

    print("PASS: flash v1 and flash v2 both passed memory plus PDF workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
