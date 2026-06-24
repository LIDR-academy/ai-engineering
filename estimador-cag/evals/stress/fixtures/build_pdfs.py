"""Generate deterministic synthetic PDF attachments for Session 06 stress tests.

The generator intentionally avoids external PDF-writing dependencies. It writes a
small standards-compliant text PDF that pypdf can extract, then calibrates the
payload length to approximate the requested sizes.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SIZES_KB = [5, 20, 50, 100]
GENERATED_DIR = Path(__file__).resolve().parent / "generated"


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _minimal_text_pdf_bytes(text: str) -> bytes:
    lines = [line[:100] for line in text.splitlines() if line.strip()]
    commands = ["BT", "/F1 9 Tf", "50 780 Td", "12 TL"]
    for line in lines:
        commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n% deterministic synthetic CAG stress PDF\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def build_pdf(*, size_kb: int, output_dir: Path = GENERATED_DIR) -> Path:
    """Create one deterministic PDF at approximately the requested size."""

    if size_kb <= 0:
        raise ValueError("Synthetic attachment size must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    fact = f"ATTACHMENT_FACT_{size_kb}KB"
    base_line = (
        f"{fact} synthetic requirements for the CAG stress runner. "
        "This document repeats deterministic scope notes about auth, audit, billing, "
        "exports, reporting, and compliance so extraction can be measured."
    )
    repetitions = max(4, (size_kb * 1024) // len(base_line))
    path = output_dir / f"attach_{size_kb}kb.pdf"

    while True:
        text = "\n".join(f"{base_line} line {index}." for index in range(repetitions))
        payload = _minimal_text_pdf_bytes(text)
        path.write_bytes(payload)
        if path.stat().st_size >= size_kb * 1024:
            return path
        repetitions = int(repetitions * 1.25) + 1


def build_all_pdfs(
    *,
    sizes_kb: list[int] | None = None,
    output_dir: Path = GENERATED_DIR,
) -> dict[int, Path]:
    """Create all requested synthetic PDFs and return a size-to-path mapping."""

    return {size: build_pdf(size_kb=size, output_dir=output_dir) for size in (sizes_kb or DEFAULT_SIZES_KB)}


if __name__ == "__main__":
    for size, path in build_all_pdfs().items():
        print(f"{size} KB -> {path} ({path.stat().st_size} bytes)")
