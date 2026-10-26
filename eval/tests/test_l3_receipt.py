#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L3 收据 ID 提取测试（2026-10-26 收据漂移修复）"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "F:/WorkBuddy/history-today/scripts")
import l3_publish as l3  # noqa: E402


class TestAsId(unittest.TestCase):
    def test_dict_note_id(self):
        v = {"note_id": "7520425445699852", "action": "appended"}
        self.assertEqual(l3._as_id(v, "note_id"), "7520425445699852")

    def test_dict_media_id(self):
        v = {"media_id": "markdown_abc", "action": "uploaded"}
        self.assertEqual(l3._as_id(v, "media_id"), "markdown_abc")

    def test_dict_id_fallback(self):
        self.assertEqual(l3._as_id({"id": "x1"}, "note_id"), "x1")

    def test_string_unchanged(self):
        self.assertEqual(l3._as_id(" 12345 ", "note_id"), "12345")

    def test_none(self):
        self.assertEqual(l3._as_id(None, "note_id"), "")

    def test_dict_missing(self):
        self.assertEqual(l3._as_id({"action": "x"}, "note_id"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
