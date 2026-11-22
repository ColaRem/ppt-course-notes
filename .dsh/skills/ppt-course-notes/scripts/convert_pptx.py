#!/usr/bin/env python3
"""Convert a .pptx deck to PDF for the image mode of ppt-course-notes.

This script only wraps LibreOffice (`soffice --headless --convert-to pdf`).
Hosts that provide their own Office conversion tool (for example DSH's
office_convert) may use that instead.

Usage:
  python convert_pptx.py deck.pptx -o work/vision/source.pdf
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

COMMON_SOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/snap/bin/libreoffice",
]


def find_soffice() -> str | None:
    for name in ("soffice", "soffice.exe", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in COMMON_SOFFICE_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 LibreOffice 把 PPTX 转成 PDF")
    parser.add_argument("input", help=".pptx 文件路径")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="输出 PDF 路径（默认与输入同目录同名 .pdf）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="转换超时秒数（默认 180）",
    )
    args = parser.parse_args(argv)

    source = Path(args.input)
    if not source.is_file():
        print(f"[error] 文件不存在：{source}", file=sys.stderr)
        return 2
    if source.suffix.lower() != ".pptx":
        print(f"[error] 仅支持 .pptx：{source.suffix or '(无扩展名)'}", file=sys.stderr)
        return 2

    soffice = find_soffice()
    if not soffice:
        print(
            "[error] 未找到 LibreOffice（soffice）。请安装 LibreOffice，"
            "或使用宿主提供的 Office 转换工具；没有转换工具时请走文本模式。",
            file=sys.stderr,
        )
        return 2

    output = Path(args.output) if args.output else source.with_suffix(".pdf")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ppt-course-notes-") as tmp:
        command = [
            soffice,
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp,
            str(source),
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired:
            print("[error] LibreOffice 转换超时", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"[error] 无法启动 LibreOffice：{exc}", file=sys.stderr)
            return 2

        produced = Path(tmp) / f"{source.stem}.pdf"
        if not produced.is_file():
            pdfs = sorted(Path(tmp).glob("*.pdf"))
            if len(pdfs) == 1:
                produced = pdfs[0]
            else:
                detail = (result.stderr or result.stdout or "").strip()[:600]
                print(f"[error] 转换失败：{detail}", file=sys.stderr)
                return 2

        try:
            os.replace(produced, output)
        except OSError as exc:
            print(f"[error] 无法写入输出文件：{exc}", file=sys.stderr)
            return 2

    try:
        header = output.read_bytes()[:5]
    except OSError as exc:
        print(f"[error] 无法读取输出文件：{exc}", file=sys.stderr)
        return 2
    if header != b"%PDF-":
        print("[error] 输出不是有效 PDF", file=sys.stderr)
        return 2

    print(f"OK {source.name} -> {output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
