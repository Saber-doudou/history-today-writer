#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_check.py 的单元测试（D7）"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import gate_check as gc  # noqa: E402

CFG = json.loads((ROOT / "eval" / "gate_config.json").read_text(encoding="utf-8"))
BODY = "灯" * 600


def make(text: str, companions: bool = True, date: str = "2026-10-22") -> Path:
    d = tempfile.mkdtemp()
    p = Path(d) / f"{date}_v2.md"
    p.write_text(text, encoding="utf-8")
    if companions:
        # M1（B-13）：v2 阶段要求复检件同目录存在
        (Path(d) / f"{date}_v2_review.json").write_text(
            json.dumps({"date": date, "p0_count": 0, "p1_count": 0,
                        "p2_count": 0, "pass": True, "issues": []}, ensure_ascii=False),
            encoding="utf-8")
    return p


def valid_text(body: str = BODY) -> str:
    return f"# On This Day | 测试标题\n2026年10月22日 · 北京\n{body}\n"


class TestGateCheck(unittest.TestCase):
    def test_valid(self):
        r = gc.check(make(valid_text()), CFG)
        self.assertTrue(r["pass"], r["p0_fail"])

    # ── A8 账本阈值（2026-11-11 修 N1 激励倒挂）──
    def test_a8_missing_ledger_after_since_fails(self):
        """强制日及之后缺账本 = 违约。此前一律 skip，导致不写账本反而放行。"""
        r = gc.check(make(valid_text(), date="2026-11-10"), CFG)
        self.assertTrue(any(f["id"] == "A8" for f in r["p0_fail"]), r["p0_fail"])

    def test_a8_missing_ledger_before_since_skips(self):
        """早于强制日缺账本仍 skip，不追溯历史。"""
        r = gc.check(make(valid_text(), date="2026-10-22"), CFG)
        a8 = [c for c in r["checks"] if c["id"] == "A8"]
        self.assertEqual(a8[0]["status"], "skip", a8)

    def test_a8_null_claims_fails(self):
        """账本存在但 claims=null 属契约违约，与「缺文件」是两种红灯。"""
        p = make(valid_text(), date="2026-11-10")
        ledger = p.parent / f"{p.name[:10]}_ledger.json"
        ledger.write_text(json.dumps({"date": "2026-11-10", "claims": None},
                                     ensure_ascii=False), encoding="utf-8")
        r = gc.check(p, CFG, claims_path=ledger)
        self.assertTrue(any(f["id"] == "A8" for f in r["p0_fail"]), r["p0_fail"])

    def test_double_dash(self):
        r = gc.check(make(valid_text(BODY + "——")), CFG)
        self.assertTrue(any(f["id"] == "A2" for f in r["p0_fail"]))

    def test_f19(self):
        r = gc.check(make(valid_text(BODY + "\n字数：600")), CFG)
        self.assertTrue(any(f["id"] == "A3" for f in r["p0_fail"]))

    def test_bad_title(self):
        text = "## 测试标题\n2026年10月22日 · 北京\n" + BODY
        r = gc.check(make(text), CFG)
        self.assertTrue(any(f["id"] == "A4" for f in r["p0_fail"]))

    def test_short_body(self):
        r = gc.check(make(valid_text("太短了")), CFG)
        self.assertTrue(any(f["id"] == "A1" for f in r["p0_fail"]))

    def test_future_date(self):
        r = gc.check(make(valid_text(BODY + "2099年1月1日")), CFG)
        self.assertTrue(any(f["id"] == "A10" for f in r["p0_fail"]))

    def test_a5_integrated_opening(self):
        text = "# On This Day | 测试标题\n2026年10月22日，北京市下了一场雨。\n" + BODY
        r = gc.check(make(text), CFG)
        a5 = [c for c in r["checks"] if c["id"] == "A5"][0]
        self.assertEqual(a5["status"], "pass", a5)

    def test_a11_term_quotes_not_counted(self):
        text = valid_text(BODY + '这家技术叫"静电复印术"，取自"干"与"书写"。')
        r = gc.check(make(text), CFG)
        a11 = [c for c in r["checks"] if c["id"] == "A11"][0]
        self.assertEqual(a11["status"], "pass", a11)

    def test_a11_long_quote_without_attribution(self):
        text = valid_text(BODY + '"这是一句足够长的话，没有任何来源。"')
        r = gc.check(make(text), CFG)
        a11 = [c for c in r["checks"] if c["id"] == "A11"][0]
        self.assertEqual(a11["status"], "warn", a11)


class TestArtifacts(unittest.TestCase):
    """M1-M3 产物齐备性（B-13，2026-10-30）。"""

    def test_m1_missing_recheck(self):
        # 契约自 2026-11-10 起强制，故用强制日当天验证「缺件必须 fail」
        r = gc.check(make(valid_text(), companions=False, date="2026-11-10"), CFG)
        self.assertTrue(any(f["id"] == "M1" for f in r["p0_fail"]), r["p0_fail"])

    def test_m1_historical_missing_recheck_skipped(self):
        # 早于强制日的历史缺件不追溯：skip 而非 fail（2026-11-10 与 sync_check ⑫ 同口径）
        r = gc.check(make(valid_text(), companions=False, date="2026-10-22"), CFG)
        self.assertFalse(any(f["id"] == "M1" for f in r["p0_fail"]), r["p0_fail"])
        m1 = [c for c in r["checks"] if c["id"] == "M1"]
        self.assertEqual(m1[0]["status"], "skip", m1)

    def test_m2_date_mismatch(self):
        p = make(valid_text())
        (p.parent / "2026-10-22_review.json").write_text(
            json.dumps({"date": "2026-10-21"}, ensure_ascii=False), encoding="utf-8")
        r = gc.check(p, CFG)
        self.assertTrue(any(f["id"] == "M2" for f in r["p0_fail"]), r["p0_fail"])

    def test_m3_warn_when_v2_without_recheck(self):
        d = Path(tempfile.mkdtemp())
        p = d / "2026-10-22.md"
        p.write_text(valid_text(), encoding="utf-8")
        (d / "2026-10-22_review.json").write_text(
            json.dumps({"date": "2026-10-22"}, ensure_ascii=False), encoding="utf-8")
        (d / "2026-10-22_v2.md").write_text(valid_text(), encoding="utf-8")
        r = gc.check(p, CFG)
        self.assertTrue(any(w["id"] == "M3" for w in r["warnings"]), r["warnings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
