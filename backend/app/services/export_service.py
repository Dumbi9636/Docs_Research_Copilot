from app.services.exporters import txt_exporter, docx_exporter, pdf_exporter

# 지원 형식 → (exporter 모듈, MIME 타입, 파일 확장자)
# 새 형식을 추가할 때는 여기에만 항목을 추가하면 됩니다.
_EXPORTERS = {
    "txt": (txt_exporter, "text/plain; charset=utf-8", "txt"),
    "docx": (
        docx_exporter,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "pdf": (pdf_exporter, "application/pdf", "pdf"),
}


def export(summary: str, fmt: str, source_filename: str) -> tuple[bytes, str, str]:
    """
    Returns: (file_bytes, media_type, file_extension)
    Raises:
        ValueError: 지원하지 않는 형식
        RuntimeError: 파일 생성 실패 (exporter 내부 오류)
    """
    if fmt not in _EXPORTERS:
        raise ValueError(f"지원하지 않는 출력 형식입니다: {fmt}")

    exporter, media_type, ext = _EXPORTERS[fmt]
    file_bytes = exporter.export(summary, source_filename)
    return file_bytes, media_type, ext
