from io import BytesIO

import pytest
from fastapi import UploadFile

from app.services.attachments import extract_upload_text
from evals.stress.fixtures.build_pdfs import build_all_pdfs


def test_pdf_generator_creates_expected_files(tmp_path):
    paths = build_all_pdfs(sizes_kb=[5, 20], output_dir=tmp_path)
    assert set(paths) == {5, 20}
    for size_kb, path in paths.items():
        assert path.exists()
        assert path.stat().st_size >= size_kb * 1024
        assert path.read_bytes().startswith(b"%PDF")


@pytest.mark.anyio
async def test_attachment_extractor_reads_generated_pdf(tmp_path):
    path = build_all_pdfs(sizes_kb=[5], output_dir=tmp_path)[5]
    upload = UploadFile(filename=path.name, file=BytesIO(path.read_bytes()))
    attachment = await extract_upload_text(upload)
    assert "ATTACHMENT_FACT_5KB" in attachment.text
