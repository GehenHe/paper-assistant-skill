# 图表分发规则

论文中的图表不再集中放在独立的「关键图表」section，而是根据标题/内容语义分布到对应的内容区域。

## 归位规则

分析每张 Figure/Table 的标题（caption），按以下规则归位：

| 标题关键词 | 放置位置 |
|-----------|----------|
| `overview`, `概览`, `teaser`, `系统总览`, `pipeline overview` | `## 一句话总结` 之后（作为 teaser 图） |
| `architecture`, `架构`, `framework`, `框架`, `model overview`, `pipeline`, `system` | `## 方法概览 → 整体框架` 之后 |
| `module`, `模块`, `component`, `组件`, `block` | `## 方法概览 → 对应核心模块` 之中 |
| `result`, `结果`, `comparison`, `对比`, `benchmark`, `performance`, `success rate` | `## 实验 → 主要结果` 之中 |
| `ablation`, `消融`, `analysis`, `component study` | `## 实验 → 消融实验` 之中 |
| `dataset`, `数据集`, `task`, `任务场景`, `setup`, `实验设置`, `robot platform` | `## 实验 → 实验设置` 之中 |
| `generalization`, `泛化`, `cross-condition`, `cross-robot`, `transfer`, `OOD` | `## 实验 → 泛化实验` 之中 |
| `data efficiency`, `数据效率`, `scaling`, `曲线` | `## 实验 → 主要结果` 之中 |
| `qualitative`, `可视化`, `visualization`, `demo`, `example rollout` | `## 实验 → 主要结果` 之后 |
| `limitation`, `failure`, `失败案例`, `局限` | `## 初步思考 → 潜在局限` 之中 |

## 原则

- 图表嵌入在相关文字描述**之后**，紧邻其说明的内容
- 图表说明文字包含：图表内容解读 + 与论文论点的关系
- 如果某张图跨多个语义（如同时包含方法和结果），放在其**主要语义**对应的位置
- Table 同样按此规则分发（主结果表 → 主要结果、消融表 → 消融实验）
