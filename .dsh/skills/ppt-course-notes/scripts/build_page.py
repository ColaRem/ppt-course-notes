#!/usr/bin/env python3
"""Merge chunk analyses and render a self-contained HTML study page.

Usage:
  python build_page.py --slides work/slides.json --chunks work/chunks -o "第3章-学习资料.html"

The output is a self-contained course-notes page: paper background, white cards,
teal accent, amber stars, collapsible chapter, per-point exercises with hidden
answers, and a mind-map tab.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"

IRRELEVANT = re.compile(
    r"(课程(概况|简介|导入|目标|安排|大纲|考核|要求|介绍)|课程导论|考核方式|学时|学分|"
    r"成绩|评分|群昵称|群号|参考教材|学习(方法|建议)|科研(入门|方法)|论文(检索|阅读|写作)|"
    r"就业|面试|致谢)"
)
QUESTION_PREFIX = re.compile(r"^\s*\*\*【([^】]+)】\*\*\s*")
GENERIC_STEM = re.compile(
    r"^(course|deck|ppt|pptx|presentation|slides?|demo|sample|test|"
    r"演示文稿|未命名|新建|文档|课件|幻灯片)([-_ ]?[a-z0-9]*)?$",
    re.IGNORECASE,
)
INLINE = re.compile(
    r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)]+\))"
)


# ---------------------------------------------------------------------------
# Normalization


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit]


def stars(value: Any) -> int:
    if isinstance(value, bool):
        return 3
    if isinstance(value, (int, float)):
        number = int(value)
    else:
        raw = str(value or "").strip().lower()
        if raw in {"core", "high", "key", "important", "must"}:
            number = 5
        elif raw in {"normal", "medium"}:
            number = 3
        elif raw in {"low", "easy", "optional"}:
            number = 2
        else:
            try:
                number = int(float(raw))
            except (TypeError, ValueError):
                number = 3
    return min(5, max(1, number))


def norm_title(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())


def strip_leading_heading(markdown: str, title: str) -> str:
    lines = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        match = re.match(r"^#{1,4}\s+(.*)$", lines[index])
        if match:
            heading = match.group(1).strip()
            if not title or heading == title or heading in title or title in heading:
                lines.pop(index)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


def normalize_examples(raw_examples: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_examples or []:
        if not isinstance(raw, dict):
            continue
        question = str(raw.get("question_md") or raw.get("question") or "").strip()
        answer = str(raw.get("answer_md") or raw.get("answer") or "").strip()
        if not question or not answer:
            continue
        key = re.sub(r"\s+", "", question)[:160]
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "question_md": question,
                "answer_md": answer,
                "difficulty": clip(str(raw.get("difficulty") or "基础").strip(), 20)
                or "基础",
            }
        )
        if len(result) >= 4:
            break
    return result


def merge_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    points: list[dict[str, Any]] = []
    index_by_title: dict[str, int] = {}
    dropped = 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        for raw in chunk.get("knowledge_points") or []:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            content = str(raw.get("content_md") or raw.get("content") or "").strip()
            if not title or not content:
                continue
            if IRRELEVANT.search(title):
                dropped += 1
                continue
            examples = normalize_examples(raw.get("examples"))
            importance = stars(raw.get("importance"))
            key = norm_title(title)
            if key and key in index_by_title:
                existing = points[index_by_title[key]]
                if len(content) > len(existing["content_md"]):
                    existing["content_md"] = content
                existing["importance"] = max(existing["importance"], importance)
                existing["examples"] = normalize_examples(
                    existing["examples"] + examples
                )
                continue
            index_by_title[key] = len(points)
            points.append(
                {
                    "title": title,
                    "content_md": content,
                    "importance": importance,
                    "examples": examples,
                }
            )
    return points[:60], dropped


def chunk_title_summary(points: list[dict[str, Any]]) -> str:
    if not points:
        return ""
    titles = "、".join(point["title"] for point in points[:6])
    return f"本章共 {len(points)} 个考点：{titles}。"


# ---------------------------------------------------------------------------
# Markdown -> HTML (small renderer for the page subset)


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def safe_url(url: str) -> str:
    value = (url or "").strip()
    if re.match(r"^(https?://|mailto:)", value, re.IGNORECASE):
        return value
    return "#"


def inline(text: str) -> str:
    result: list[str] = []
    last = 0
    for match in INLINE.finditer(text):
        result.append(esc(text[last : match.start()]))
        token = match.group(0)
        if token.startswith("**") or token.startswith("__"):
            result.append(f"<strong>{esc(token[2:-2])}</strong>")
        elif token.startswith("`"):
            result.append(f"<code class=\"md-inline-code\">{esc(token[1:-1])}</code>")
        elif token.startswith("["):
            link = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", token)
            if link:
                result.append(
                    f'<a class="md-link" href="{esc(safe_url(link.group(2)))}" '
                    f'target="_blank" rel="noreferrer">{esc(link.group(1))}</a>'
                )
            else:
                result.append(esc(token))
        else:
            result.append(f"<em>{esc(token[1:-1])}</em>")
        last = match.end()
    result.append(esc(text[last:]))
    return "".join(result)


def render_table(lines: list[str]) -> str:
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.match(r"^:?-{2,}:?$", cell) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    head, *body = rows
    head_html = "".join(f"<th>{inline(cell)}</th>" for cell in head)
    body_html = ""
    for row in body:
        cells = row + [""] * (len(head) - len(row))
        body_html += "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in cells) + "</tr>"
    return (
        '<div class="md-table-wrap"><table class="md-table"><thead><tr>'
        + head_html
        + "</tr></thead><tbody>"
        + body_html
        + "</tbody></table></div>"
    )


def md_to_html(markdown: str) -> str:
    text = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if line.strip().startswith("```"):
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            out.append(
                f'<pre class="md-code"><code>{esc(chr(10).join(code))}</code></pre>'
            )
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(
                f'<h{level} class="md-h{level}">{inline(heading.group(2))}</h{level}>'
            )
            index += 1
            continue

        if (
            line.lstrip().startswith("|")
            and index + 1 < len(lines)
            and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[index + 1])
        ):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            out.append(render_table(table_lines))
            continue

        if re.match(r"^\s*>\s?", line):
            quote: list[str] = []
            while index < len(lines) and re.match(r"^\s*>\s?", lines[index]):
                quote.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            out.append(f'<blockquote class="md-quote">{inline(" ".join(quote))}</blockquote>')
            continue

        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items: list[str] = []
            while index < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[index]):
                items.append(inline(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[index])))
                index += 1
            tag = "ol" if ordered else "ul"
            out.append(
                f'<{tag} class="md-list">'
                + "".join(f"<li>{item}</li>" for item in items)
                + f"</{tag}>"
            )
            continue

        if re.match(r"^\s*(---|\*\*\*)\s*$", line):
            out.append('<hr class="md-divider">')
            index += 1
            continue

        paragraph = [line.strip()]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not re.match(r"^(#{1,4})\s+", lines[index])
            and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[index])
            and not re.match(r"^\s*>", lines[index])
            and not lines[index].strip().startswith("```")
            and not lines[index].lstrip().startswith("|")
        ):
            paragraph.append(lines[index].strip())
            index += 1
        rendered = [inline(item) for item in paragraph]
        hard_break = len(rendered) > 1 and any(
            re.match(r"^(?:[A-D][.．、)]\s|\*\*解析|\*\*答案)", item)
            for item in paragraph
        )
        out.append(
            '<p class="md-paragraph">'
            + ("<br>".join(rendered) if hard_break else " ".join(rendered))
            + "</p>"
        )

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Data


def load_slides(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"[error] 找不到 slides.json：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        files = sorted(path.glob("*.json"))
    elif path.is_file():
        files = [path]
    else:
        raise SystemExit(f"[error] 找不到分块目录：{path}")
    if not files:
        raise SystemExit(f"[error] {path} 里没有 JSON 分块文件")

    chunks: list[dict[str, Any]] = []
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[error] {file.name} 不是合法 JSON：{exc}") from exc
        if isinstance(data, list):
            chunks.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict) and isinstance(data.get("chunks"), list):
            chunks.extend(item for item in data["chunks"] if isinstance(item, dict))
        elif isinstance(data, dict):
            chunks.append(data)
    return chunks


def split_kind(question: str) -> tuple[str, str]:
    match = QUESTION_PREFIX.match(question)
    if not match:
        return "", question
    return match.group(1).strip(), question[match.end() :]


# ---------------------------------------------------------------------------
# Rendering


def stars_html(importance: int) -> str:
    filled = "★" * importance
    empty = "☆" * (5 - importance)
    return (
        f'<span class="point-stars" aria-label="重要度 {importance} / 5">'
        f'<span class="stars-on">{filled}</span>'
        f'<span class="stars-off">{empty}</span></span>'
    )


def render_example(example: dict[str, str], index: int) -> str:
    kind, question = split_kind(example["question_md"])
    kind_tag = f'<span class="tag tag-kind">{esc(kind)}</span>' if kind else ""
    return f"""<div class="example-card">
  <div class="example-head">
    <div class="row">
      <span class="example-index">例 {index}</span>
      {kind_tag}
      <span class="tag tag-amber">{esc(example["difficulty"])}</span>
    </div>
    <button type="button" class="example-toggle" aria-expanded="false">查看答案</button>
  </div>
  <div class="example-question md">{md_to_html(question)}</div>
  <div class="example-answer" hidden>
    <span class="answer-label">参考答案</span>
    <div class="md">{md_to_html(example["answer_md"])}</div>
  </div>
</div>"""


def render_point(point: dict[str, Any]) -> str:
    content = strip_leading_heading(point["content_md"], point["title"])
    examples = "".join(
        render_example(example, number)
        for number, example in enumerate(point["examples"], start=1)
    )
    practice = (
        f"""<div class="point-examples">
  <h4 class="point-examples-title">配套练习</h4>
  {examples}
</div>"""
        if point["examples"]
        else ""
    )
    return f"""<section class="point-card">
  <div class="point-head">
    <h3 class="point-title">{esc(point["title"])}</h3>
    {stars_html(point["importance"])}
  </div>
  <div class="md point-content">{md_to_html(content)}</div>
  {practice}
</section>"""


def render_mm_node(node: dict[str, Any], root: bool = False) -> str:
    label = esc(node.get("label") or "未命名")
    note = esc(node.get("note") or "")
    css = "mm-node mm-root" if root else "mm-node"
    button = (
        f'<button type="button" class="{css}" data-note="{note}">{label}</button>'
    )
    children = [child for child in node.get("children") or [] if child.get("label")]
    if not children:
        return button
    items = "".join(f"<li>{render_mm_node(child)}</li>" for child in children)
    toggle = (
        '<button type="button" class="mm-toggle" data-mm-toggle '
        'aria-label="折叠分支">−</button>'
    )
    return (
        '<div class="mm-branch">'
        f'<span class="mm-node-wrap">{button}{toggle}</span>'
        f'<ul class="mm-children">{items}</ul>'
        "</div>"
    )


def render_mindmap(tree: dict[str, Any]) -> str:
    return f"""<div class="mm">
  <div class="mm-toolbar">
    <span class="mm-title">思维导图</span>
    <span class="mm-actions">
      <button type="button" class="mm-icon-btn" data-mm-zoom="-0.1" aria-label="缩小">−</button>
      <span class="mm-scale-label">100%</span>
      <button type="button" class="mm-icon-btn" data-mm-zoom="0.1" aria-label="放大">+</button>
      <button type="button" class="mm-icon-btn" data-mm-reset aria-label="重置">⟲</button>
      <button type="button" class="mm-icon-btn" data-mm-fullscreen aria-label="全屏">⛶</button>
    </span>
  </div>
  <div class="mm-area">
    <div class="mm-scale">{render_mm_node(tree, root=True)}</div>
  </div>
  <div class="mm-detail" hidden>
    <div class="mm-detail-head">
      <span class="mm-detail-title"></span>
      <button type="button" class="mm-detail-close">关闭</button>
    </div>
    <p class="mm-detail-note">点击节点查看内容；有子节点时可点右侧按钮折叠。</p>
  </div>
</div>"""


def build_markdown(
    title: str, overview: str, file_name: str, summary: str, points: list[dict[str, Any]]
) -> str:
    lines = [f"# {title}", "", overview, "", "## " + title, "", summary, ""]
    lines.extend([f"> 来源：{file_name}", ""])
    for point in points:
        rating = "★" * point["importance"] + "☆" * (5 - point["importance"])
        lines.extend([f"### {point['title']}　{rating}", "", point["content_md"], ""])
        for number, example in enumerate(point["examples"], start=1):
            lines.extend(
                [
                    f"**练习 {number}**",
                    "",
                    example["question_md"],
                    "",
                    "<details><summary>参考答案</summary>",
                    "",
                    example["answer_md"],
                    "",
                    "</details>",
                    "",
                ]
            )
    lines.extend(["## 思维导图", "", mindmap_outline({"label": title, "children": [{"label": point["title"]} for point in points[:40]]})])
    return "\n".join(lines).rstrip() + "\n"


def mindmap_outline(tree: dict[str, Any], depth: int = 0) -> str:
    lines = ["  " * depth + f"- {tree.get('label', '')}"]
    for child in tree.get("children") or []:
        lines.append(mindmap_outline(child, depth + 1))
    return "\n".join(lines)


def snippet(markdown: str, limit: int = 120) -> str:
    text = re.sub(r"[*_`#>]", "", markdown or "")
    text = re.sub(r"\s+", " ", text).strip()
    match = re.match(r"(.+?[。！？!?])", text)
    if match:
        text = match.group(1)
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def render_page(
    *,
    title: str,
    overview: str,
    file_name: str,
    generated: str,
    points: list[dict[str, Any]],
    chapter_summary: str,
    mindmap: dict[str, Any],
    markdown: str,
) -> str:
    example_count = sum(len(point["examples"]) for point in points)
    key_count = sum(1 for point in points if point["importance"] >= 4)
    points_html = "".join(render_point(point) for point in points)
    chapter = f"""<article class="chapter-card">
  <button type="button" class="chapter-head" data-chapter-toggle aria-expanded="true">
    <span class="chapter-index">1</span>
    <span class="chapter-main">
      <span class="chapter-title">{esc(title)}</span>
      <span class="chapter-summary">{esc(chapter_summary)}</span>
      <span class="source-tags"><span class="source-tag">{esc(file_name)}</span></span>
    </span>
    <span class="chapter-arrow" aria-hidden="true">−</span>
  </button>
  <div class="chapter-body">
    {points_html}
  </div>
</article>"""

    style = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
    script = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
    markdown_json = json.dumps(markdown, ensure_ascii=False).replace("</", "<\\/")

    body = f"""<header class="course-head">
  <div class="row-between">
    <span class="tag">PPT / PDF 课程</span>
    <span class="small muted">{esc(generated)}</span>
  </div>
  <h1 class="course-title">{esc(title)}</h1>
  <p class="course-overview">{esc(overview)}</p>
  <div class="course-stats">
    <div class="stat"><span class="stat-num">1</span><span class="stat-label">章节</span></div>
    <div class="stat"><span class="stat-num">{len(points)}</span><span class="stat-label">知识点</span></div>
    <div class="stat"><span class="stat-num">{example_count}</span><span class="stat-label">例题</span></div>
    <div class="stat"><span class="stat-num">{key_count}</span><span class="stat-label">重点</span></div>
  </div>
  <div class="merge-note">1 份源文件 → 1 个章节；每份课件独立成章。</div>
</header>

<nav class="detail-tabs" role="tablist" aria-label="学习资料视图">
  <button type="button" class="detail-tab active" role="tab" aria-selected="true" aria-controls="panel-study" data-tab="study">学习资料</button>
  <button type="button" class="detail-tab" role="tab" aria-selected="false" aria-controls="panel-mindmap" data-tab="mindmap">导图</button>
</nav>

<section id="panel-study" role="tabpanel" aria-label="学习资料">
  {chapter}
</section>

<section id="panel-mindmap" role="tabpanel" aria-label="思维导图" hidden>
  {render_mindmap(mindmap)}
</section>

<div class="bottom-actions">
  <button type="button" class="btn btn-ghost" id="copy-md">复制 Markdown</button>
  <button type="button" class="btn btn-primary" id="download-md">保存学习文档</button>
</div>
<footer class="page-foot">内容由课件自动整理，仅供复习参考。</footer>"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="generator" content="ppt-course-notes">
<title>{esc(title)} · 学习资料</title>
<style>
{style}
</style>
</head>
<body>
<main class="page">
{body}
</main>
<div class="toast" id="toast" hidden></div>
<script type="application/json" id="markdown-data">{markdown_json}</script>
<script>
{script}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把分块考点 JSON 渲染成 HTML 学习资料")
    parser.add_argument("--slides", required=True, help="extract_slides.py 生成的 slides.json")
    parser.add_argument("--chunks", required=True, help="分块 JSON 目录或单个 JSON 文件")
    parser.add_argument("-o", "--out", required=True, help="输出 HTML 路径")
    parser.add_argument("--title", default="", help="覆盖章节标题（默认取 slides.json.title）")
    parser.add_argument("--overview", default="", help="覆盖概述文字")
    args = parser.parse_args(argv)

    for name in ("style.css", "app.js"):
        if not (ASSETS_DIR / name).is_file():
            raise SystemExit(f"[error] 缺少资源文件：{ASSETS_DIR / name}")

    slides = load_slides(Path(args.slides))
    chunks = load_chunks(Path(args.chunks))
    points, dropped = merge_chunks(chunks)
    if not points:
        raise SystemExit(
            "[error] 没有识别到考点：请检查 work/chunks/*.json 是否包含 knowledge_points，"
            "或课件是否全是课程事务信息/图片。"
        )

    file_name = str(slides.get("file_name") or "课件")
    stem = Path(file_name).stem
    title = args.title.strip()
    if not title:
        title = stem
        deck_title = str(slides.get("deck_title") or "").strip()
        if (
            GENERIC_STEM.match(stem)
            and deck_title
            and deck_title != stem
            and not re.match(r"^第\s*\d+\s*页$", deck_title)
            and len(deck_title) >= 2
        ):
            title = deck_title
    title = title or "课程学习资料"
    overview = args.overview or (
        f"按《{file_name}》独立整理：1 份课件对应 1 章，"
        "包含考点知识点、星级重要度与配套练习。"
    )
    chapter_summary = chunk_title_summary(points)

    mindmap = {
        "label": title,
        "children": [
            {
                "label": point["title"],
                "note": snippet(point["content_md"]),
                "children": [],
            }
            for point in points[:40]
        ],
    }

    markdown = build_markdown(title, overview, file_name, chapter_summary, points)
    page = render_page(
        title=title,
        overview=overview,
        file_name=file_name,
        generated=date.today().isoformat(),
        points=points,
        chapter_summary=chapter_summary,
        mindmap=mindmap,
        markdown=markdown,
    )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")

    example_count = sum(len(point["examples"]) for point in points)
    key_count = sum(1 for point in points if point["importance"] >= 4)
    kind_count = len(
        {
            split_kind(example["question_md"])[0]
            for point in points
            for example in point["examples"]
            if split_kind(example["question_md"])[0]
        }
    )

    warnings: list[str] = []
    if dropped:
        warnings.append(f"过滤了 {dropped} 个课程事务类知识点")
    short = [point["title"] for point in points if len(point["examples"]) < 2]
    if short:
        warnings.append(f"{len(short)} 个知识点练习不足 2 道")
    if all(point["importance"] == 5 for point in points):
        warnings.append("所有知识点都是 5 星，建议拉开重要度")
    if kind_count < 3:
        warnings.append(f"题型只有 {kind_count} 种，建议覆盖至少 3 种")
    if re.search(
        r'<(?:link|img|script|iframe)[^>]+(?:src|href)="https?://', page, re.IGNORECASE
    ) or re.search(r"url\(\s*[\"']?https?://", page):
        warnings.append("页面包含外部资源引用，请检查")

    print(
        f"OK {output.resolve()} | 章节 1 | 知识点 {len(points)} | "
        f"练习 {example_count} | 重点 {key_count} | 题型 {kind_count}"
    )
    for warning in warnings:
        print(f"WARN {warning}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())