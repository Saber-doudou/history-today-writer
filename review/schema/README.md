# review/schema — 契约说明（2026-10-22）

## 唯一契约

`review_output.v2.json` 是 `review.json` 的唯一契约，字段与运行时实际产物对齐。

核心必填（所有新产物）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | `YYYY-MM-DD` |
| `p0_count` / `p1_count` / `p2_count` | integer ≥ 0 | 三级问题计数 |
| `pass` | boolean | 是否通过 |
| `issues` | array | 问题列表，每项含 `id/category/severity/location/current/suggested/reason` |

推荐字段（`--strict` 时必填）：

| 字段 | 取值 | 说明 |
|------|------|------|
| `independence` | `cross_family` / `same_family` / `self_review` / `mixed` | 审校独立性等级 |
| `reviewer_model` | string | 审校模型标识，用于复现 |

## 兼容文件

`review_output.json`（v1）已标记 `deprecated`，只为 `sync_check` 的路径可达性检查保留，v10.3.8 移除。不要再用它校验新产物。

## 校验

```bash
python eval/validate_review.py            # 最近 10 份，核心字段
python eval/validate_review.py --strict   # 最近 10 份，核心 + 推荐字段
python eval/validate_review.py --all      # 全部归档
```

退出码：0 全过；1 有失败；2 参数错误。

## 首次测量（2026-10-22）

97 份归档中，按新契约核心字段通过 9 份，合规率 9.3%。主要缺口：`date` 缺失 71 份，P0/P1/P2 缺失 60 份，`pass` 缺失 53 份，issue 子字段缺失 25 至 44 份，`location` 不符合 `P{n}` 格式 117 处。

这是「向新契约迁移」的起点，不是历史数据全部错误。旧文件保留原样，不回改；新产物从 v10.3.8 起按 v2 输出。
