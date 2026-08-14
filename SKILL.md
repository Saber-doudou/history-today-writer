---
name: "history-today-writer"
title: "history-today-writer"
summary: "On This Day — narrative-driven historical storytelling skill for WorkBuddy"
agent_created: true
trigger_words:
  - "历史上的今天"
  - "historytoday"
  - "今天的历史"
  - "历史故事"
  - "on this day"
  - "historical story"
  - "历史短篇"
  - "每日历史"
  - "写历史"
  - "历史写作"
keywords:
  - "历史上的今天"
  - "historytoday"
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

| 阶段 | 加载文件 | 内容 | 字符数 |
|------|---------|------|-----------|
| **Phase 1 选题** | `topic_rules.md` | 事件价值矩阵评分 + 选题淘汰测试 | ~1.9K |
| **Phase 2-3 写作** | `writing_core.md` + `rule_index.md` +（按题材）`topics/` 1 个 +（按需）`craft_optional.md` | 核心：叙事结构 + 6维工具包 + 写作标准 + 59条hot规则（§5A基础23 + §5X通用36）+ 温控表；索引：155条规则编号+摘要；题材专项×3；非强制技法 | 核心70K（v9.7.8瘦身后）+ 索引14K + 题材6-12K（+按需12K） |
| Phase 3.5 审校 | `review_rules.md` | P0/P1/P2审校表 + 元规则 + 反馈日志 + Rule 31-90 + 审校子系统 + 标点规范 | ~39K |
| **Phase 3.5 审校** | `review/prompts/` | 6维度深度审校Prompt模板 | ~47K |
| **Phase 3.6 判例** | `review/CASE_STUDIES.md` | 51条案例（续号至50+来源附录；只Grep命中关键词，禁止整读进上下文） | ~96K |

**模块化设计原则**：
- Orchestrator 写作阶段不加载 review_rules.md —— 避免"知道考纲做题"
- Orchestrator 写作阶段加载：writing_core.md + rule_index.md +（按题材）topics/ 1 个 —— 题材专项规则按需加载省Token（darwin step3.4）
- craft_optional.md 非强制技法按需 Read，不默认加载
- cold 规则降级为「编号+1行摘要」（rule_index.md），正文存 archive/cold_rules.md
- Orchestrator 精修阶段加载 review_rules.md —— 精准修复
- ReviewerAgent 不加载 writing_core.md —— 纯粹的审核视角
- CASE_STUDIES.md（约96K）只 grep 命中关键词，禁止整读进上下文

---

## 🔄 自动化执行流程（Orchestrator 模式）

```
Phase 0: 防重跑检查（archive/daily/YYYY-MM-DD.md）
    ↓
Phase 1: 【加载 topic_rules.md】→ 选题+搜索 → topic_result.json
    ↓
Phase 2: 【加载 writing_core.md + rule_index.md】→ 写作+自检 → draft.md
    ↓
Phase 3: Phase 2内置 — Humanizer + P0复检
    ↓
Phase 3.5: 【加载 review_rules.md + review/prompts/】→ 6维度审校 → review_report.json
    ↓
Phase 3.6: 【判例预检 + Grep CASE_STUDIES.md（只grep命中关键词，禁止整读96K进上下文）】→ 领域专项检查
    ↓
  若 P0=0 且 P1≤1 → Phase 3.7
  否则 → 回到 Phase 2（最多2轮）
    ↓
Phase 3.7: 【人工审核检查点】→ 输出当前最佳版本 → 等待 Master 确认
    ↓
  - Master 确认 → 进入 Phase 4
  - Master 要求修改 → 收集反馈回 Phase 2（最多 1 轮人工修改）
  - Master 要求废弃 → 标记后跳过此选题
  - 超时无人确认（默认）→ 自动进入 Phase 4
    ↓
Phase 4: 输出（全文 + 执行摘要）
    ↓
Phase 4.5: ASO优化（标题+摘要+标签优化）→ archive/daily/YYYY-MM-DD_aso.md
    ↓
Phase 5: 记忆更新（MEMORY.md + TOPICS.md + CASE_STUDIES.md）
    ↓
Phase 6: 投喂素材准备（创建 投喂素材/YYYYMMDD/ + 8个空txt）→ 四AI学习用
```

**reviewer spawn 规范与熔断链（P0-1，v9.7.8 写死）**：
- **spawn 写法**：`Agent(subagent_type="general-purpose", model="reasoning")`——**禁止传 name 参数**（name 参数依赖 team 上下文，本地 automation 环境必失败；08-13 实证去掉 name 后 spawn 成功）
- **熔断链**：spawn 报 team 上下文错误 → 去掉 name 参数重试 1 次 → 仍失败 → **熔断**（本次运行不再尝试 spawn）→ Orchestrator 自审（加载 review_rules.md + review/prompts/ 6 个模板执行 6 维度审校）→ 输出标注「⚠️ 未独立审校」
- **等待策略（P0-2）**：spawn 成功后才进入等待；每 1 分钟轮询检查 `archive/daily/{YYYY-MM-DD}_review.json` 是否生成；reviewer 显式上限 15 分钟（spawn 成功起算）；收到 SendMessage(status=done) 或文件已生成 → 继续；15 分钟未产出 → 按熔断降级（Orchestrator 自审 + 标注）

**效率规范**：网络请求上限3次；版本管理直接在目标文件 Edit；记忆更新合并为1次。

---

## 📝 输出示例

以下为本文 Article 的典型输出结构（以条形码事件为例）：

```markdown
## On This Day | 沙滩上的线条

1974年6月26日 · 美国俄亥俄州特洛伊市

1949年的迈阿密海滩上，一个年轻人用手指在沙地里划出一道道间距不等的条纹。...
（~600-750字叙事，含因果链、关键人物、具体数据）

---

*字数：约750字 | 领域：科技史/商业*
```

**输出规范**：
- **文件名**：`archive/daily/YYYY-MM-DD.md`
- **字数**：500-800 字（推荐 600 字）
- **标题格式**：`# On This Day | [核心意象/双关语]`
- **副标题**：具体日期 + 地点
- **结尾**：`*字数：约N字 | 领域：[主题]*`
- 写完后必须运行 `scripts/sync_check.py` 核验（规则数 155=104+51、版本号、文件路径一致性）

---

## 🤖 多 Agent 执行模式（v9.1）

> **1 Agent spawn 模式**：Orchestrator 亲自选题+写作+精修，只 spawn Reviewer 做独立审校。

| 角色 | 职责 | 阶段 | 加载模块 | 预估 Token |
|------|------|------|---------|:---:|
| **Orchestrator**（Automation 自身） | 选题 + 写作 + 精修 + 输出 + 记忆更新 + 投喂素材准备 | Phase 1-2, 4-9 | 写作阶段: `topic_rules.md` + `writing_core.md` + `rule_index.md` +（按题材）`topics/` 1 个；精修阶段: + `review_rules.md` | 峰值~32K |
| **reviewer**（spawn） | 6维度审校 + 判例检索 | Phase 3 | `review_rules.md` + `review/prompts/*.md` | ~32K |

### Agent 级异常处理

| 场景 | 处理策略 |
|------|---------|
| **spawn 规范** | `Agent(subagent_type="general-purpose", model="reasoning")`——**禁止传 name 参数**（name 依赖 team 上下文，本地 automation 环境必失败；08-13 实证去掉 name 可成功） |
| reviewer spawn 报 team 上下文错误 | 去掉 name 参数重试 1 次 → 仍失败 → **熔断**（本次运行不再尝试 spawn）→ Orchestrator 自审（加载 review_rules.md + review/prompts/ 6 个模板执行 6 维度审校）→ 输出标注「⚠️ 未独立审校」 |
| reviewer 超时（spawn 成功后 15 分钟无响应/未产出） | 按熔断降级：Orchestrator 自审（同上）+ 输出标注「⚠️ 未独立审校」 |
| reviewer 返回空结果 | Orchestrator 重试 1 次，仍为空 → 按熔断降级（Orchestrator 自审 + 标注「⚠️ 未独立审校」） |
| 搜索失败 | 从 TOPICS.md 待写选题列表中选取备用事件 |

### reviewer 等待策略（文件检测优先，v9.7.8）

1. **spawn 成功后才进入等待**；spawn 失败不进入等待，直接走上方熔断链
2. 每 1 分钟轮询检查 `archive/daily/{YYYY-MM-DD}_review.json` 是否已生成（文件检测为主）
3. reviewer 显式上限 **15 分钟**（从 spawn 成功起算）
4. 收到 reviewer SendMessage（status=done）或检测到 review.json 已生成 → 立即继续
5. 15 分钟未产出 → 按熔断降级（Orchestrator 自审 + 输出标注「⚠️ 未独立审校」）

### 迭代终结条件

- 审校通过（P0=0 且 P1≤1）→ 输出文章
- 审校不通过 → Orchestrator 直接修复 → reviewer 重新审校（最多 2 轮）
- 2 轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本
- **防死循环（v9.7.8）**：连续 2 轮审校指向同一 P 级问题且修复无实质改进 → 停止迭代，标记"⚠️ 需人工审核"并输出当前最佳版本

### 消息协议

reviewer → orchestrator：
```json
{ "agent": "reviewer", "status": "done", "file": "archive/daily/{date}_review.json", "p0_count": 0, "p1_count": 0, "pass": true }
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

### 人工审核检查点
在设计上，每次审校通过后的输出前（Phase 3.7）设有一处人工确认检查点。
- **检查点位置**：审校通过 → 待输出前 → 暂停等待 Master
- **触发条件**：文章完成审校，P0=0 且 P1≤1
- **默认行为**：超时（5 分钟）无人工响应 → 自动继续（不阻塞自动化流程）
- **Overrides**：自动化执行时通过 `--force` / Automation prompt 跳过检查点

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

## 规则温控月报
| 指标 | 值 |
|------|-----|
| 总规则数 | 155 (104条规则+51条禁止) |
| hot 规则 | [n] |
| cold 规则 | [n] |
| recovered 规则 | [n] |
| 本月升温数 | [n] |
| 本月降级数 | [n] |
```

| 温控数据 | `review/rule_heat.json` | 全量规则触发记录，机器可读 |

---

## 🔗 关键文件路径

| 文件 | 路径 | 用途 |
|------|------|------|
| 主索引 | `SKILL.md` | 本文件——核心哲学+模块索引+执行流程 |
| 选题规则 | `topic_rules.md` | 评分矩阵+淘汰测试 |
| 写作核心 | `writing_core.md` | 叙事结构+6维工具包+59条hot规则（§5A基础23+§5X通用36）+基础/hot禁止模式+温控表（v9.7.8瘦身：26条cold Forbidden正文与cold状态表已迁 archive） |
| 规则索引 | `rule_index.md` | 155条规则编号+摘要+温控+文件定位 |
| 题材专项 | `topics/nature_disaster.md` `topics/war_institution.md` `topics/tech_engineering.md` | 按题材加载 1 个（17 hot Rule + 7 hot Forbidden） |
| 非强制技法 | `craft_optional.md` | 参悟/心理/命运/节奏词/四AI/镜像/开篇密度/日期（按需Read） |
| 冷规则存档 | `archive/cold_rules.md` | 冷规则正文（29 Rule + 26 Forbidden）+ cold 状态表（v9.7.8 迁入） |
| 审校规则 | `review_rules.md` | 审校表+元规则+Rule 31-88+审校子系统 |
| 审校Prompt | `review/prompts/0*.md` | 6维度深度审校模板 |
| 判例库 | `review/CASE_STUDIES.md` | 51条案例（续号至50+来源附录） |
| 选题历史 | `archive/daily/TOPICS.md` | 已写选题去重 |
| 记忆文件 | `../.workbuddy/memory/MEMORY.md` | 执行记录+系统改造 |
| 温控数据 | `review/rule_heat.json` | 全量规则触发记录，机器可读 |

---

*Version: v9.7.8 | 2026-08-14 | 自动化卡顿优化：①reviewer spawn 规范写死（禁止 name 参数）+ 熔断链 + 文件检测等待策略（P0-1/P0-2）；②模块索引字符数与规则数校准（155=104+51）；③writing_core 冷规则物理瘦身（26 cold Forbidden 正文 + cold 状态表迁 archive/cold_rules.md，75.7K→70.3K，零丢失）；④sync_check.py 一键核验；⑤CASE_STUDIES 只 grep 禁整读；⑥精修防死循环；基于 v9.7.7（北美大停电 L2：Rule 102/103/104）*
