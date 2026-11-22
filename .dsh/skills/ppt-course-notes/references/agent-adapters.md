# Agent 适配说明

核心流程只依赖 Python 脚本和 `SKILL.md` 的通用协议；不同 Agent 只需要替换“查看图片”“PPTX 转 PDF”“发布文件”这三个宿主能力。

## 能力映射

| 能力 | DSH | Claude Code | 通用编码 Agent | 纯聊天 Agent |
|---|---|---|---|---|
| 查看 `probe.png` / sheet | `read_image` | `Read` 图片文件 | 模型图片输入工具 | 图片上传/查看（若支持） |
| PPTX → PDF | `office` 技能 + `office_convert` | `scripts/convert_pptx.py`（LibreOffice） | 同 Claude Code，或宿主转换工具 | 需先本地转换 |
| 运行 Python 脚本 | `pwsh` | `Bash` | `Bash` / 终端 | 需代码解释器 |
| 发布 HTML | `present` | 直接给文件链接 | 直接给文件链接 | 附件/文件卡片 |
| 技能安装位置 | `.dsh/skills/` 或 `~/.dsh/skills/` | `.claude/skills/` 或 `~/.claude/skills/` | 任意目录，指向 `SKILL.md` | 使用 `AGENT_PROMPT.md` |

## DSH

- 安装：运行仓库根目录的 `install.ps1`，或把本目录复制到 `~/.dsh/skills/ppt-course-notes/`。
- 图片探测：`read_image("work/vision/probe.png")`。
- PPTX 图片模式：加载 `office` 技能，用 `office_convert`（`format: "pdf"`）转换，复制临时 PDF 到 `work/vision/source.pdf`，再运行 `render_slides.py`。
- 交付：回复文件链接；环境支持时用 `present` 发布 HTML。
- 文本模型（不支持图片）会自动走文本回退，无需改配置。

## Claude Code

- 安装：把 `ppt-course-notes/` 放到项目的 `.claude/skills/` 下，或用户级 `~/.claude/skills/` 下；Claude Code 会读取 `SKILL.md`。
- 图片探测：用 Read 打开 `work/vision/probe.png`；Claude 能直接查看图片。
- PPTX 图片模式：安装 LibreOffice 后运行 `python scripts/convert_pptx.py deck.pptx -o work/vision/source.pdf`；没有 LibreOffice 时也可以先在 PowerPoint/Keynote 中另存为 PDF，或走文本模式。
- 交付：直接给 HTML 文件路径/链接。

## 通用编码 Agent（Cursor、Codex、OpenHands 等）

- 把本目录放进仓库，让 Agent 读取 `SKILL.md` 和 `references/content-spec.md`。
- 需要能执行 Bash/Python；图片模式还需要模型支持图片输入。
- 没有 `read_image` 这类工具时，使用 Agent 自己的图片查看/上传能力。
- PPTX 转 PDF 使用 `convert_pptx.py` 或宿主工具；PDF 直接渲染。

## 豆包 / Coze / 其他聊天 Agent

这些产品没有统一的 `SKILL.md` 技能规范，需要按实际能力判断：

- 如果支持**自定义插件、代码解释器或工作流**：把 `scripts/` 放进可执行环境，按 `SKILL.md` 的流程运行，或把 `AGENT_PROMPT.md` 作为系统提示。
- 如果只支持**聊天 + 文件上传**，没有代码执行：Agent 无法本地解析 PPTX/PDF，也无法运行渲染脚本。此时只能：
  1. 先在本地用本仓库脚本生成 `work/slides.json` 和 HTML，再把结果交给 Agent 润色；或
  2. 让 Agent 读取它自己解析出的文本，按 `references/content-spec.md` 直接写 HTML（会丢失图片/图表信息）。
- 不要假设豆包/Coze 会自动发现 `SKILL.md`；以该产品当前的“插件/技能/代码解释器”能力为准。

## 纯文本模型

没有图片输入能力时，跳过图片探测，直接使用 `extract_slides.py` 的文本结果。扫描件/纯图片 PDF 需要用户先提供 OCR 或可复制文字的版本。

## 通用约定

- 所有脚本只依赖 Python；路径参数用引号包住，兼容空格和中文。
- `work/` 是临时目录，不放技能目录。
- 页面是自包含 HTML，不依赖宿主 CDN 或网络。
