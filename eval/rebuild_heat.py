#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_heat.py — 从 ledger 派生温控字段（D6，2026-10-24）

原则：不覆盖 last_triggered（L2 规则应用口径），只补充：
  - last_issue：最近一次被 review.json 引用的日期（L1 缺陷口径）
  - issue_count_30d：近 30 天被引用次数（L1 缺陷口径）
  - source：标注字段来源

这样 migrate_cold_rules 可以取 max(last_triggered, last_issue) 作为「最近活动」，
避免把「仍有缺陷触发、但 L2 未更新日期」的规则误降 cold。

用法：
    python eval/rebuild_heat.py --dry-run
    python eval/rebuild_heat.py --apply
    python eval/rebuild_heat.py --apply --report eval/reports/heat_rebuild_20261024.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rule_ledger as rl  # noqa: E402

HEAT = ROOT / "review" / "rule_heat.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="仅报告（默认）")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    data = json.loads(HEAT.read_text(encoding="utf-8"))
    rules = data.get("rules", {})
    review_refs, broken, total_issues = rl.load_review_refs(None)

    today = date.today()
    cutoff = (today - timedelta(days=30)).isoformat()

    updated = 0
    lag, missing, heat_only, same_or_ahead = [], [], [], []
    for key, h in rules.items():
        dates = sorted(review_refs.get(key, []))
        last_issue = dates[-1] if dates else None
        count_30 = sum(1 for d in dates if d >= cutoff)
        h["last_issue"] = last_issue
        h["issue_count_30d"] = count_30
        if last_issue:
            h["source"] = "manual+ledger" if h.get("last_triggered") else "ledger"
            updated += 1
            lt = h.get("last_triggered")
            if not lt:
                missing.append(key)
            elif last_issue > lt:
                lag.append({"key": key, "last_issue": last_issue, "last_triggered": lt})
            else:
                same_or_ahead.append(key)
        elif h.get("last_triggered"):
            heat_only.append(key)

    data["last_updated"] = today.isoformat()
    data["ledger_derived_at"] = datetime.now().isoformat(timespec="seconds")
    data["ledger_source_note"] = "last_issue/issue_count_30d 来自 review.json；last_triggered 保留 L2 应用口径"

    report = {
        "date": today.isoformat(),
        "review_json_files": len(list(rl.DAILY_DIR.glob("*_review.json"))),
        "broken_json": broken,
        "issues_total": total_issues,
        "rules_with_issue": updated,
        "heat_lag": len(lag),
        "heat_missing": len(missing),
        "heat_only_expected": len(heat_only),
        "same_or_heat_ahead": len(same_or_ahead),
        "heat_lag_examples": lag[:10],
        "heat_missing_examples": missing[:10],
        "applied": args.apply,
    }

    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.apply:
        backup = HEAT.with_suffix(".json.bak-20261024")
        if not backup.exists():
            shutil.copy2(HEAT, backup)
        HEAT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["backup"] = str(backup)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
