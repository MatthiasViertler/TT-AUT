"""
Converts docs/kapitalertrag_documentation.md → docs/kapitalertrag_documentation.docx.
Run at major version bumps (e.g. v0.3 → v0.4) to keep the human-readable Word doc current.

Usage:
    python scripts/build_docs.py
"""
import re
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
except ImportError:
    raise SystemExit("python-docx not installed. Run: pip install python-docx")

SRC = Path(__file__).parent.parent / "docs" / "kapitalertrag_documentation.md"
DST = Path(__file__).parent.parent / "docs" / "kapitalertrag_documentation.docx"


def build() -> None:
    md = SRC.read_text(encoding="utf-8")
    doc = Document()

    for section in doc.sections:
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)

    in_code = False
    code_lines: list[str] = []

    def flush_code() -> None:
        if not code_lines:
            return
        p = doc.add_paragraph()
        run = p.add_run("\n".join(code_lines))
        run.font.name = "Courier New"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        p.paragraph_format.left_indent = Inches(0.3)

    def plain(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        return text

    for line in md.splitlines():
        if line.startswith("```"):
            if in_code:
                flush_code()
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        if line.startswith("#### "):
            doc.add_heading(plain(line[5:]), level=4)
        elif line.startswith("### "):
            doc.add_heading(plain(line[4:]), level=3)
        elif line.startswith("## "):
            doc.add_heading(plain(line[3:]), level=2)
        elif line.startswith("# "):
            doc.add_heading(plain(line[2:]), level=1)
        elif re.match(r"^---+$", line.strip()):
            pass
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.match(r"^[-:]+$", c.replace(" ", "")) for c in cells if c):
                continue
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            run = p.add_run("  |  ".join(c for c in cells if c))
            run.font.size = Pt(9)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(plain(line[2:]), style="List Bullet")
        elif not line.strip():
            pass
        else:
            text = plain(line)
            if text.strip():
                doc.add_paragraph(text)

    doc.save(DST)
    print(f"Written: {DST}")


if __name__ == "__main__":
    build()
