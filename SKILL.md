---
name: "history-today-writer"
title: "history-today-writer"
summary: "On This Day — narrative-driven historical storytelling skill for WorkBuddy. 适用：'On This Day' 历史微文（500-800字）写作/自动化。不适用：非历史叙事任务（如新闻、攻略、技术文档），此类任务勿触发。"
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

> **计数口径说明**：所有规则数 / Forbidden 数 / 文件体积声称值，一律以 `scripts/sync_check.py` 实跑结果为准（提及并集口径）；声称值如有出入（如 cold 29 条含 7 个幽灵编号 24-30 无正文、hot 84 vs 索引 83 差 1 来自 R97 指针头），以校验脚本为权威。

| 阶段 | 加载文件 | 内容 | 字符数 |
|------|---------|------|-----------|
| **Phase 1 选题** | `topic_rules.md` | 事件价值矩阵评分 + 选题淘汰测试 | ~1.9K |
| **Phase 2-3 写作** | `writing_core.md` + `rule_index.md` +（按题材）`topics/` 1 个 +（按需）`craft_optional.md` +（按需）`fact_checklist.md` | 核心：叙事结构 + 6维工具包 + 写作标准 + 90条hot规则（core 70 + 题材专项 20，sync_check ⑤ 实跑口径）+ 温控表；索引：199条规则编号+摘要；题材专项×3；非强制技法；写作侧事实核查清单 | 核心~85K + 索引18K + 题材8-16K（+按需12K+4K） |
| Phase 3.5 审校 | `review_rules.md` | P0/P1/P2审校表 + 元规则 + 反馈日志 + Rule 31-77 四AI共性模式（+R111 等 hot 引用，编号见 rule_index）+ 审校子系统 + 标点规范 | ~43K |
| **Phase 3.5 审校** | `review/prompts/` | 6维度深度审校Prompt模板 | ~47K |
| **Phase 3.6 判例** | `review/CASE_STUDIES.md` | 96条案例（续号至96；只Grep命中关键词，禁止整读进上下文） | ~131K |

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
Phase 1: 【加载 topic_rules.md】→ 选题+搜索 → topic_result.json（事件价值矩阵≥18 + 选题淘汰测试，矩阵/测试口径见 topic_rules.md；WebSearch ≤2 次；查重跑 `python scripts/check_topic.py --angle "{选题名}"`（机械校验，替代整读 TOPICS.md：退出码 0=通过 / 1=重复需换候选（角度区提示：确认写作角度不同可人工放行）/ 2=参数错误；脚本三源索引=TOPICS.md 表格+复盘块+全部日更文章216篇，覆盖率100%，历史回归硬误杀0/漏放0，口径漂移时跑 `--self-test` 复验）；标注题材域 natural_disaster / war_institution / tech_engineering，无则跳过；搜索失败 → TOPICS.md 待写列表 fallback）
    ↓
Phase 2: 【加载 writing_core.md + rule_index.md】→ 写作+自检 → draft.md（⚠️ 写作阶段不加载审校侧规则文件，保持「不知道考纲」隔离；按 core 写 500-800 字推荐 600，Humanizer 去 AI 味 + Forbidden 逐条自检 → 写入 archive/daily/YYYY-MM-DD.md）
    ↓
Phase 2.5: 标题复审（强制，不可跳过，与 L2 feed-learning Phase 2.5 同款约束）
    - 写作定稿前，显式复审当前标题：套用 R38（不剧透最大悬念）/ R117（标题双钩）/ 首尾意象咬合
    - 若标题莫名其妙 / 无钩子 / 反讽双关模糊（读者一眼不懂反转逻辑），重拟为「设问+明确钩子」或「直揭底」
    - 红线：中外历史类比（如卢沟桥事变之于假旗事件）仅用于理解共鸣，禁止写入正文（政治敏感规避项）
    ↓
Phase 3: Phase 2内置 — Humanizer + P0复检
    ↓
Phase 3.5: 【加载 review_rules.md + review/prompts/】→ 6维度审校 → review_report.json（实际产物文件名：archive/daily/YYYY-MM-DD_review.json，字段名固定 `p0_count`/`p1_count`/`p2_count`（计数）、`pass`、`issues` 数组、`f19_check`，与 review/schema/review_output.json 一致；P0/P1 修复被吸收后补 `fix_applied: true` 回流字段，P2 以 note 记录不强制修复）
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
Phase 4: 输出（全文 + 执行摘要）——执行摘要须含：候选事件对比评分 / 审校结果 P0/P1/P2 + 审校方式（独立 Reviewer 或自审标注）/ 迭代次数 / 版本号 / 宿主状态 / 运行模型 / 终版字数（以实测计并注明汉字口径；防摘要自报与落盘文本不符）
    ↓
Phase 5: 记忆更新（MEMORY.md 执行记录+质量仪表盘 + TOPICS.md 选题+复盘 + CASE_STUDIES.md 新案例时 + 当日日志 .workbuddy/memory/YYYY-MM-DD.md + 执行摘要写入权威 automation memory `.workbuddy/memory/automations/automation-1778209807842/memory.md`——唯一权威路径（2026-09-07 A2 统一），旧 `.workbuddy/automations/` 已废弃禁写，L3 侧由 l3_publish Phase 7b 同指此路径）
    ↓
Phase 5b: 选题索引重建（2026-08-26 新增）→ 写 archive/daily/选题索引.md（纯选题两列：运行日期 | 选题名；数据源 = TOPICS.md 全部「选题复盘」块标题；按运行日期倒序；每次运行重建，保证与 TOPICS.md 一致、无重复行；文件头注明仅收录有结构化选题记录的日期，更早无选题记录的旧文不纳入）
    ↓
Phase 5c: 冷热迁移对账（2026-08-26 新增，v0.1）→ 在技能目录运行 `python scripts/migrate_cold_rules.py --dry-run`（默认仅报告不搬运；出现 ① 建议降级候选或 ③ 新增冲突项 → 记录并提示 Master；`--force` 由 Master 明确指示后手动执行）。规则正文冷热迁移方案见 docs/rule-cold-migration-plan.md（定稿 v1.1）；L2 学习侧对应 feed-learning Phase 8
    ↓
Phase 6: 投喂素材准备（创建 投喂素材/YYYYMMDD/ + 8个空txt：ds.txt / ds点评优化.txt / ima.txt / ima点评优化.txt / 千问.txt / 千问点评优化.txt / 豆包.txt / 豆包点评优化.txt）→ 四AI学习用
```

**Reviewer 独立子进程规范与熔断链（P0-1，v9.8.3 收敛，08-18 起不依赖 team）**：
- **spawn 写法**：`Agent(subagent_type="general-purpose", model="reasoning")`——**禁止传 name 参数**（name 参数依赖 team 上下文，本地 automation 环境必失败；08-13 实证去掉 name 后 spawn 成功）
- **熔断链**：spawn 报 team 上下文错误 → 去掉 name 参数重试 1 次 → 仍失败 → **熔断**（本次运行不再尝试 spawn）→ Orchestrator 自审（加载 review_rules.md + review/prompts/ 6 个模板执行 6 维度审校）→ 输出标注「⚠️ 未独立审校」
- **等待策略（P0-2）**：spawn 成功后才进入等待；每 1 分钟轮询检查 `archive/daily/{YYYY-MM-DD}_review.json` 是否生成；reviewer 显式上限 15 分钟（spawn 成功起算）；收到 SendMessage(status=done) 或文件已生成 → 继续；15 分钟未产出 → 按熔断降级（Orchestrator 自审 + 标注）

**效率规范**：网络请求上限3次；版本管理直接在目标文件 Edit；记忆更新合并为1次。

---

## 📝 输出示例

以下为输出结构模板（叙事范文见 `archive/daily/` 近年篇目，按「具体反常细节」标题谱系取近期 10 篇对照）：

```markdown
# On This Day | [核心意象/双关标题，不剧透最大悬念]

YYYY年M月D日 · [国家/城市]

[约 600 字叙事：具体场景切入 → 因果链 → 关键人物 → 具体数据；结尾禁加字数/领域元信息脚注（F19）]
```

**输出规范**：
- **文件名**：`archive/daily/YYYY-MM-DD.md`
- **字数**：500-800 字（推荐 600 字）
- **标题格式**：`# On This Day | [核心意象/双关语]`
- **副标题**：具体日期 + 地点
- **结尾**：意象回扣 + 价值升华双段（R8），**禁加** 字数/领域 元信息脚注（F19 已恢复禁止，正文不得输出）
- 写完后必须运行 `scripts/sync_check.py` 核验（24 项门禁：规则数 199=146+53、版本号五处一致、文件路径可达、hot 规则正文完整性、prompt 一致性 ⑦⑨、记忆体积 ⑧⑭、元数据 ⑩⑪、分片新鲜度 ⑫、IMA 收据 ⑬）

---

## 审校子进程协议（已收敛，详见上文「Reviewer 独立子进程规范」）

> spawn 规范 / 熔断链 / 等待策略统一见「自动化执行流程」中的「Reviewer 独立子进程规范与熔断链」段（08-13 实证去掉 name 可成功；08-17/18 独立子进程为主路径）。此处仅保留协议细节：

### 迭代终结条件

- 审校通过（P0=0 且 P1≤1）→ 输出文章
- **P2 不阻塞（2026-09-07，防 critic 空转）**：P2 级项不强制修复，记为 note；Reviewer 输出达标时**允许 pass=true 且 issues 为空**，禁止为凑条目虚构 P2（Snorkel Self-Critique Paradox：高基线任务上自批评易幻觉缺陷，98% 基线叠自评会掉到 57%）
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
1. **多轮修改不达标**：超过 2 轮修改仍不通过，标记为"需人工审核"
2. **选题冲突**：自动选择下一个高分选题
3. **Token 超限**：精简内容，优先保证核心叙事

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
| 总规则数 | 199 (146条规则+53条禁止) |
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
| 写作核心 | `writing_core.md` | 叙事结构+6维工具包+90条hot规则（core 70 + 题材专项 20，sync_check ⑤ 实跑口径）+基础/hot禁止模式+温控表（v9.7.8瘦身：26条cold Forbidden正文与cold状态表已迁 archive） |
| 规则索引 | `rule_index.md` | 199条规则编号+摘要+温控+文件定位 |
| 题材专项 | `topics/nature_disaster.md` `topics/war_institution.md` `topics/tech_engineering.md` | 按题材加载 1 个（题材专项 hot 20 条，sync_check ⑤ 口径） |
| 非强制技法 | `craft_optional.md` | 参悟/心理/命运/节奏词/四AI/镜像/开篇密度/日期（按需Read） |
| 事实核查清单 | `fact_checklist.md` | 写作侧事实核查（P0/P1/P2 逐项：核查项→怎么做→通过标准→失败动作，按需Read） |
| 冷规则存档 | `archive/cold_rules.md` | 冷规则正文（29 Rule + 26 Forbidden）+ cold 状态表（v9.7.8 迁入） |
| 审校规则 | `review_rules.md` | 审校表+元规则+Rule 31-77（四AI共性）+审校子系统 |
| 审校Prompt | `review/prompts/0*.md` | 6维度深度审校模板 |
| 判例库 | `review/CASE_STUDIES.md` | 96条案例（续号至96） |
| 选题历史 | `archive/daily/TOPICS.md` | 已写选题人类可读视图（LLM 不再整读） |
| 查重脚本 | `scripts/check_topic.py` | Phase 1 选题查重（三源索引+退出码0/1/2，--self-test 全量回归） |
| 选题索引 | `archive/daily/选题索引.md` | 纯选题两列视图（运行日期\|选题名），Phase 5b 从 TOPICS.md 选题复盘块重建 |
| 记忆文件 | `../.workbuddy/memory/MEMORY.md` | 执行记录+系统改造 |
| 温控数据 | `review/rule_heat.json` | 全量规则触发记录，机器可读 |

---

*Version: v10.3.6 | 2026-10-20 | 逐版变更流水已完整收录于 CHANGELOG.md（含 v10.1.6 至 v10.2.6 全量逐版记录），本文件不再重复，版本纪律与逢十进位规则见 MEMORY.md 运维速记*

> 注：v9.7.7 的规则（R102/103/104）与 v9.7.8 优化同批提交于 1c92cb9，git 历史无独立 v9.7.7 提交。
