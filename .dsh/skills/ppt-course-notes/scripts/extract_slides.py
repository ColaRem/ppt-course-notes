#!/usr/bin/env python3
"""Extract slide text from a .pptx or .pdf deck for the ppt-course-notes skill.

Output JSON:
  {
    "file": "...", "file_name": "...", "source_type": "pptx" | "pdf",
    "title": "<file stem>", "deck_title": "...", "slide_count": N,
    "scanned": false, "warnings": ["..."],
    "slides": [{"index": 1, "title": "...", "text": "...", "notes": "...", "images": 0}]
  }

PPTX prefers python-pptx and falls back to reading the OOXML zip directly.
PDF prefers pdfplumber and falls back to PyMuPDF. Image-only decks are reported
with `scanned: true` instead of inventing content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A = "{%s}" % A_NS
MAX_SLIDES = 300
MAX_TEXT = 6000
MAX_NOTES = 2000


def normalize(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)] + "\n...[内容过长已截断]"


# ---------------------------------------------------------------------------
# PPTX


def _parse_pptx_with_python_pptx(path: Path) -> list[dict[str, Any]]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

    title_types = {
        PP_PLACEHOLDER.TITLE,
        PP_PLACEHOLDER.CENTER_TITLE,
        PP_PLACEHOLDER.SUBTITLE,
    }
    presentation = Presentation(str(path))
    slides: list[dict[str, Any]] = []

    for index, slide in enumerate(presentation.slides, start=1):
        if index > MAX_SLIDES:
            break
        title_lines: list[str] = []
        body_lines: list[str] = []
        image_count = 0

        def walk(shapes) -> None:
            nonlocal image_count
            for shape in shapes:
                try:
                    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                        walk(shape.shapes)
                        continue
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        image_count += 1
                        continue
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            cells = [_cell_text(cell) for cell in row.cells]
                            if any(cells):
                                body_lines.append(" | ".join(cells))
                        continue
                    if not getattr(shape, "has_text_frame", False):
                        continue
                    is_title = False
                    try:
                        is_title = bool(
                            shape.is_placeholder
                            and shape.placeholder_format.type in title_types
                        )
                    except Exception:
                        is_title = False
                    target = title_lines if is_title else body_lines
                    for paragraph in shape.text_frame.paragraphs:
                        text = "".join(run.text for run in paragraph.runs).strip()
                        if text:
                            target.append(text)
                except Exception:
                    continue

        walk(slide.shapes)

        if title_lines:
            title = title_lines[0]
        elif body_lines:
            title = body_lines.pop(0)
        else:
            title = f"第 {index} 页"

        notes = ""
        try:
            if slide.has_notes_slide:
                notes = normalize(slide.notes_slide.notes_text_frame.text)
        except Exception:
            notes = ""

        slides.append(
            {
                "index": index,
                "title": title.strip(),
                "text": clip(normalize("\n".join(body_lines)), MAX_TEXT),
                "notes": clip(notes, MAX_NOTES),
                "images": image_count,
            }
        )
    return slides


def _cell_text(cell) -> str:
    try:
        return normalize(cell.text).replace("\n", " ").strip()
    except Exception:
        return ""


def _parse_pptx_from_zip(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "ppt/presentation.xml" not in names:
            raise ValueError("不是有效的 PPTX：缺少 presentation.xml")
        slide_names = [
            name
            for name in names
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        ]
        slide_names.sort(key=lambda name: int(re.search(r"\d+", name).group(0)))
        slides: list[dict[str, Any]] = []
        for index, name in enumerate(slide_names[:MAX_SLIDES], start=1):
            root = ET.fromstring(archive.read(name))
            texts = [
                (node.text or "").strip()
                for node in root.iter(A + "t")
                if (node.text or "").strip()
            ]
            title = texts[0] if texts else f"第 {index} 页"
            body = "\n".join(texts[1:]) if len(texts) > 1 else ""
            notes = ""
            note_name = f"ppt/notesSlides/notesSlide{index}.xml"
            if note_name in names:
                try:
                    note_root = ET.fromstring(archive.read(note_name))
                    notes = "\n".join(
                        (node.text or "").strip()
                        for node in note_root.iter(A + "t")
                        if (node.text or "").strip()
                    )
                except Exception:
                    notes = ""
            slides.append(
                {
                    "index": index,
                    "title": normalize(title),
                    "text": clip(normalize(body), MAX_TEXT),
                    "notes": clip(normalize(notes), MAX_NOTES),
                    "images": 0,
                }
            )
        return slides


def parse_pptx(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        return _parse_pptx_with_python_pptx(path), "python-pptx"
    except ImportError:
        return _parse_pptx_from_zip(path), "ooxml"
    except Exception as exc:
        # A malformed file should fail clearly; only a missing dependency falls back.
        if "No module named" in str(exc):
            return _parse_pptx_from_zip(path), "ooxml"
        raise


# ---------------------------------------------------------------------------
# PDF


def _pdf_pages_with_pdfplumber(path: Path) -> tuple[list[str], int]:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages[:MAX_SLIDES]:
            try:
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            except Exception:
                text = ""
            pages.append(normalize(text))
    return pages, total


def _pdf_pages_with_pymupdf(path: Path) -> tuple[list[str], int]:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore

    document = fitz.open(str(path))
    try:
        total = len(document)
        pages = [
            normalize(document.load_page(index).get_text("text"))
            for index in range(min(total, MAX_SLIDES))
        ]
    finally:
        document.close()
    return pages, total


def parse_pdf(path: Path) -> tuple[list[dict[str, Any]], str]:
    pages: list[str] = []
    total = 0
    engine = ""
    try:
        pages, total = _pdf_pages_with_pdfplumber(path)
        engine = "pdfplumber"
    except ImportError:
        pages = []
    except Exception:
        # A broken/encrypted PDF may fail in pdfplumber; try PyMuPDF below.
        pages = []
    if not pages or sum(len(page) for page in pages) < max(80, len(pages) * 40):
        try:
            alt_pages, alt_total = _pdf_pages_with_pymupdf(path)
        except ImportError:
            alt_pages, alt_total = [], 0
        if sum(len(page) for page in alt_pages) > sum(len(page) for page in pages):
            pages, total, engine = alt_pages, alt_total, "pymupdf"
    if not pages:
        raise SystemExit(
            "[error] 无法读取 PDF：请先安装 pdfplumber 或 PyMuPDF（pip install pdfplumber）"
        )

    slides: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        if lines and len(lines[0]) <= 80:
            title = lines[0].lstrip("#").strip()
            body = "\n".join(lines[1:])
        else:
            title = ""
            body = page
        slides.append(
            {
                "index": index,
                "title": normalize(title) or f"第 {index} 页",
                "text": clip(normalize(body), MAX_TEXT),
                "notes": "",
                "images": 0,
            }
        )
    return slides, engine


# ---------------------------------------------------------------------------


def build_result(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    warnings: list[str] = []
    if suffix == ".ppt":
        raise SystemExit("[error] 不支持旧版 .ppt，请先另存为 .pptx")
    if suffix == ".pptx":
        slides, engine = parse_pptx(path)
        source_type = "pptx"
    elif suffix == ".pdf":
        slides, engine = parse_pdf(path)
        source_type = "pdf"
    else:
        raise SystemExit(f"[error] 不支持的文件类型：{suffix or '(无扩展名)'}，仅支持 .pptx / .pdf")

    if not slides:
        raise SystemExit("[error] 文件里没有解析出任何幻灯片/页面")

    text_chars = sum(len((slide["text"] or "").strip()) for slide in slides)
    empty = sum(1 for slide in slides if not (slide["text"] or "").strip())
    scanned = text_chars < max(80, len(slides) * 20)
    if scanned:
        warnings.append(
            "几乎没有可提取文字，可能是扫描件/图片版；请先 OCR 或提供可复制文字的 PDF。"
        )
    elif empty > len(slides) * 0.6:
        warnings.append(
            f"{empty}/{len(slides)} 页没有文字，可能以图片为主；图片中的内容未包含在资料里。"
        )
    else:
        image_only = [
            slide
            for slide in slides
            if slide.get("images") and len((slide.get("text") or "").strip()) < 20
        ]
        if image_only:
            warnings.append(
                f"{len(image_only)} 页以图片为主、文字很少；图片中的文字未提取，"
                "若考点在图中请提供可复制文字的版本。"
            )

    deck_title = slides[0]["title"] if slides else path.stem
    return {
        "file": str(path.resolve()),
        "file_name": path.name,
        "source_type": source_type,
        "title": path.stem,
        "deck_title": deck_title,
        "engine": engine,
        "slide_count": len(slides),
        "text_chars": text_chars,
        "scanned": scanned,
        "warnings": warnings,
        "slides": slides,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抽取 PPTX/PDF 幻灯片文本")
    parser.add_argument("path", help="课件路径（.pptx 或 .pdf）")
    parser.add_argument("-o", "--output", default="slides.json", help="输出 JSON 路径")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.is_file():
        print(f"[error] 文件不存在：{path}", file=sys.stderr)
        return 2

    try:
        result = build_result(path)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[error] 解析失败：{exc}", file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    warning = f" | 警告：{len(result['warnings'])} 条" if result["warnings"] else ""
    print(
        f"OK {result['file_name']} | {result['source_type']} | "
        f"{result['slide_count']} 页 | {result['text_chars']} 字 | {result['engine']}{warning}"
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())