#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_claims.py 的单元测试（D5）"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import verify_claims as vc  # noqa: E402


def claim(cid="C1", value="604,330,000", unit="股", sources=2, status="verified"):
    return {
        "id": cid, "claim": "x", "value": value, "unit": unit,
        "status": status, "cross_check": sources,
        "sources": [{"url": f"https://{i}", "title": "t", "retrieved_at": "x"}
                    for i in range(sources)],
    }


class TestNumbers(unittest.TestCase):
    def test_cn_to_num(self):
        cases = {
            "六千零四十万": 60_400_000,
            "六亿零四百三十万": 604_300_000,
            "一百六十万": 1_600_000,
            "三百": 300,
        }
        for s, v in cases.items():
            self.assertEqual(vc.cn_to_num(s), v, s)
        self.assertAlmostEqual(vc.cn_to_num("十三点五"), 13.5)
        self.assertAlmostEqual(vc.cn_to_num("二十二点六"), 22.6)

    def test_parse_value(self):
        self.assertEqual(vc.parse_value("604,330,000"), [604_330_000])
        self.assertEqual(vc.parse_value("1.2万"), [12_000])
        self.assertEqual(vc.parse_value("13.5-14.5"), [13.5, 14.5])
        self.assertEqual(vc.parse_value("六亿零四百三十万"), [604_300_000])

    def test_extract_chinese(self):
        tokens, dates = vc.extract_tokens("成交六千零四十万股，跌幅22.6%，耗时13.5小时。")
        vals = {t.value for t in tokens}
        self.assertIn(60_400_000, vals)
        self.assertIn(22.6, vals)
        self.assertIn(13.5, vals)
        self.assertEqual(len(tokens), 3)
        self.assertEqual(dates, [])

    def test_extract_arabic_wan(self):
        tokens, _ = vc.extract_tokens("成交6040万股。")
        self.assertEqual(tokens[0].value, 60_400_000)

    def test_date_not_in_measured(self):
        tokens, dates = vc.extract_tokens("1879年10月21日傍晚，灯亮了。")
        self.assertEqual(tokens, [])
        self.assertEqual(len(dates), 1)

    def test_match(self):
        r = vc.verify("成交六亿多股，跌幅22.6%。", [claim(), claim("C2", "22.6", "%")])
        self.assertEqual(r["unmatched"], 0)
        self.assertGreaterEqual(r["coverage"], 0.99)

    def test_unmatch_magnitude(self):
        r = vc.verify("成交六千零四十万股。", [claim()])
        self.assertEqual(r["unmatched"], 1)
        self.assertEqual(r["coverage"], 0.0)

    def test_single_source(self):
        r = vc.verify("成交六亿多股。", [claim(sources=1, status="single_source")])
        self.assertEqual(len(r["single_source_claims"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
