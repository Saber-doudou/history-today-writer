# eval — 优化基线、回归与金标准

本目录是 D0「基线冻结」产物，用于后续每个优化单元（OU）的「改前 / 改后」对比与棘轮决策。

## 文件

| 文件 | 用途 |
|------|------|
| `baseline_20261022.json` | 系统基线：上下文规模、审校质量、规则容量、交付链、资产规模 |
| `l2_errors_2026Q4.json` | 近 10 期 L2 事实纠错清单，作为「P0 逃逸率」的分母与金标准弱标签 |
| `golden_set.json` | 金标准集 20 篇候选，题材均衡，后续人工标注 P0/P1 |
| `results_system.tsv` | 每个 OU 的 before/after 与 keep/revert 记录（D1 起追加） |
| `check_delivery.py` | 交付链三检：工作区、版本号、远端一致性 |
| `snapshot.py` | 技能目录与日更目录双 zip 快照，manifest 含 sha256 |
| `validate_review.py` | review.json 契约校验（JSON Schema 子集，stdlib） |
| `verify_claims.py` | 正文数字与 claims 账本对账，输出覆盖率与未匹配项 |
| `tests/` | unittest，覆盖契约校验与 claims 解析 |
| `reports/` | 一次性测量报告（契约合规、claims 基线、自测输出） |

## 纪律

1. 基线只读。冻结后不因「看起来不好看」改数；发现口径错误另开 `baseline_correction` 记录。
2. 缺失数据标 `unknown`，不估算填充。
3. L2 学习总结的分级不统一，`p0_declared` / `p1_declared` 仅在原文明确标注时填写；`normalized_factual_count` 是事实类条目计数，用于趋势，不用于绝对判定。
4. 金标准集只放候选，标注前不得作为 recall 分母。
