---
name: paper-assistant
description: 交互式论文阅读助手。触发词："读论文"、"分析这篇paper"、"论文笔记"、提供PDF/arXiv链接。三阶段流程：初读建骨架 → 多轮问答 → 融合讨论完善笔记。
---

# 交互式论文阅读助手

三阶段工作：初读建骨架 → 多轮问答深化理解 → 融合讨论完善笔记。
核心理念：笔记是"活的"——初读只是起点，理解在问答中逐步建立。

## 适用场景

**触发方式**：
- 用户说"读论文"、"读一下这篇"、"帮我读这篇论文"、"分析这篇paper"、"论文笔记"
- 用户提供 arXiv 链接、DOI 链接、本地 PDF 路径或论文标题
- 用户说"继续讨论XX论文"、"接着聊上次那篇"→ 恢复之前的讨论

**支持的输入**：

| 输入方式 | 示例 |
|----------|------|
| arXiv 链接 | `https://arxiv.org/abs/2501.12345` |
| 本地 PDF | `/path/to/paper.pdf` |
| DOI 链接 | `https://doi.org/10.xxxx/...` |
| 论文标题 | "Attention Is All You Need" |

**不适用**：
- 非学术类 PDF（技术报告、手册、书籍章节）→ 用普通对话处理
- 用户只想快速查术语/公式 → 直接回答，无需走三阶段流程

## Step 0: 读取共享配置

先读取 `../_shared/user-config.json`，如果 `../_shared/user-config.local.json` 存在，再用它覆盖。

显式生成并在后续统一使用这些变量：
- `VAULT_PATH` — Obsidian vault 根路径
- `NOTES_PATH = {VAULT_PATH}/{paper_notes_folder}`
- `CONCEPTS_PATH = {NOTES_PATH}/{concepts_folder}`
- `SKILL_ROOT` — 本 skill 所在目录的绝对路径（即 SKILL.md 所在目录）

如果配置文件不存在，询问用户 vault 路径和笔记保存位置。

在开始处理前，检查关键工具可用性：
- `which curl` — 图片可达性检测
- `which pdfimages` — PDF 图片提取（不可用时标记为 fallback-only）

如果工具不可用影响了输出质量，在处理过程中明确告知用户原因和修复方法（如 `sudo apt install poppler-utils`）。

## Phase 1: 初读建骨架

### 1.1 论文发现与获取

```bash
python3 {SKILL_ROOT}/lib/discover.py "{用户输入}"
```

自动识别输入类型（arXiv 链接/标题/DOI/本地 PDF/HuggingFace URL），按优先级搜索：

| 输入类型 | 发现路径 |
|----------|----------|
| arXiv 链接 | 直接解析 ID → HTML 优先 → PDF 兜底 |
| 论文标题 | arXiv 搜索 → 未找到 → technical report pdf → HuggingFace/GitHub/官网 |
| 本地 PDF / DOI / PDF URL | 直接定位并下载 |

返回 JSON：`source_type`, `arxiv_id`, `pdf_path`, `metadata`。
每步失败记录原因，不静默跳过。

### 1.2 内容提取

```bash
python3 {SKILL_ROOT}/lib/extract.py --pdf {pdf_path}
```

>30 页自动启用目录优先策略：

| 策略 | 提取范围 |
|------|----------|
| 短论文（≤30 页） | 完整提取 |
| 长论文（>30 页） | ToC → Introduction（全文）→ Method（首段跳读）→ Experiments（主结果）→ Conclusion（全文）。Appendix 默认跳过 |

从论文中提取：
- **元数据**：标题、作者、机构、年份、会议/期刊、arXiv ID、DOI、项目主页
- **一句话总结**（≤50字）、**核心贡献**（3-5条）
- **问题背景**：要解决的问题 + 现有方法局限 + 本文动机
- **方法概览**：整体框架 → 核心模块（每模块1-2句话）→ 关键公式
- **实验**：数据集、主要结果、消融实验
- **图表**：所有 Figure 的编号、描述；所有 Table 的完整数据
- **初步思考**：亮点、局限、待深入问题

### 1.3 图片获取

```bash
python3 {SKILL_ROOT}/lib/images.py \
  --arxiv-id {arxiv_id} | --pdf-path {pdf_path} \
  --output-dir "{笔记路径}/assets" \
  --method-name {MethodName}
```

两级 fallback：arXiv HTML `<figure>` 提取 → PDF 提取（`pdfimages` 或 PyMuPDF/fitz）。返回结构化 JSON。

- `ref_type: url` → `![Figure X: caption](url)`
- `ref_type: local` → `![[local_name.png]]`
- 全部失败 → `> 📝 图片缺失：{原因}`，**严禁**在文件不存在时写入引用

URL 去重、ar5iv 编号陷阱等排错见 `references/image-troubleshooting.md`。

笔记保存后，运行 `download_note_images.py` 对外链做可达性检查。

### 1.4 生成初步笔记

按 `assets/paper-note-template.md` 模板生成，保存到 `{NOTES_PATH}/{YYYY}/{来源}/{MethodName}.md`。

- `YYYY`：论文发表/arXiv 年份
- `来源`：`arxiv` / `NeurIPS` / `ICLR` / `ICML` / `CVPR` / `ICCV` / `ECCV` / `ACL` / `AAAI` / 其他
- `MethodName`：方法名/模型名缩写

笔记必须包含：YAML frontmatter、`## 元信息`、`## 一句话总结`、`## 核心贡献`、`## 问题背景`、`## 方法概览`、`## 实验`、`## 初步思考`、`## 讨论与问答`（初始为空）。

**图表按语义分布到各 section**，不在末尾集中放置。分发规则见 `references/figure-placement.md`。

### 1.5 保存后告知用户

告知笔记路径和内容概要（核心贡献数/公式数/图表数/待深入问题数），邀请用户进入问答——可提问方法细节、公式含义、实验设计、概念解释或与研究方向的关系，说"总结讨论"结束本阶段。

### 1.6 质量自检

对照 `references/quality-standards.md` 的检查清单逐项验证（Figures 完整性、公式 5 类错误、Tables 行列完整、MathJax 格式）。发现缺失立即修正。

## Phase 2: 多轮问答

### 2.1 问答模式

用户在终端提问，Claude 在终端回答。**过程中不写笔记**——笔记只在话题结束时以总结形式写入。

回答要求：基于论文原文 + 相关知识储备，引用具体段落/公式/图表编号，首次出现的术语用 `[[概念]]` 标注。
不同问题类型的详细回答策略见 `references/discussion-guide.md`（8 类：概念解释/方法细节/问题定位/设计动机/实验分析/对比分析/局限批判/扩展思考）。

### 2.2 话题管理

问答以**话题**为单位组织——同一主题的连续问答归为一个话题。
- 用户切换到新主题时，先确认「这个话题先记下来吗？」
- 用户说"记一下"/"保存这条"→ 将当前话题总结写入笔记
- 用户可能问：方法细节、公式推导、实验设计、baseline 选择、扩展应用、概念解释等

### 2.3 话题总结写入

将围绕该话题的问答写入 `## 讨论与问答`。**以保留讨论细节为优先**——压缩的是冗余表达，不是信息量：

```markdown
### 话题{N}: {话题标题} `{date}`

**讨论过程**:
{保留问答的推理脉络。如果用户的多轮追问逐步推进了理解，保留这个递进过程。
关键问答可以 Q&A 形式记录，但合并同一子话题的碎片化交流。}

**关键结论**:
- {从讨论中沉淀的洞察}
- {被澄清的误解或新的理解}

**关联概念**: [[概念1]] · [[概念2]]
```

总结原则：
- **保留推理过程**，不只是结论——用户需要看到"怎么得出这个结论的"
- **保留论文引用位置**（Section X, Eq X, Figure X）——这是后续回溯的关键锚点
- **保留反驳和修正**——如果讨论中纠正了某个误解，记录"为什么之前理解不准确"
- 首次澄清的概念标注 `[[链接]]`

### 2.4 结束条件

用户说"总结讨论"/"更新笔记"/"差不多了"/"先这样"/"结束讨论"时退出问答。
进入 Phase 3 前确保所有话题已总结写入。用户直接说"结束"时提醒可先整理笔记。

## Phase 3: 融合讨论，完善笔记

### 3.1 回顾讨论

阅读 `## 讨论与问答` 中所有话题总结，识别三类可融合内容：

| 类型 | 融合目标 | 示例 |
|------|----------|------|
| 方法理解深化 | `## 方法概览` 对应模块 | 模块实现细节补充 |
| 概念澄清 | 正文 `[[概念]]` + 新建概念笔记 | 用户问"什么是 XX"后的澄清 |
| 批判思考 | `## 深入分析` | 实验设计质疑、改进建议 |

### 3.2 融合规则

**融合 ≠ 压缩**。将讨论中沉淀的理解补充到笔记对应章节，但 `## 讨论与问答` 中的原始讨论记录**完整保留**——它记录了"理解是如何建立起来的"。

| 讨论内容 | 融合方式 | 保留方式 |
|----------|----------|----------|
| 方法细节澄清 | 补充到 `## 方法概览` 对应模块 | 讨论原文保留，在方法处添加脚注 `[见讨论话题{N}]` |
| 概念理解深化 | 正文首次出现处补充 `[[概念]]` 链接 | 讨论中"为什么这个概念重要"的推理过程保留 |
| 批判性思考 | 写入 `## 深入分析` | 讨论中的质疑逻辑链保留 |
| 实验设计讨论 | 补充到 `## 实验` 对应子节 | 讨论中"为什么这个实验设计好/不好"的论证保留 |

**不要做的事**：
- 不要因为"方法细节已经写进方法概览了"就删掉讨论原文中"怎么理解这个细节"的推理
- 不要只保留结论——一个"ICT 是关键"的结论没有"为什么 2D trace 单独只提升 5pp 但组合提升 25pp"的推理有价值
- `## 讨论与问答` 开头添加提示，标注哪些话题已融入其他章节

### 3.3 补充概念库

扫描笔记中所有 `[[概念]]` 链接，检查 `{CONCEPTS_PATH}/` 下是否存在。
缺失的概念按 `references/concept-categories.md` 的 15 类体系归类创建（模板见该文件）。

### 3.4 收尾

更新 frontmatter：`status: enriched`、`last_discussed`、`discussion_rounds`。
告知用户融合结果（补充了几处细节、新增几个概念、深入分析条目数），提示可随时"继续讨论 {MethodName}"。

## 继续之前的讨论

用户说"继续讨论 XX 论文"时：
1. Glob 在 `{NOTES_PATH}` 下找到对应笔记并读取
2. 回顾 `## 讨论与问答` 和 `## 初步思考` 恢复上下文
3. 直接进入 Phase 2，结束后进入 Phase 3

## 笔记质量标准

- **公式**：LaTeX `$$` 块，前后留空行（Obsidian 适配），长公式用 `aligned` 拆分
- **图片**：优先外链 `![Figure X](url)`，不可用时本地化
- **概念链接**：技术术语首次出现用 `[[概念名]]` 标注
- **表格**：完整保留所有行列数据
- **文件名**：只用方法名/模型名，如 `Pi05.md`

## 前置依赖

| 依赖 | 级别 | 缺失时行为 |
|------|:---:|------|
| `curl` | **必需** | Phase 1.3 可达性检查跳过，保留外链不本地化 |
| `poppler-utils`（`pdfimages`） | **图片 fallback** | PDF 图片提取不可用；有 arXiv HTML 则用外链，否则用文字描述替代图片引用 |

环境缺少必需依赖时在 Step 0 即告知，不推迟到 Phase 1.3 静默跳过。

## 参考文件

| 文件 | 用途 | 何时阅读 |
|------|------|----------|
| `assets/paper-note-template.md` | 初读笔记模板 | Phase 1.4 生成笔记时 |
| `references/figure-placement.md` | 图表分发规则 | Phase 1.4 嵌入图表时 |
| `references/quality-standards.md` | 笔记质量规范 + 自检清单 | Phase 1.6 质量检查时 |
| `references/image-troubleshooting.md` | 图片获取排错指南 | Phase 1.3 图片获取时 |
| `references/concept-categories.md` | 概念分类体系 + 概念笔记模板 | Phase 3.3 补充概念库时 |
| `scripts/download_note_images.py` | 图片可达性检查 + 本地化 | Phase 1.3 执行 |
