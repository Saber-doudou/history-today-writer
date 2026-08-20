> ⚠️ **LEGACY（2026-08-20 标注）**：v9.7.6 时代的快速指南，内容陈旧（现 v9.8.3/165 条），已从 L3 发布白名单移除，不再维护。权威见 SKILL.md + rule_index.md。

> ⚠️ **LEGACY（2026-08-20 标注）**：v9.7.6 时代的快速指南，内容陈旧（现 v9.8.3/165 条），已从 L3 发布白名单移除，不再维护。权威见 SKILL.md + rule_index.md。

# 🗺️ history-today-writer v9.7.6 模块加载指南

> 快速参考：按阶段读什么、写什么、输出什么。

## 执行流程速览

```
Phase 0  防重跑         检查 archive/daily/YYYY-MM-DD.md
Phase 1  选题           读 topic_rules.md → 写 topic_result.json
Phase 2  写作           读 writing_core.md + rule_index.md + (按题材)topics/1个 → 写 archive/daily/YYYY-MM-DD.md
Phase 3  自检+Humanizer 用 writing_core.md 内嵌清单
Phase 3.5 审校           读 review_rules.md + review/prompts/ → 写 YYYY-MM-DD_review.json
Phase 3.6 判例           按需 Grep CASE_STUDIES.md
Phase 4  输出            消息贴全文 + 执行摘要
Phase 5  记忆            更新 MEMORY.md + TOPICS.md + CASE_STUDIES.md
```

## 阶段×模块×Token

| 阶段 | 加载文件 | Token | 做什么 |
|------|---------|-------|--------|
| 选题 | topic_rules.md | ~1K | 五维评分、淘汰测试 |
| 写作 | writing_core.md + rule_index.md | ~13K | 核心叙事规则+全量索引（darwin step3.4 拆分） |
| 写作(按题材) | topics/ 1 个 | ~1-2K | 题材专项规则（灾难/战争制度/科技工程） |
| 写作(按需) | craft_optional.md | ~2K | 非强制技法（参悟/心理/节奏词/镜像等） |
| 审校 | review_rules.md | ~7K | 审校表、Rule 31-90、标点 |
| 审校 | review/prompts/ | ~21K | 6维度深度审校模板 |
| 判例 | CASE_STUDIES.md | ~8K | 按需Grep，不预加载 |
| 总览 | SKILL.md | ~2K | 核心哲学+模块索引 |

## 关键设计原则

1. **写作不加载审校标准** → 避免"知道考纲做题"
2. **审校不加载写作规则** → 纯粹审核视角
3. **判例按需检索** → 不塞进上下文
4. **规则有生命周期** → P0/P1永不退休，P2可观察/退休
5. **判例预检** → 审校前按领域筛高频问题

## 文件清单

```
~/.workbuddy/skills/history-today-writer/
├── SKILL.md                         ← 模块索引（2K）
├── topic_rules.md                   ← 选题规则（1K）
├── writing_core.md                  ← 写作核心（darwin step3.4）
├── rule_index.md                    ← 规则全量索引（138行）
├── topics/                          ← 题材专项规则（按题材加载1个）
│   ├── nature_disaster.md
│   ├── war_institution.md
│   └── tech_engineering.md
├── craft_optional.md                ← 非强制技法（按需Read）
├── archive/cold_rules.md            ← 冷规则正文存档
├── writing_rules.md                 ← 已废弃占位指针（勿加载）
├── review_rules.md                  ← 审校规则（7K）
├── review/
│   ├── CASE_STUDIES.md              ← 判例库（8K，按需检索）
│   ├── prompts/                     ← 6维度审校Prompt（21K，仅审校加载）
│   │   ├── 01_language.md
│   │   ├── 02_fact_accuracy.md
│   │   ├── 03_narrative_logic.md
│   │   ├── 04_terminology.md
│   │   ├── 05_structure.md
│   │   └── 06_expression.md
│   ├── schema/review_output.json
│   ├── templates/report.html
│   └── scripts/review_scheduler.py

F:/WorkBuddy/history-today/
├── archive/daily/YYYY-MM-DD.md       ← 文章输出
├── archive/daily/TOPICS.md           ← 选题历史+复盘
└── .workbuddy/memory/MEMORY.md       ← 执行记录+质量仪表盘
```
