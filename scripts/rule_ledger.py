#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rule_ledger.py — 规则触发台账（2026-10-13 瘦身治理 B2，C2 双判据的数据基础）

背景：rule_heat.json 的 count_30d 字段语义不可信（多条 last_triggered 在窗口外但 count>0），
「89.9% 近 30 天零触发」是估算。本脚本用 review.json 的 issues[].rule 实测引用重建台账，
替代 rule_heat 的不可信口径，作为 C2「ledger 零触发 + 一句话失败模式测试」双判据的第一判据。

数据源（只读）：
  archive/daily/*_review.json 的 issues[].rule 字段（L1 审校实测引用，含规则编号文本）
  CHANGELOG.md 全文的规则编号引用（L2 学习实测引用：「已由 RX 覆盖」「新增 Rule N」等，
      修正 v1 盲区：元规则类如 R42 在 L1 必然零触发，但其价值在 L2 学习侧大量体现）
  review/rule_heat.json 的 status / last_triggered（温控声称，仅作对照列）

⚠️ 口径纪律（2026-10-13 C2 方法论，违反会误杀）：
  1. Forbidden 类零触发语义反转：F 生效=没犯（零触发是防线起效的证据），
     Forbidden 零触发**不得**作为删除依据；本脚本 --zero-only 默认排除 forbidden_*，
     仅 Rule 进入候选。
  2. Rule 零触发也只是「第一判据候选」：Rule 生效=审校没问题=不出现，
     0 触发不能区分「死规则」与「正是它把问题压到 0 的规则」，
     必须再过第二判据（一句话失败模式测试：能否说清防什么，且不与既有规则重叠）。

口径备注（2026-10-13 T2 取证结论，3 行）：
  - 漂移计数默认口径 = 全量双口径（L1 review + L2 CHANGELOG），B2 时点（未加 L2 扫描）纯 L1 口径为 19（分支1=17+分支2=2，已复现）；两者差 87 为 L2 口径增量，非数据错误，四组 --since 窗口（106/62/33/27）均不复现 19。
  - drift 判定三个分支均要求「实测与 heat 至少一方非空」：分支1 实测有+heat 有不一致 / 分支2 实测有+heat 缺 / 分支3 heat 有+实测零（A1 新增，heat 口径不可信的最强信号）。
  - 零触发 Rule 计数全量与 --zero-only 同口径（均排除 Forbidden），A2 起统一。

输出（stdout）：
  1. 总览：review.json 解析数 / 语法错误跳过数 / 实测触发规则数 / 零触发规则数
  2. 触发台账（按实测次数倒序）：编号 | hot/cold | 实测次数 | 实测最后触发 | heat声称最后触发 | 一致性
  3. 零触发名单（C2 候选）：实测 0 触发的 hot 规则编号清单
  4. 声称漂移警示：三类形态——实测与 heat 均非空但不一致 / 实测有而 heat 缺记录 / heat 有而实测零引用

用法：
  python rule_ledger.py                # 全量台账
  python rule_ledger.py --zero-only    # 只输出零触发名单（C2 圈选用）
  python rule_ledger.py --since 2026-06-01  # 只统计该日期之后的 review.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent  # 技能根目录（scripts/ 的上级）
DAILY_DIR = Path("F:/WorkBuddy/history-today/archive/daily")
HEAT_FILE = SKILL_DIR / "review" / "rule_heat.json"
CHANGELOG = SKILL_DIR / "CHANGELOG.md"


def extract_rule_ids(rule_text: str) -> list[str]:
    """从 issue.rule 文本提取规则编号，统一为 rule_NN / forbidden_NN 形态。

    兼容历史形态：'Rule 37' / 'R13' / 'Forbidden #19' / 'F19' / 'Forbidden #58'。
    """
    ids = []
    for m in re.finditer(r'(?:Rule|R)\s*#?\s*(\d{1,3})', rule_text):
        ids.append(f"rule_{int(m.group(1)):02d}")
    for m in re.finditer(r'(?:Forbidden|F)\s*#?\s*(\d{1,3})', rule_text):
        ids.append(f"forbidden_{int(m.group(1)):02d}")
    return ids


def load_changelog_refs(since: str | None) -> dict[str, list[str]]:
    """扫描 CHANGELOG.md 的规则编号引用（L2 学习口径）。

    匹配形态：'新增 Rule N' / 'R42' / 'Rule 143' / 'F19' 等；日期取所在版本条目日期。
    """
    refs: dict[str, list[str]] = {}
    if not CHANGELOG.exists():
        return refs
    cur_date = "?"
    for line in CHANGELOG.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^##\s+v[\d.]+\s*\|\s*(2026-\d{2}-\d{2})', line)
        if m:
            cur_date = m.group(1)
            continue
        if since and cur_date != "?" and cur_date < since:
            continue
        for rid in extract_rule_ids(line):
            refs.setdefault(rid, []).append(cur_date)
    return refs


def load_review_refs(since: str | None) -> tuple[dict, list[str], int]:
    """扫描全部 review.json，返回 ({rule_id: [dates]}, 解析失败文件列表, 总issue数)"""
    refs: dict[str, list[str]] = {}
    broken: list[str] = []
    total_issues = 0
    for f in sorted(DAILY_DIR.glob("*_review.json")):
        date = f.name[:10]
        if since and date < since:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            broken.append(f.name)
            continue
        for issue in data.get("issues", []) or []:
            total_issues += 1
            # 兼容两种历史形态：dict（含 rule 字段）与纯字符串
            rule_text = issue.get("rule", "") if isinstance(issue, dict) else str(issue)
            for rid in extract_rule_ids(str(rule_text)):
                refs.setdefault(rid, []).append(date)
    return refs, broken, total_issues


def main() -> int:
    ap = argparse.ArgumentParser(description="规则触发台账（review.json 实测口径）")
    ap.add_argument("--since", default=None, help="只统计该日期(YYYY-MM-DD)之后的 review.json")
    ap.add_argument("--zero-only", action="store_true", help="只输出零触发 hot 规则名单（C2 圈选）")
    args = ap.parse_args()

    refs, broken, total_issues = load_review_refs(args.since)
    cl_refs = load_changelog_refs(args.since)
    # 合并双口径：L1 review 实测 + L2 CHANGELOG 引用（后者补元规则类盲区）
    for rid, dates in cl_refs.items():
        refs.setdefault(rid, []).extend(dates)
    cl_total = sum(len(v) for v in cl_refs.values())

    heat: dict = {}
    if HEAT_FILE.exists():
        heat = json.loads(HEAT_FILE.read_text(encoding="utf-8")).get("rules", {})

    print(f"[ledger] review.json 解析: {len(list(DAILY_DIR.glob('*_review.json')))} 个文件, "
          f"语法错误跳过 {len(broken)} 个{('：' + ', '.join(broken)) if broken else ''}")
    print(f"[ledger] 实测 issue 总数: {total_issues}（L1 review 口径）；CHANGELOG 规则引用 {cl_total} 处（L2 口径）；"
          f"合并后实测触发规则数: {len(refs)}")

    if args.zero_only:
        # Forbidden 零触发语义反转（防线起效），默认排除，仅 Rule 进候选
        zero_hot = [rid for rid, h in heat.items()
                    if h.get("status") == "hot" and rid not in refs and rid.startswith("rule_")]
        print(f"[ledger] 实测 0 触发的 hot Rule {len(zero_hot)} 条（C2 候选第一判据；Forbidden 已按口径纪律排除）:")
        print("  " + ", ".join(sorted(zero_hot)) if zero_hot else "  （无）")
        return 0

    # 全量台账（按实测次数倒序）
    rows = []
    for rid in sorted(set(list(refs.keys()) + list(heat.keys()))):
        dates = refs.get(rid, [])
        measured = len(dates)
        last_measured = max(dates) if dates else None
        h = heat.get(rid, {})
        status = h.get("status", "?")
        last_heat = h.get("last_triggered")
        drift = ""
        if last_measured and last_heat and last_measured != last_heat:
            drift = f"⚠️漂移(heat={last_heat})"
        elif last_measured and not last_heat:
            drift = "⚠️heat缺记录"
        elif last_heat and not last_measured:
            drift = "⚠️heat独有(实测0)"  # A1 新增：heat 声称有触发但实测零引用（R50 降级前即此形态）
        rows.append((measured, rid, status, last_measured or "-", last_heat or "-", drift))

    rows.sort(key=lambda r: -r[0])
    print(f"\n[ledger] 触发台账 Top 30（编号 | 状态 | 实测次数 | 实测最后触发 | heat声称 | 一致性）：")
    for measured, rid, status, lm, lh, drift in rows[:30]:
        print(f"  {rid:14s} {status:5s} {measured:4d}  {lm}  {lh}  {drift}")

    hot_rule_total = sum(1 for k, v in heat.items()
                         if v.get("status") == "hot" and k.startswith("rule_"))
    zero_hot = [rid for rid, h in heat.items()
                if h.get("status") == "hot" and rid not in refs and rid.startswith("rule_")]
    print(f"\n[ledger] 实测 0 触发的 hot Rule {len(zero_hot)}/{hot_rule_total}"
          f"（C2 候选第一判据；第二判据=一句话失败模式测试，人工复核后降 cold；Forbidden 已按口径纪律排除，与 --zero-only 同口径）")
    print(f"[ledger] 口径注：分母 {hot_rule_total} = 索引温控列自称 hot 的 Rule 全量（含 §5A 表格基础规则）；"
          f"sync_check ⑤ 的 88 为排除 §5A 23 条后的口径，两者差即 §5A，非账实不符")
    drift_count = sum(1 for r in rows if r[5])
    heat_only = sum(1 for r in rows if 'heat独有' in r[5])
    print(f"[ledger] 声称漂移条目 {drift_count} 个（三类形态：实测与heat不一致 / 实测有heat缺 {drift_count - heat_only - sum(1 for r in rows if '漂移(heat' in r[5])} / heat有实测零 {heat_only}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
