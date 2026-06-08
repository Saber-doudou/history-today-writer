---
title: "history-today-writer"
summary: "On This Day — narrative-driven historical storytelling skill for WorkBuddy"
agent_created: true
---

# history-today-writer

A structured narrative writing skill for "On This Day" historical micro-articles (~350-800 words). Modular architecture: rules split by execution phase for context efficiency.

---

## 🎯 核心哲学：故事第一，升华第二

> **首要目标**：让不懂故事全貌的人，读完能知道发生了什么、为什么重要。
>
> **次要目标**：在此基础上完成标题总览、主旨升华。

**写作逻辑**：
```
旧逻辑：先有主旨 → 再找标题 → 再写故事 → 最后升华
新逻辑：先讲好故事（让不懂的人读懂）→ 标题总览故事 → 在此基础上升华
```

**核心原则**：
1. **读者视角优先**：从"不懂这个事件的人"角度出发
2. **人性共通性**：让读者在历史人物身上看到自己的影子
3. **命运与规律的对照**：个人选择 vs 历史必然的张力
4. **现代参悟**：读者能带走什么智慧
5. **标题直达主题**：让不了解故事的读者一目了然

---

## 📂 模块索引（按执行阶段加载）

| 阶段 | 加载文件 | 内容 | Token估算 |
|------|---------|------|-----------|
| **Phase 1 选题** | `topic_rules.md` | 事件价值矩阵评分 + 选题淘汰测试 | ~2K |
| **Phase 2-3 写作** | `writing_rules.md` | 叙事结构 + 6维工具包 + 写作标准 + 44条规则 + Forbidden Patterns + Humanizer | ~12K |
| **Phase 3.5 审校** | `review_rules.md` | P0/P1/P2审校表 + 元规则 + 反馈日志 + Rule 31-44 + 审校子系统 + 标点规范 | ~10K |
| **Phase 3.5 审校** | `review/prompts/` | 6维度深度审校Prompt模板 | ~21K |
| **Phase 3.6 判例** | `review/CASE_STUDIES.md` | 17条判例库（按需Grep检索，不预加载） | ~8K |

**模块化设计原则**：
- WriterAgent 不加载 review_rules.md —— 避免"知道考纲做题"
- ReviewAgent 不加载 writing_rules.md —— 纯粹的审核视角
- CASE_STUDIES.md 按需检索，不塞进上下文

---

## 🔄 自动化执行流程（Orchestrator 模式）

```
Phase 0: 防重跑检查（archive/daily/YYYY-MM-DD.md）
    ↓
Phase 1: 【加载 topic_rules.md】→ 选题+搜索 → topic_result.json
    ↓
Phase 2: 【加载 writing_rules.md】→ 写作+自检 → draft.md
    ↓
Phase 3: Phase 2内置 — Humanizer + P0复检
    ↓
Phase 3.5: 【加载 review_rules.md + review/prompts/】→ 6维度审校 → review_report.json
    ↓
Phase 3.6: 【判例预检 + Grep CASE_STUDIES.md】→ 领域专项检查
    ↓
  若 P0=0 且 P1≤1 → Phase 4
  否则 → 回到 Phase 2（最多2轮）
    ↓
Phase 4: 输出（全文 + 执行摘要）
    ↓
Phase 5: 记忆更新（MEMORY.md + TOPICS.md + CASE_STUDIES.md）
```

**效率规范**：网络请求上限3次；版本管理直接在目标文件 Edit；记忆更新合并为1次。

---

## 📊 质量仪表盘（每次执行后更新 MEMORY.md）

```yaml
## 质量趋势（最近10篇）
| 指标 | 值 | 趋势 |
|------|-----|------|
| 平均P0数 | [n] | [↑→↓] |
| 平均P1数 | [n] | [↑→↓] |
| 平均P2数 | [n] | [↑→↓] |
| 首版通过率 | [n]% | [↑→↓] |
| 平均修改轮次 | [n] | [↑→↓] |
| 规则触发Top3 | Rule[n](n次), Rule[n](n次), Rule[n](n次) | - |
```

---

## 🔗 关键文件路径

| 文件 | 路径 | 用途 |
|------|------|------|
| 主索引 | `SKILL.md` | 本文件——核心哲学+模块索引+执行流程 |
| 选题规则 | `topic_rules.md` | 评分矩阵+淘汰测试 |
| 写作规则 | `writing_rules.md` | 叙事结构+6维工具包+44条规则+禁止模式 |
| 审校规则 | `review_rules.md` | 审校表+元规则+Rule 31-44+审校子系统 |
| 审校Prompt | `review/prompts/0*.md` | 6维度深度审校模板 |
| 判例库 | `review/CASE_STUDIES.md` | 17条历史判例+四AI对比 |
| 选题历史 | `archive/daily/TOPICS.md` | 已写选题去重 |
| 记忆文件 | `../.workbuddy/memory/MEMORY.md` | 执行记录+系统改造 |

---

*Version: v7.1 | 2026-06-08 | 新增Rule 45-47（备胎叙事/科技史创新/时间线阶段）；Forbidden#14-16；科技/技术领域判例预检；8086处理器案例*
