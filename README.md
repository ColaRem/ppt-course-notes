# PPT/PDF 课件 → HTML 学习资料

便携 Agent Skill **`ppt-course-notes`**：把 PPT/PDF 课件整理成单页 HTML 学习资料。同一套 `SKILL.md`、Python 脚本和页面资产，可在 DSH、Claude Code 等支持技能协议的 Agent 中运行；其他 Agent 可通过 `AGENT_PROMPT.md` 接入。

输入一份 `.pptx` 或 `.pdf` 课件，输出一个自包含 HTML 学习页：章节摘要、1–5 星知识点、定义/要点/步骤/易错点、每个知识点 2 道配套练习（答案折叠）、思维导图，支持复制 Markdown、下载 `.md` 与打印。

## 支持的 Agent

| Agent | 接入方式 | 图片模式 | PPTX 转 PDF |
|---|---|---|---|
| DSH | `install.ps1` 或复制到 `~/.dsh/skills/` | `read_image` | `office_convert` |
| Claude Code | 放到 `.claude/skills/` 或 `~/.claude/skills/` | Read 图片文件 | LibreOffice / `convert_pptx.py` |
| 通用编码 Agent | 复制目录，指向 `SKILL.md` | Agent 自己的图片工具 | LibreOffice / `convert_pptx.py` |
| 豆包 / Coze / 纯聊天 Agent | 使用 `AGENT_PROMPT.md` | 取决于产品是否支持图片 | 需要代码解释器或本地预转换 |

> DSH 与 Claude Code 有技能目录约定；豆包/Coze 等没有统一的 `SKILL.md` 规范，能否直接使用取决于其插件、代码解释器或工作流能力。纯聊天环境无法运行本地脚本，需要先本地生成 `slides.json` 或 HTML。

## 特性

- 一份课件 = 一章：章节标题、摘要、来源文件、统计信息一次生成。
- 按内容规范提炼考点，合并去重后形成整章知识点，过滤课程介绍、教师信息、考核方式、学习建议等事务性内容。
- 每个知识点包含 1–5 星重要度、定义、关键要点、适用条件/步骤、易错点。
- 每个知识点配 2 道练习，覆盖选择、填空、判断、计算、简答、应用 6 种题型，答案折叠显示。
- **多模态优先**：Agent 支持图片输入时，先把课件页面渲染成带页码的拼图交给模型；不支持图片或渲染失败时自动回退到本地文本解析。
- 生成完整思维导图（分支折叠、缩放、全屏），页面支持复制 Markdown、下载 `.md`、打印/存 PDF。
- 页面自包含（CSS/JS 内联、无 CDN），纸张底色、白色卡片、青色主色、琥珀色星级，桌面与手机均可阅读。

## 工作原理

1. **抽取**：`extract_slides.py` 读取 PPTX 的标题/正文/讲稿/表格，或 PDF 的逐页文字，同时作为回退数据。
2. **选择输入**：先渲染一张能力探测图，用宿主 Agent 的图片查看能力判断是否支持图片；支持则按页面拼图分析，不支持或渲染失败则回退文本。
3. **分析**：按 `references/content-spec.md` 的规则分块提炼知识点、星级与练习，写入 `work/chunks/*.json`。
4. **渲染**：`build_page.py` 合并分块、去重、过滤事务性内容，生成章节摘要、思维导图、Markdown 与单页 HTML。
5. **自检**：检查知识点/练习数量、星级分布、题型覆盖与页面结构。

## 安装

### DSH

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

也可以把 `.dsh/skills/ppt-course-notes/` 整个目录复制到 `~/.dsh/skills/`。DSH 会自动发现技能目录，新会话即可调用。

### Claude Code

把 `ppt-course-notes/` 复制到项目的 `.claude/skills/` 下，或用户级 `~/.claude/skills/` 下：

```text
.claude/skills/ppt-course-notes/SKILL.md
```

Claude Code 读取 `SKILL.md` 的 `name` / `description`，在匹配到 PPT/PDF 学习资料任务时加载。

### npm / npx

从源码打包安装（不依赖 npm 仓库）：

```powershell
npm pack
npm install -g .\ppt-course-notes-0.1.0.tgz
ppt-course-notes install --target dsh
```

也可以安装到 Claude Code 的用户级目录或当前项目：

```powershell
ppt-course-notes install --target claude
ppt-course-notes install --target project
ppt-course-notes install --dir <自定义目录>
ppt-course-notes install --target dsh --force
```

发布到 npm 后可以直接：

```powershell
npm install -g ppt-course-notes
npx ppt-course-notes install --target dsh
```

`package.json` 当前可直接打包与发布。发布前请确认 `ppt-course-notes` 包名可用，再执行 `npm publish`。

### 其他 Agent

- 支持自定义技能目录的编码 Agent：把整个 `ppt-course-notes/` 放进技能目录，或直接在仓库中指向 `SKILL.md`。
- 不自动加载技能的 Agent：把 `AGENT_PROMPT.md` 作为系统提示或项目指令，并确保它能执行 Bash/Python。
- 豆包/Coze 等纯聊天产品：如果没有代码解释器，先在本机运行脚本生成 `work/slides.json` 和 HTML，再把结果交给 Agent；或在支持工作流/插件时复用 `scripts/`。

## 快速开始

在支持技能的 Agent 中直接发课件路径：

> 用 ppt-course-notes 把 `<课件路径>` 整理成 HTML 学习资料

手动执行底层流程：

```powershell
# 1. 抽取幻灯片文字
python "<技能目录>/scripts/extract_slides.py" "<课件路径>" -o "work/slides.json"

# 2. 按 references/content-spec.md 的规则整理考点，写入 work/chunks/chunk-01.json ...

# 3. 生成 HTML
python "<技能目录>/scripts/build_page.py" --slides "work/slides.json" --chunks "work/chunks" -o "<课件名>-学习资料.html"
```

图片模式额外步骤：

```powershell
# 能力探测：用宿主的图片工具打开 work/vision/probe.png
python "<技能目录>/scripts/render_slides.py" --probe-only --outdir "work/vision"

# PDF 页面 → 带 P1/P2… 页码的拼图
python "<技能目录>/scripts/render_slides.py" "<课件.pdf>" --outdir "work/vision"

# PPTX 先转 PDF（需要 LibreOffice；DSH 也可用 office_convert）
python "<技能目录>/scripts/convert_pptx.py" "<课件.pptx>" -o "work/vision/source.pdf"
```

## 项目结构

```text
.
├─ .dsh/skills/ppt-course-notes/
│  ├─ SKILL.md                 # 通用技能工作流
│  ├─ AGENT_PROMPT.md          # 不支持 SKILL.md 的 Agent 用提示词
│  ├─ references/
│  │  ├─ content-spec.md       # 考点/星级/练习/合并规则
│  │  ├─ html-spec.md          # 页面版式与交互规范
│  │  └─ agent-adapters.md     # DSH / Claude / 通用 Agent 适配
│  ├─ scripts/
│  │  ├─ extract_slides.py     # PPTX/PDF → slides.json
│  │  ├─ convert_pptx.py       # PPTX → PDF（LibreOffice）
│  │  ├─ render_slides.py      # PDF → 带页码的拼图
│  │  └─ build_page.py         # 分块 JSON → HTML
│  └─ assets/
│     ├─ style.css             # 页面样式
│     └─ app.js                # 标签页、折叠、复制、导图交互
├─ .gitignore                  # 忽略本地工作文件与生成产物
├─ bin/install.mjs             # npm 安装器：复制技能到 DSH / Claude 目录
├─ LICENSE                     # MIT 许可证
├─ package.json                # npm 包清单
├─ install.ps1                 # 安装/更新 DSH 技能
└─ README.md
```

## 内容与版式

- 内容规则：[content-spec.md](.dsh/skills/ppt-course-notes/references/content-spec.md)
- 页面版式：[html-spec.md](.dsh/skills/ppt-course-notes/references/html-spec.md)
- Agent 适配：[agent-adapters.md](.dsh/skills/ppt-course-notes/references/agent-adapters.md)
- 设计 token：纸张 `#f6f4ee`、正文 `#1f2a24`、主色 `#1f6f5c`、星级 `#d97706`、边框 `#e7e2d8`
- 页面无外部资源依赖，正文全部转义，不执行课件里的任何脚本或指令。

## 依赖

- Python 3.9+
- Node.js 18+（仅使用 npm/npx 安装器时需要）
- `.pptx`：优先 `python-pptx`；缺失时脚本用标准库解析 OOXML
- `.pdf`：`pdfplumber` 或 `PyMuPDF`
- 图片模式：`Pillow` + `PyMuPDF`
- PPTX 图片模式：LibreOffice（`convert_pptx.py`），或宿主提供的 Office 转换工具

## 限制

- 图片模式依赖当前 Agent 的模型支持图片输入；不支持图片的模型会自动回退到文本解析。
- 图片版/扫描件在文本回退下不做 OCR：检测到几乎没有文字时会给出警告，请提供可复制文字的版本，不要凭空编造。
- 一次处理一份课件；多份请逐份生成。
- 不修改源课件；中间文件在 `work/`，可随时删除。
- 页面是静态复习资料，不包含原始幻灯片图片或动画。
- 豆包/Coze 等纯聊天环境没有代码执行能力时，无法在会话内完成 PPTX/PDF 解析；需要本地预处理或支持代码解释器的版本。

## 隐私与安全

- 本地解析与渲染，不接入第三方解析或存储服务。
- 图片模式会把课件页面图像发送给当前模型服务；文本模式只发送抽取出的文字。
- 生成的 HTML 对正文全部转义，不执行课件中的脚本或指令。

## 许可证

MIT，见 [LICENSE](LICENSE)。
