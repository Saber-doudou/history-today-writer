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
RECHECK_SCHEMA = json.loads((ROOT / "review" / "schema" / "review_recheck.v1.json").read_text(encoding="utf-8"))


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


def recheck_valid() -> dict:
    return {
        "date": "2026-10-30",
        "p0_count": 0,
        "p1_count": 1,
        "p2_count": 1,
        "pass": True,
        "issues": [
            {"dimension": "叙事与读者视角", "severity": "p1", "rule": "R20", "desc": "d", "fix": "f"},
            {"dimension": "事实准确性", "severity": "p2", "rule": "R13", "desc": "d", "fix": "f"},
        ],
        "independence": "independent_subprocess",
        "reviewer_model": "reasoning",
    }


class TestRouting(unittest.TestCase):
    """产物族路由：文件名即契约（B-24/B-25）。"""

    def test_recheck_names(self):
        for n in ("2026-10-30_v2_review.json", "2026-10-30-v2_review.json", "2026-10-31_v3_review.json"):
            self.assertEqual(vr.route_schema(Path(n)), "recheck", n)

    def test_review_names(self):
        for n in ("2026-10-30_review.json", "2026-10-29_review.json"):
            self.assertEqual(vr.route_schema(Path(n)), "review", n)

    def test_schema_mapping(self):
        self.assertEqual(vr.schema_path_for("recheck").name, "review_recheck.v1.json")
        self.assertEqual(vr.schema_path_for("review").name, "review_output.v2.json")


class TestNormalize(unittest.TestCase):
    """防腐层：只做等价变换，不猜字段。"""

    def test_independence_hyphen(self):
        d, changes = vr.normalize({"independence": "independent-subprocess"})
        self.assertEqual(d["independence"], "independent_subprocess")
        self.assertTrue(changes)

    def test_severity_case(self):
        d, _ = vr.normalize({"issues": [{"severity": "P1"}, {"severity": "P2"}]})
        self.assertEqual([i["severity"] for i in d["issues"]], ["p1", "p2"])

    def test_noop(self):
        d, changes = vr.normalize({"independence": "cross_family", "issues": [{"severity": "p0"}]})
        self.assertEqual(changes, [])
        self.assertEqual(d["independence"], "cross_family")

    def test_unknown_enum_untouched(self):
        d, changes = vr.normalize({"independence": "totally-new-mode"})
        self.assertEqual(d["independence"], "totally-new-mode")
        self.assertEqual(changes, [])

    def test_original_not_mutated(self):
        src = {"independence": "independent-subprocess"}
        vr.normalize(src)
        self.assertEqual(src["independence"], "independent-subprocess")


class TestRecheckSchema(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(vr.validate(recheck_valid(), RECHECK_SCHEMA, RECHECK_SCHEMA), [])

    def test_id_not_required(self):
        d = recheck_valid()
        self.assertNotIn("id", d["issues"][0])
        self.assertEqual(vr.validate(d, RECHECK_SCHEMA, RECHECK_SCHEMA), [])

    def test_missing_fix(self):
        d = recheck_valid()
        del d["issues"][0]["fix"]
        self.assertTrue(any("fix" in e for e in vr.validate(d, RECHECK_SCHEMA, RECHECK_SCHEMA)))

    def test_bad_dimension_empty(self):
        d = recheck_valid()
        d["issues"][0]["dimension"] = ""
        self.assertTrue(any("dimension" in e for e in vr.validate(d, RECHECK_SCHEMA, RECHECK_SCHEMA)))

    def test_raw_fails_normalized_passes(self):
        d = recheck_valid()
        d["independence"] = "independent-subprocess"
        d["issues"][0]["severity"] = "P1"
        self.assertTrue(vr.validate(d, RECHECK_SCHEMA, RECHECK_SCHEMA))
        norm, _ = vr.normalize(d)
        self.assertEqual(vr.validate(norm, RECHECK_SCHEMA, RECHECK_SCHEMA), [])


class TestCountMismatch(unittest.TestCase):
    def test_match(self):
        self.assertEqual(vr.count_mismatch(recheck_valid()), [])

    def test_mismatch(self):
        d = recheck_valid()
        d["p1_count"] = 0
        self.assertTrue(any("p1_count" in w for w in vr.count_mismatch(d)))

    def test_non_int_declared_ignored(self):
        d = recheck_valid()
        d["p0_count"] = "0"
        self.assertEqual(vr.count_mismatch(d), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
