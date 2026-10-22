#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_review.py 的单元测试（D2）"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import validate_review as vr  # noqa: E402

SCHEMA = json.loads((ROOT / "review" / "schema" / "review_output.v2.json").read_text(encoding="utf-8"))


def valid() -> dict:
    return {
        "date": "2026-10-21",
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
        "pass": True,
        "issues": [],
    }


def with_issue(**kw) -> dict:
    d = valid()
    issue = {
        "id": 1,
        "category": "fact_accuracy",
        "severity": "p0",
        "location": "P3-P5",
        "current": "原文",
        "suggested": "建议",
        "reason": "原因",
    }
    issue.update(kw)
    d["issues"] = [issue]
    d["p0_count"] = 1
    return d


class TestValidateReview(unittest.TestCase):
    def test_valid_core(self):
        self.assertEqual(vr.validate(valid(), SCHEMA, SCHEMA), [])

    def test_missing_required(self):
        d = valid()
        del d["p0_count"]
        errs = vr.validate(d, SCHEMA, SCHEMA)
        self.assertTrue(any("p0_count" in e for e in errs))

    def test_negative_count(self):
        d = valid()
        d["p1_count"] = -1
        self.assertTrue(any("最小值" in e for e in vr.validate(d, SCHEMA, SCHEMA)))

    def test_bad_date(self):
        d = valid()
        d["date"] = "2026/10/21"
        self.assertTrue(any("不匹配" in e for e in vr.validate(d, SCHEMA, SCHEMA)))

    def test_bad_severity(self):
        errs = vr.validate(with_issue(severity="P0"), SCHEMA, SCHEMA)
        self.assertTrue(any("severity" in e for e in errs))

    def test_bad_location(self):
        errs = vr.validate(with_issue(location="第三段"), SCHEMA, SCHEMA)
        self.assertTrue(any("location" in e for e in errs))

    def test_issue_missing_field(self):
        d = with_issue()
        del d["issues"][0]["reason"]
        errs = vr.validate(d, SCHEMA, SCHEMA)
        self.assertTrue(any("reason" in e for e in errs))

    def test_strict_missing_independence(self):
        errs = vr.validate(valid(), SCHEMA, SCHEMA, strict=True)
        self.assertTrue(any("independence" in e for e in errs))
        self.assertTrue(any("reviewer_model" in e for e in errs))

    def test_strict_pass(self):
        d = valid()
        d["independence"] = "cross_family"
        d["reviewer_model"] = "model-x"
        self.assertEqual(vr.validate(d, SCHEMA, SCHEMA, strict=True), [])

    def test_wrong_type_bool_as_int(self):
        d = valid()
        d["p0_count"] = True
        self.assertTrue(vr.validate(d, SCHEMA, SCHEMA))


if __name__ == "__main__":
    unittest.main(verbosity=2)
