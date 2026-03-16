from datetime import datetime


def export(summary: str, source_filename: str) -> bytes:
    lines: list[str] = []

    if source_filename:
        lines.append(f"원본 파일: {source_filename}")
    lines.append(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("─" * 40)
    lines.append("")
    lines.append(summary)

    return "\n".join(lines).encode("utf-8")
