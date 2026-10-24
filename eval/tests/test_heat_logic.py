#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D6 温控逻辑测试：last_activity = max(last_triggered, last_issue)"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_cold_rules as m  # noqa: E402


class TestLastActivity(unittest.TestCase):
    def test_issue_later(self):
        self.assertEqual(
            m.last_activity({"last_triggered": "2026-08-06", "last_issue": "2026-10-08"}),
            date(2026, 10, 8),
        )

    def test_triggered_later(self):
        self.assertEqual(
            m.last_activity({"last_triggered": "2026-10-22", "last_issue": "2026-07-14"}),
            date(2026, 10, 22),
        )

    def test_only_issue(self):
        self.assertEqual(m.last_activity({"last_issue": "2026-09-30"}), date(2026, 9, 30))

    def test_only_triggered(self):
        self.assertEqual(m.last_activity({"last_triggered": "2026-09-01"}), date(2026, 9, 1))

    def test_none(self):
        self.assertIsNone(m.last_activity({}))

    def test_invalid(self):
        self.assertIsNone(m.last_activity({"last_triggered": "not-a-date"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
