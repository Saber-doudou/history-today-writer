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
| **Phase 2-3 写作** | `writing_core.md` + `rule_index.md` +（按题材）`topics/` 1 个 +（按需）`craft_optional.md` +（按需）`fact_checklist.md` | 核心：叙事结构 + 6维工具包 + 写作标准 + 81条hot规则（core 59 + 题材专项 22，sync_check ⑤ 实跑口径）+ 温控表；索引：186条规则编号+摘要；题材专项×3；非强制技法；写作侧事实核查清单 | 核心~85K + 索引18K + 题材8-16K（+按需12K+4K） |
| Phase 3.5 审校 | `review_rules.md` | P0/P1/P2审校表 + 元规则 + 反馈日志 + Rule 31-77 四AI共性模式（+R111 等 hot 引用，编号见 rule_index）+ 审校子系统 + 标点规范 | ~43K |
| **Phase 3.5 审校** | `review/prompts/` | 6维度深度审校Prompt模板 | ~47K |
| **Phase 3.6 判例** | `review/CASE_STUDIES.md` | 65条案例（续号至65；只Grep命中关键词，禁止整读进上下文） | ~118K |

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
Phase 1: 【加载 topic_rules.md】→ 选题+搜索 → topic_result.json（事件价值矩阵≥18 + 选题淘汰测试，矩阵/测试口径见 topic_rules.md；WebSearch ≤2 次；对照 archive/daily/TOPICS.md 去重；标注题材域 natural_disaster / war_institution / tech_engineering，无则跳过；搜索失败 → TOPICS.md 待写列表 fallback）
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
Phase 3.5: 【加载 review_rules.md + review/prompts/】→ 6维度审校 → review_report.json（实际产物文件名：archive/daily/YYYY-MM-DD_review.json，含 p0/p1/p2 计数、pass、issues 数组、f19_check）
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
Phase 4: 输出（全文 + 执行摘要）——执行摘要须含：候选事件对比评分 / 审校结果 P0/P1/P2 + 审校方式（独立 Reviewer 或自审标注）/ 迭代次数 / 版本号
    ↓
Phase 5: 记忆更新（MEMORY.md 执行记录+质量仪表盘 + TOPICS.md 选题+复盘 + CASE_STUDIES.md 新案例时 + 当日日志 .workbuddy/memory/YYYY-MM-DD.md）
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

以下为本文 Article 的典型输出结构（以条形码事件为例）：

```markdown
## On This Day | 沙滩上的线条

1974年6月26日 · 美国俄亥俄州特洛伊市

1949年的迈阿密海滩上，一个年轻人用手指在沙地里划出一道道间距不等的条纹。...
（~600-750字叙事，含因果链、关键人物、具体数据）

---

（结尾禁加 字数/领域 元信息脚注，F19 已恢复禁止，正文不得输出）
```

**输出规范**：
- **文件名**：`archive/daily/YYYY-MM-DD.md`
- **字数**：500-800 字（推荐 600 字）
- **标题格式**：`# On This Day | [核心意象/双关语]`
- **副标题**：具体日期 + 地点
- **结尾**：意象回扣 + 价值升华双段（R8），**禁加** 字数/领域 元信息脚注（F19 已恢复禁止，正文不得输出）
- 写完后必须运行 `scripts/sync_check.py` 核验（规则数 186=130+56、版本号、文件路径、hot 规则正文完整性）

---

## 审校子进程协议（已收敛，详见上文「Reviewer 独立子进程规范」）

> spawn 规范 / 熔断链 / 等待策略统一见「自动化执行流程」中的「Reviewer 独立子进程规范与熔断链」段（08-13 实证去掉 name 可成功；08-17/18 独立子进程为主路径）。此处仅保留协议细节：

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
1. **多轮修改不达标**：超过 2 轮修改仍不通过，标记为"需人工审核"
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
| 总规则数 | 186 (130条规则+56条禁止) |
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
| 写作核心 | `writing_core.md` | 叙事结构+6维工具包+81条hot规则（core 59 + 题材专项 22，sync_check ⑤ 实跑口径）+基础/hot禁止模式+温控表（v9.7.8瘦身：26条cold Forbidden正文与cold状态表已迁 archive） |
| 规则索引 | `rule_index.md` | 186条规则编号+摘要+温控+文件定位 |
| 题材专项 | `topics/nature_disaster.md` `topics/war_institution.md` `topics/tech_engineering.md` | 按题材加载 1 个（题材专项 hot 22 条，sync_check ⑤ 口径） |
| 非强制技法 | `craft_optional.md` | 参悟/心理/命运/节奏词/四AI/镜像/开篇密度/日期（按需Read） |
| 事实核查清单 | `fact_checklist.md` | 写作侧事实核查（P0/P1/P2 逐项：核查项→怎么做→通过标准→失败动作，按需Read） |
| 冷规则存档 | `archive/cold_rules.md` | 冷规则正文（29 Rule + 26 Forbidden）+ cold 状态表（v9.7.8 迁入） |
| 审校规则 | `review_rules.md` | 审校表+元规则+Rule 31-77（四AI共性）+审校子系统 |
| 审校Prompt | `review/prompts/0*.md` | 6维度深度审校模板 |
| 判例库 | `review/CASE_STUDIES.md` | 65条案例（续号至65） |
| 选题历史 | `archive/daily/TOPICS.md` | 已写选题去重 |
| 选题索引 | `archive/daily/选题索引.md` | 纯选题两列视图（运行日期\|选题名），Phase 5b 从 TOPICS.md 选题复盘块重建 |
| 记忆文件 | `../.workbuddy/memory/MEMORY.md` | 执行记录+系统改造 |
| 温控数据 | `review/rule_heat.json` | 全量规则触发记录，机器可读 |

---

*Version: v9.9.4 | 2026-09-05（Google成立 L2：新增 Rule 130 标题具象钩子正文兑现（ds+ima+豆包 3/4）+ Forbidden #56 无出处推测套话（ds+豆包 2/4），184→186=130+56）；基于 v9.8.13 | 2026-09-03（瑞典换边 Dagen H L2：新增 Rule 128 外文代号须点明并解释含义（ds+ima 2/4）+ Rule 129 反直觉好结果须补达成机理（ds+ima+豆包 3/4），182→184=129+55）；基于 v9.8.12 | 2026-09-02（清廷废科举 L2：新增 Rule 127 群体反应绝对化 + Forbidden #55 半截隐喻悬置，180→182=127+55）；基于 v9.8.11 | L1 自动化流程新增 Phase 2.5 标题复审（与 L2 对齐）；德国入侵波兰 L2（2026-09-01）：新增 R120 殖民时长精度/R121 宗主国动机多因/R122 去殖民武装抗争呼应（去殖民专项，均 2/4 共识），173→176（122+54）；基于 v9.8.8（第一架喷气式飞机首飞 L2：新增 Rule 118（正文避免插入面向读者的说教式过渡/纠正认知闲笔，P2，IMA+豆包 2/4 指出 v1 中段"今天的大多数旅客大概以为…"说教过渡打断节奏）+ Rule 119（同一人物/机构身份与归属表述须全文事实自洽，P1，DS+IMA+豆包 3/4 指出 v1 瓦西茨"空军部指派"与"绕开空军部"矛盾）+ Forbidden #54（克制无法验证的反事实英雄叙事断言，P2，豆包 1/4 独家指出 v1 "赌上私财绕过僵化军方体系"为反事实+主观断言），170→173 条（119+54）；基于 v9.8.7（喀拉喀托 L2 学习：新增 Rule 117（多强钩子标题双钩，P2，千问+豆包 2/4 指出原标题只点声音线），169→170 条（117+53）；巴黎解放 L2 学习：新增 Rule 115（受降/签字多地点流程区分，P0，ima+豆包 2/4 指出 v1 误将蒙帕纳斯车站列入受降签字地，实为戴高乐抵达地；正文附 writing_core.md）+ Rule 116（象征性细节主体存疑时模糊化，P2，豆包 1/4 独家指出埃菲尔铁塔升旗主体非消防队员、各源不一），167→169 条（116+53）；v2 吸收：受降流程修正（默里斯=投降地→警察总局=签字地，蒙帕纳斯改戴高乐抵达，P0）、补 8-19 起义规模与戴高乐政治博弈（ds+千问+豆包 3/4）、吸收"Brennt Paris?"题眼（ima 独家）、升旗主体模糊化（豆包独家）、补军事困境铺垫（豆包独家）、理顺时间线（豆包独家）、修复错字"让历史意外选择"缺"的"（ima 独家）；基于 v9.8.5（庞贝 L2 学习：新增 Rule 114，166→167，hot 68→69）；基于 v9.8.4（伽利略望远镜 L2：新增 Rule 113，165→166，hot 67→68）；基于 v9.8.3（布拉格之春 L2：新增 Rule 112 + Forbidden #53，163→165，hot 66→67）；基于 v9.8.2（达盖尔银版摄影法 L2：新增 Rule 111，162→163，hot 65→66）；基于 v9.8.1（妇女选举权 L2：Rule 108/109/110 + Forbidden #52，158→162，hot 62→65）；基于 v9.8.0（伊兹米特地震 L2：Rule 105/106/107，155→158）；基于 v9.7.9（全量审查修复：sync_check 崩溃/假阳性修复 + hot 正文完整性 + Rule97 去重 + 文档索引批量修正）；基于 v9.7.8（自动化卡顿优化：spawn 规范写死/熔断链/文件检测等待/冷规则瘦身/sync_check 一键核验/CASE_STUDIES 只 grep 禁整读/精修防死循环）；2026-08-26 增补 Phase 5b 选题索引（archive/daily/选题索引.md，两列：运行日期|选题名，数据源 TOPICS.md 选题复盘块，每次运行重建；Automation prompt Phase 6b 同步；版本号不变仍 v9.8.6）；基于 v9.8.9（马来亚独立 L2：新增 R120-122，规则 173→176）；2026-09-01 德国入侵波兰 L2：新增 Rule 123（落败方须见实际抵抗与装备对比，P1）+ Rule 124（冲击性事实点须具象细节或收紧措辞，P1）+ Rule 125（战术名词点明机械运作链条，P2）+ Rule 126（落败方决策须交代背景去事后评判腔，P2），176→180（126+54）*

> 注：v9.7.7 的规则（R102/103/104）与 v9.7.8 优化同批提交于 1c92cb9，git 历史无独立 v9.7.7 提交。
