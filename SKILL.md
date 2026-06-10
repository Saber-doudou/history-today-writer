---
title: "history-today-writer"
summary: "On This Day — narrative-driven historical storytelling skill for WorkBuddy"
agent_created: true
trigger_words:
  - "历史上的今天"
  - "今天的历史"
  - "历史故事"
  - "on this day"
  - "historical story"
  - "历史短篇"
  - "每日历史"
  - "写历史"
  - "历史写作"
keywords:
  - "历史"
  - "故事"
  - "写作"
  - "叙事"
  - "自动化"
  - "微文章"
---

# history-today-writer

A structured narrative writing skill for "On This Day" historical micro-articles (~500-800 words). Modular architecture: rules split by execution phase for context efficiency.

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
| **Phase 2-3 写作** | `writing_rules.md` | 叙事结构 + 6维工具包 + 写作标准 + 54条规则 + 20条禁止模式 + Humanizer | ~14K |
| **Phase 3.5 审校** | `review_rules.md` | P0/P1/P2审校表 + 元规则 + 反馈日志 + Rule 31-50 + 审校子系统 + 标点规范 | ~11K |
| **Phase 3.5 审校** | `review/prompts/` | 6维度深度审校Prompt模板 | ~21K |
| **Phase 3.6 判例** | `review/CASE_STUDIES.md` | 20条判例库（按需Grep检索，不预加载） | ~10K |

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

## 🤖 多 Agent 执行模式（v8.0 🆕）

> **2 Agent spawn 模式**：Automation 本身充当 Orchestrator，负责编排协调；实际 spawn 的 Agent 只有 2 个。

| Agent | 职责 | 阶段 | 加载模块 | 预估 Token |
|-------|------|------|---------|:---:|
| **writer** | 选题 + 搜索 + 写作 + Humanizer + 自检 | Phase 1-3 | `topic_rules.md` + `writing_rules.md` | ~15K |
| **reviewer** | 6维度审校 + 判例检索 | Phase 3.5-3.6 | `review_rules.md` + `review/prompts/*.md` | ~32K |

**Orchestrator**（Automation 自身，非 spawn 的 Agent）负责：TeamCreate → 分派 → 收集 → 裁决 → 输出 → TeamDelete。

### Agent 级异常处理

| 场景 | 处理策略 |
|------|---------|
| writer 超时（8分钟无响应） | Orchestrator 检查文件是否已写入 → 若已写入则手动继续 → 若未写入则重试 1 次，仍失败则终止并报告 |
| reviewer 超时（10分钟无响应） | Orchestrator 跳过审校，直接输出初稿 + 标注"⚠️ 未审校" |
| writer 返回空文 | 检查搜索结果是否为空 → 使用 TOPICS.md 备用选题 |
| reviewer 返回空结果 | Orchestrator 重试 1 次，仍为空则跳过审校 |
| 文件写入冲突 | writer 写 `.md`，reviewer 写 `_review.json`，天然隔离 |
| SendMessage 丢失 | 等待完整超时（writer 8分钟/reviewer 10分钟）→ 检查文件是否已写入 → 若已写入则手动继续 → 若未写入则重试 |

### 迭代终结条件

- 审校通过（P0=0 且 P1≤1）→ 输出文章
- 审校不通过 → writer 修复 → reviewer 重新审校（最多 2 轮）
- 2 轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本

### 消息协议

writer → orchestrator：
```json
{ "agent": "writer", "status": "done", "file": "archive/daily/{date}.md", "topic": "选题标题", "score": 18 }
```

reviewer → orchestrator：
```json
{ "agent": "reviewer", "status": "done", "file": "archive/daily/{date}_review.json", "p0_count": 0, "p1_count": 0, "pass": true }
```

orchestrator → writer（修复指令）：
```json
{ "action": "fix", "review_file": "archive/daily/{date}_review.json", "fix_only": ["p0", "p1"] }
```

---
## 🚨 边界条件与异常处理

### 网络异常处理
1. **搜索无结果**：使用备用选题列表（TOPICS.md 中的待写选题）
2. **API 超时**：重试 2 次，间隔 5 秒；仍失败则使用缓存数据
3. **网络不可用**：切换到离线模式，使用本地素材库

### 质量异常处理
1. **多轮修改不达标**：超过 3 轮修改仍不通过，标记为"需人工审核"
2. **选题冲突**：自动选择下一个高分选题
3. **Token 超限**：精简内容，优先保证核心叙事

### 资源限制处理
1. **文件过大**：自动压缩图片，精简非核心内容
2. **存储空间不足**：清理旧的临时文件，保留最近 30 天的存档

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

*Version: v8.1 | 2026-06-10 | 超时逻辑修复（文件检查优先）；自检规则14-20（因果链/句式去重/泛化断言/中国视角/全员结局/数据唯一/场景具象）；Forbidden#20（元信息外露）；目标字数500-800*
