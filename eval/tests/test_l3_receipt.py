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


class TestReceiptFlags(unittest.TestCase):
    """B-18/B-19（2026-10-30）：收据须自证「KB 幂等跳过」与「git 未推送」。"""

    def setUp(self):
        import tempfile
        self._orig = {k: l3.CFG.get(k) for k in ("article_dir", "git_repo_path")}
        self.tmp = tempfile.TemporaryDirectory()
        l3.CFG["article_dir"] = self.tmp.name
        l3.KB_STATE.update({"idempotent": False, "media_id": ""})
        l3.GIT_STATE.update({"pending": False, "error": ""})

    def tearDown(self):
        for k, v in self._orig.items():
            if v is None:
                l3.CFG.pop(k, None)
            else:
                l3.CFG[k] = v
        self.tmp.cleanup()

    def _read(self, path):
        import json
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_clean_receipt_has_no_flags(self):
        p = l3.write_ima_receipt("2026-10-30", "v10.4.4", "n1", "commit=abc1234", "kb1")
        d = self._read(p)
        self.assertNotIn("kb_idempotent", d)
        self.assertNotIn("git_pending", d)

    def test_kb_idempotent_flag(self):
        l3.KB_STATE["idempotent"] = True
        p = l3.write_ima_receipt("2026-10-30", "v10.4.4", "n1", "commit=abc1234", "")
        d = self._read(p)
        self.assertTrue(d["kb_idempotent"])

    def test_git_pending_flag(self):
        l3.GIT_STATE.update({"pending": True, "error": "[network] connect reset"})
        p = l3.write_ima_receipt("2026-10-30", "v10.4.4", "n1", "network fail", "kb1")
        d = self._read(p)
        self.assertTrue(d["git_pending"])
        self.assertIn("network", d["git_error"])

    def test_git_pending_resolved_on_rerun(self):
        """上一次标记未推送、本次成功 → 显式写 False 并清掉 git_error。

        2026-11-11 修 N2：旧实现只写 True 从不写 False，标记永久滞留，
        事后无法分辨到底推没推（11-10 实锤：收据 pending=true，实际已推成 4cdbbce）。
        """
        import json
        ledger = Path(self.tmp.name) / "2026-10-30_ima_receipt.json"
        ledger.write_text(json.dumps({
            "date": "2026-10-30", "note_id": "n0",
            "git_pending": True, "git_error": "[network] timeout",
        }, ensure_ascii=False), encoding="utf-8")
        l3.GIT_STATE.update({"pending": False, "error": ""})
        p = l3.write_ima_receipt("2026-10-30", "v10.4.4", "n1", "commit=abc1234", "kb1")
        d = self._read(p)
        self.assertIs(d["git_pending"], False)
        self.assertNotIn("git_error", d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
