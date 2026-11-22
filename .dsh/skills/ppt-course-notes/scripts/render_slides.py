#!/usr/bin/env python3
"""Render PDF pages into labeled contact sheets for multimodal analysis.

PPTX is intentionally not rendered here: convert it to PDF first with
LibreOffice (scripts/convert_pptx.py) or a host-provided Office converter,
then run this script on the PDF.

Output:
  work/vision/sheets.json
  work/vision/sheet-01.png, sheet-02.png, ...

Each sheet holds up to `--per-sheet` pages (default 4, 2x2), with a "P<n>"
label on every tile so the model can cite the slide/page number.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

MAX_PAGES = 300
PAD = 14
LABEL_H = 40


def load_imaging():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            "[error] 需要 Pillow：pip install pillow"
        ) from exc
    return Image, ImageDraw, ImageFont


def load_pymupdf():
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "[error] 需要 PyMuPDF：pip install pymupdf"
            ) from exc
    return fitz


def page_font(ImageFont, size: int):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def render(
    input_path: Path, outdir: Path, per_sheet: int, width: int, max_pages: int
) -> dict:
    Image, ImageDraw, ImageFont = load_imaging()
    fitz = load_pymupdf()

    suffix = input_path.suffix.lower()
    if suffix == ".pptx":
        raise SystemExit(
            "[error] 不直接渲染 PPTX：请先用 LibreOffice（convert_pptx.py）"
            "或宿主的 Office 转换工具转成 PDF，再对 PDF 运行本脚本。"
        )
    if suffix != ".pdf":
        raise SystemExit(f"[error] 仅支持 .pdf：{input_path.suffix or '(无扩展名)'}")

    document = fitz.open(str(input_path))
    try:
        total_pages = len(document)
        page_count = min(total_pages, max(1, max_pages))
        if total_pages <= 0:
            raise SystemExit("[error] PDF 没有页面")

        per_sheet = max(1, min(6, per_sheet))
        cols = 2 if per_sheet > 1 else 1
        rows = max(1, math.ceil(per_sheet / cols))
        tile_w = max(640, width)
        tile_h = int(tile_w * 9 / 16)
        sheet_w = cols * tile_w
        sheet_h = rows * tile_h
        font = page_font(ImageFont, max(18, tile_w // 50))

        outdir.mkdir(parents=True, exist_ok=True)
        pages_payload = []
        for page_index in range(page_count):
            page = document.load_page(page_index)
            rect = page.rect
            fit = min(
                (tile_w - 2 * PAD) / max(rect.width, 1),
                (tile_h - LABEL_H - 2 * PAD) / max(rect.height, 1),
            )
            matrix = fitz.Matrix(fit * 1.6, fit * 1.6)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes(
                "RGB", (pixmap.width, pixmap.height), pixmap.samples
            )
            image.thumbnail((tile_w - 2 * PAD, tile_h - LABEL_H - 2 * PAD), Image.LANCZOS)
            pages_payload.append(image)
    finally:
        document.close()

    sheets = []
    for sheet_index in range(0, len(pages_payload), per_sheet):
        group = pages_payload[sheet_index : sheet_index + per_sheet]
        sheet = Image.new("RGB", (sheet_w, sheet_h), "#e7e2d8")
        draw = ImageDraw.Draw(sheet)
        for offset, image in enumerate(group):
            column = offset % cols
            row = offset // cols
            header_top = row * tile_h
            draw.rectangle(
                (
                    column * tile_w,
                    header_top,
                    (column + 1) * tile_w,
                    header_top + LABEL_H,
                ),
                fill="#1f2a24",
            )
            page_no = sheet_index + offset + 1
            draw.text(
                (column * tile_w + 12, header_top + 7),
                f"P{page_no}",
                fill="#ffffff",
                font=font,
            )
            left = column * tile_w + (tile_w - image.width) // 2
            top = header_top + LABEL_H + (tile_h - LABEL_H - image.height) // 2
            sheet.paste(image, (left, top))

        sheet_path = outdir / f"sheet-{len(sheets) + 1:02d}.png"
        sheet.save(sheet_path, format="PNG")
        pages = list(range(sheet_index + 1, sheet_index + len(group) + 1))
        sheets.append(
            {
                "index": len(sheets) + 1,
                "pages": pages,
                "file": sheet_path.name,
                "width": sheet_w,
                "height": sheet_h,
            }
        )

    payload = {
        "source": str(input_path.resolve()),
        "source_type": "pdf",
        "total_pages": total_pages,
        "page_count": page_count,
        "per_sheet": per_sheet,
        "tile_width": tile_w,
        "tile_height": tile_h,
        "sheet_width": sheet_w,
        "sheet_height": sheet_h,
        "sheets": sheets,
    }
    (outdir / "sheets.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 PDF 页面渲染成带页码的拼图")
    parser.add_argument(
        "input", nargs="?", help="PDF 路径（PPTX 请先转 PDF；--probe-only 时可省略）"
    )
    parser.add_argument("--outdir", default="work/vision", help="输出目录")
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="只生成一张能力探测图 probe.png，不读取 PDF",
    )
    parser.add_argument(
        "--per-sheet",
        type=int,
        default=4,
        help="每张拼图包含的页数（1-6，默认 4；文字密集建议 2）",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="单个页面的拼图宽度（默认 1280）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help="最多渲染多少页；先用 4 做能力探测，再全量渲染",
    )
    args = parser.parse_args(argv)

    if args.probe_only:
        Image, ImageDraw, ImageFont = load_imaging()
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (640, 360), "#f6f4ee")
        draw = ImageDraw.Draw(image)
        draw.text(
            (24, 24),
            "VISION PROBE",
            fill="#1f2a24",
            font=page_font(ImageFont, 32),
        )
        probe = outdir / "probe.png"
        image.save(probe, format="PNG")
        print(f"OK 能力探测图：{probe.resolve()}")
        return 0

    if not args.input:
        parser.error("需要 PDF 路径（或使用 --probe-only）")

    path = Path(args.input)
    if not path.is_file():
        print(f"[error] 文件不存在：{path}", file=sys.stderr)
        return 2

    try:
        payload = render(
            path, Path(args.outdir), args.per_sheet, args.width, args.max_pages
        )
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[error] 渲染失败：{exc}", file=sys.stderr)
        return 2

    print(
        f"OK {path.name} | 共 {payload['total_pages']} 页 | "
        f"渲染 {payload['page_count']} 页 | {len(payload['sheets'])} 张拼图 | "
        f"{Path(args.outdir).resolve()}"
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())