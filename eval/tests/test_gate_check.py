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


def make(text: str) -> Path:
    d = tempfile.mkdtemp()
    p = Path(d) / "2026-10-22_v2.md"
    p.write_text(text, encoding="utf-8")
    return p


def valid_text(body: str = BODY) -> str:
    return f"# On This Day | 测试标题\n2026年10月22日 · 北京\n{body}\n"


class TestGateCheck(unittest.TestCase):
    def test_valid(self):
        r = gc.check(make(valid_text()), CFG)
        self.assertTrue(r["pass"], r["p0_fail"])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
