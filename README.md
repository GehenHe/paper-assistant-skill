# Paper Assistant

交互式学术论文阅读助手 (Claude Code Skill)。

## 功能

三阶段工作流：

1. **初读建骨架** — 读取论文 → 提取核心信息 → 生成结构化 Obsidian 笔记
2. **多轮问答** — 围绕论文深入讨论，按话题组织，讨论内容融合回笔记
3. **融合完善** — 回顾讨论 → 补充方法细节 → 更新概念库

## 安装

将 `paper-assistant/` 目录复制到 Claude Code 的 skills 目录：

```bash
cp -r paper-assistant ~/.claude/skills/
```

或放在项目本地 `.claude/skills/paper-assistant/`。

## 触发方式

- "读论文" / "分析这篇paper" / "论文笔记"
- 提供 arXiv 链接、DOI、本地 PDF 路径或论文标题
- "继续讨论XX论文" → 恢复之前的讨论

## 依赖

- `curl` — 图片可达性检测
- `poppler-utils` (`pdfimages`) — PDF 图片提取（可选）

## 目录结构

```
paper-assistant/
├── SKILL.md              # Skill 入口
├── assets/               # 笔记模板
├── references/           # 参考规范（按需加载）
└── scripts/              # 工具脚本
```
