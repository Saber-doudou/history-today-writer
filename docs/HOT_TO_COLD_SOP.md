# HOT → COLD 手工降级 SOP

> **适用场景**：规则库 `hot 90/90` 触顶，L2 需要新增 hot 规则必须先做「等价减法」腾位。
> **为什么是手工**：`migrate_cold_rules.py --force` 的搬运实现从未写过（v0.1 只做四区对账），2026-11-10 已改为**显式拒绝**（传入即 `exit 2`）。降级动作要动规则正文，属于最高风险操作，不走自动化。
> **决策依据**：Master 2026-11-10 选 D3-A（先手工，后续确有连续降级需求再做脚本化）。

---

## 0. 必须先理解的机制

| 概念 | 实际口径 | 容易误判的点 |
|---|---|---|
| `hot 90/90` 怎么算 | `sync_check.py`：`hot_now = core_actual + topics_actual`，即**正文文件里实际有多少条规则** | 改 `rule_heat.json` 的 `status` 字段**不会**让 hot 数下降 |
| 降级的本质 | 把规则**正文**从 `writing_core.md` / `topics/*.md` 移出，追加到 `archive/cold_rules.md` | 只改索引不改正文 = 数据分裂，⑥ 三向一致会红 |
| 规则总数 | 199 = 146 Rule + 53 Forbidden，**降级不减少总数** | 降级是「搬家」不是「删除」 |
| `rule_index` 两列 | 「温控」列（hot/cold 状态）+「文件」列（正文落点：core / war / tech / nat / cold） | 两列都要改，只改一列会触发 ⑥ |

---

## 1. 前置闸（不满足就不许降）

```
python scripts/migrate_cold_rules.py --dry-run
```

看 ① 区（建议降级候选）是否列出该规则。双闸条件：

- **闸 A**：`max(last_triggered, last_issue)` 距今 ≥ 60 天（`null` 视为超期）
- **闸 B**：`demoted_at` 距今 ≥ 30 天（从未 demote 视为满足）

再查三项否决条件：

1. `never_cool == true` → **禁止降级**（永不降级集合）
2. P0 级规则 → **禁止降级**（设计文档规定 P0 永不降级，⑥ 会报「P0 却 cold」）
3. 该规则是某条 hot 规则的唯一承载（删了会留下无约束的空缺）→ 先合并再降

> ⚠️ **② 区曾因 bug 误报，已于 2026-11-10 修复**：`scan_rule_blocks` 原先不识别 Rule 的「cold 占位」，导致已降级规则（如 Rule50，`demoted_at=2026-10-13`、正文在 `archive/cold_rules.md §1.21`、hot 区只留一行占位说明）被判为 hot 正文，进而报成「未满阈值候补、预计 2026-11-12 达标」。新增 `_is_cold_placeholder()` 后 ② 区已归零。
> **记法**：Rule 侧现在与 Forbidden 侧一致，都识别占位（Forbidden 用「（cold）」标记，Rule 用标题后首个引用块含「cold 占位」）。若 ② 区再出现条目，按真实候补处理，但降级决策仍**一律以 ① 区为准**。

---

## 2. 操作步骤

### 2.1 建 checkpoint（动正文前必做）

技能目录是 git 仓库，先落一个干净提交或记录当前 commit：

```
cd C:/Users/admin/.workbuddy/skills/history-today-writer
git status --porcelain        # 必须为空，否则先处理
git rev-parse HEAD            # 记下这个 sha，回滚用
```

### 2.2 定位正文

查 `rule_index.md` 中该规则行，确认「文件」列：

```
| R50 | 科 | 专 | P2 | cold | cold | 轨距/制式等选型不可遗漏（2026-10-13 C2 双判据淘汰） |
                            ↑温控  ↑文件
```

正文落点对应：

- `core` → `writing_core.md`
- `war` / `tech` / `nat` → `topics/` 下对应文件
- 已在 `cold` → **已经降过了，不要重复操作**

在该文件中搜索 `### Rule {NN}`（或该文件实际的规则标题格式），确认起止边界：从该行开始，到**下一个同级 `###` 标题之前**为止。

### 2.3 摘出正文（不要手打）

用脚本按行号切片，避免手抄引入错字：

```
python - <<'PY'
from pathlib import Path
p = Path("writing_core.md")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
start = next(i for i, l in enumerate(lines) if l.startswith("### Rule 50"))
end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("### "))
print("".join(lines[start:end]))
PY
```

把输出**原样**留存，下一步要用。

### 2.4 追加到 cold_rules.md

在 `archive/cold_rules.md` 的「## 一、冷 Rules」区末尾追加，格式照现有条目：

```
### 1.{下一个序号} Rule {NN}（正文源自 {原文件}）
### Rule {NN}. {原标题}（{原级别}）
{正文，逐字保留}
```

同时把章节标题的条数 +1：`## 一、冷 Rules（28 条）` → `（29 条）`。

### 2.5 从原文件删除正文

按 2.2 确认的起止边界整段删除（含该 `###` 标题行，不含下一个 `###`）。

**只删这一段，不要顺手改别的。** 删完立刻确认：

```
python -c "
from pathlib import Path
t = Path('writing_core.md').read_text(encoding='utf-8')
print('残留检查:', 'Rule 50' in t)
"
```

### 2.6 改 rule_heat.json

该规则对象改两个字段，其余保留：

```json
"status": "cold",
"demoted_at": "YYYY-MM-DD"
```

- `last_triggered` / `count_30d` / `last_issue` **保持不变**（降级不改历史触发记录）
- 不要动 `never_cool`

### 2.7 改 rule_index.md

同一行改两列：
- 「温控」列：`hot` → `cold`
- 「文件」列：`core`（或 `war`/`tech`/`nat`）→ `cold`
- 「摘要」列：压成 1 行，末尾补降级原因，如 `（2026-XX-XX 双判据淘汰）`

### 2.8 验证（缺一不可）

```
python scripts/sync_check.py
```

必须 **24/24**，重点看：

- **①** 规则行数仍为 146 Rule / 53 Forbidden（降级不改总数）
- **⑤** hot 规则正文完整性（删正文后不应报缺失）
- **⑥** rule_heat ↔ rule_index ↔ 正文落点三向一致

再确认 ① 区已不再列该条：

```
python scripts/migrate_cold_rules.py --dry-run
```

最后确认 hot 数已下降：

```
python scripts/sync_check.py | grep "规则数监管"
```

---

## 3. 回滚

任一步出错，按 checkpoint 回滚：

```
git checkout -- writing_core.md
git checkout -- archive/cold_rules.md
git checkout -- review/rule_heat.json
git checkout -- rule_index.md
python scripts/sync_check.py      # 应回到 24/24
```

若已 commit，用 `git revert`，**不要** `reset --hard`（会丢其他未提交改动）。

---

## 4. 已知坑

| 坑 | 表现 | 规避 |
|---|---|---|
| 只改 `rule_heat` 不改正文 | hot 数不变，⑥ 报落点不一致 | 记住 hot 数是数正文条数 |
| 删正文时多删一个 `###` | 相邻规则被吞，① 行数减少 | 用行号切片，不按「感觉」找边界 |
| 忘记改 `cold_rules.md` 章节条数 | 文档内部数字与实际条目不符 | 2.4 最后一步补 |
| P0 规则被降 | ⑥ 报「P0 却 cold」 | 前置闸第 2 项先查级别 |
| 用 `--force` 想省事 | `exit 2` 拒绝 | 该参数已永久停用 |
| ② 区误报当依据 | 对已 cold 的规则重复操作 | 只认 ① 区 |

---

## 5. 变更记录

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-11-10 | 建档。明确 hot 数口径、手工六步、回滚与已知坑 | Master 决策 D3-A；`--force` 同日改为显式拒绝 |
