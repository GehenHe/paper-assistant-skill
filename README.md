# Paper Assistant

> 不只是读论文——是**理解**论文。交互式学术论文阅读助手，基于标准 SKILL.md，可被 [Claude Code](https://claude.ai/code)、Codex 等 agent 平台调用。

<p align="center">
  <b>📄 论文 → 🤖 多轮对话 → 📝 结构化 Obsidian 笔记</b>
</p>

---

## 为什么用 Paper Assistant？

读论文最耗时的不是"读"本身，而是**建立理解**。传统工具能帮你翻译、总结、甚至画思维导图——但理解一个方法为什么这样设计、一个公式里每个符号的含义、一个实验结论对自己研究方向意味着什么，只能在对话中建立。

Paper Assistant 把论文阅读变成一个**三阶段对话过程**：

```
初读建骨架 ────────▶ 多轮问答深化 ────────▶ 融合完善笔记
(5 min)              (你来主导节奏)            (自动)
```

| 阶段 | 做什么 | 产出 |
|------|--------|------|
| **Phase 1** 初读 | 自动提取论文核心信息，生成结构化 Obsidian 笔记（含公式、图表、元数据） | 完整初稿笔记 |
| **Phase 2** 问答 | 围绕论文自由提问——方法细节、公式推导、实验设计、与你的研究方向的关系 | 讨论记录（保留推理过程） |
| **Phase 3** 融合 | 将讨论中沉淀的理解补充到笔记对应章节，概念链接自动补全 | 最终深度笔记 |

## 怎么用

### 安装

同一份 skill 可被多个 agent 平台调用，只是安装位置不同：

```bash
# Claude Code
git clone https://github.com/GehenHe/paper-assistant-skill.git ~/.claude/skills/paper-assistant/

# Codex（仓库级，从工作目录向上扫描 .agents/skills）
git clone https://github.com/GehenHe/paper-assistant-skill.git .agents/skills/paper-assistant/
# 或用户级：~/.codex/skills/paper-assistant/
```

SKILL.md 为唯一真相源，跨平台通用——相同的 frontmatter 与正文被两个平台直接读取，差异仅在安装路径。

### 开始阅读

```
# arXiv 链接
读论文 https://arxiv.org/abs/2512.08924

# 论文标题（自动搜索 arXiv / HuggingFace / GitHub）
读论文 Efficiently Reconstructing Dynamic Scenes One D4RT at a Time

# 本地 PDF
读论文 /path/to/paper.pdf
```

### 继续讨论

```
继续讨论 D4RT
```

## 特性

### 智能问答策略

Phase 2 不是简单的 Q&A——针对 8 类问题有**不同的回答策略**：

- **概念解释**：逐层展开（定义 → 原理 → 设计细节 → 与已知概念关联）
- **问题定位**：用最简单的话说清"这篇论文到底做了什么"
- **设计动机**：区分"作者为什么选这个"和"客观上为什么这是好的"
- **对比分析**：跨论文建立连接，引用之前读过的论文内容
- [完整策略](references/discussion-guide.md)

### 多来源论文发现

不再假设所有论文都在 arXiv：

```
arXiv 链接 → HTML 优先 → PDF 兜底
论文标题 → arXiv 搜索 → HuggingFace 直链 → GitHub → 官网
本地 PDF → 直接读取
```

### 长论文智能提取

>30 页自动启用目录优先策略：ToC → Introduction（全文）→ Method（跳读）→ Main Results → Conclusion。Appendix 默认跳过。

### 图片自动获取

arXiv HTML 提取 `<figure>` → PDF 提取（`pdfimages` 或 PyMuPDF 兜底）→ URL 去重 → 可达性检查。图片落地前不会写入不存在的引用。

## 笔记示例

生成的 Obsidian 笔记包含完整的 YAML frontmatter、结构化章节（元信息 / 核心贡献 / 问题背景 / 方法概览 / 实验 / 讨论与问答 / 深入分析）、公式渲染、概念双向链接、图表嵌入。

## 依赖

| 依赖 | 级别 | 说明 |
|------|:---:|------|
| `curl` | 必需 | 图片可达性检测 |
| `poppler-utils` | 可选 | PDF 图片提取（无则用 PyMuPDF 兜底） |
| `PyMuPDF` | 可选 | PDF 图片兜底方案 |

## 项目结构

```
paper-assistant/
├── SKILL.md                          # Skill 入口（流程编排指令，唯一真相源）
├── lib/                              # 论文获取独立库
│   ├── discover.py                   #   多来源论文发现与下载
│   ├── extract.py                    #   ToC-first 内容提取
│   └── images.py                     #   图片获取管线
├── scripts/
│   └── download_note_images.py       # 后处理：可达性检查 + 本地化
├── assets/
│   ├── paper-note-template.md        # Obsidian 论文笔记模板
│   └── concept-note-template.md      # 概念笔记模板
├── references/
│   ├── discussion-guide.md           # 8 类问题回答策略
│   ├── quality-standards.md          # 公式/表格/图片质量规范
│   ├── image-troubleshooting.md      # 图片获取排错指南
│   ├── figure-placement.md           # 图表分发放置规则
│   └── concept-guide.md              # 概念库维护指南
├── CLAUDE.md                         # 架构说明 + 跨平台可移植契约
└── .gitignore
```

## License

MIT
