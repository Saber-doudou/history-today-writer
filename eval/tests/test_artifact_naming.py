#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产物命名合规检查测试（B-25，2026-10-30）

背景：`sync_topics` 与 sync_check ⑫ 按 `{date}_v2.md` 扫描，写成 `{date}-v2.md`
的定稿对门禁「隐身」——缺行不报、反判通过。命名即契约，故单列测试。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_check as sc  # noqa: E402


def touch(d: Path, *names: str) -> None:
    for n in names:
        (d / n).write_text("x", encoding="utf-8")


class TestFindNoncanonical(unittest.TestCase):
    def test_hyphen_v2_md(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "2026-10-30-v2.md")
            self.assertEqual(
                sc.find_noncanonical_artifacts(p),
                [("2026-10-30-v2.md", "2026-10-30_v2.md")],
            )

    def test_hyphen_recheck_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "2026-10-30-v2_review.json")
            self.assertEqual(
                sc.find_noncanonical_artifacts(p),
                [("2026-10-30-v2_review.json", "2026-10-30_v2_review.json")],
            )

    def test_canonical_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "2026-10-30.md", "2026-10-30_v2.md", "2026-10-30_review.json",
                  "2026-10-30_v2_review.json", "2026-10-30_ima_receipt.json")
            self.assertEqual(sc.find_noncanonical_artifacts(p), [])

    def test_v3_and_dotted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "2026-11-01-v3.md", "2026-11-02-v2.1.md")
            got = dict(sc.find_noncanonical_artifacts(p))
            self.assertEqual(got["2026-11-01-v3.md"], "2026-11-01_v3.md")
            self.assertEqual(got["2026-11-02-v2.1.md"], "2026-11-02_v2.1.md")

    def test_non_artifact_names_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "README.md", "选题索引.md", "2026-10-30_notes.txt", "abc-v2.md")
            self.assertEqual(sc.find_noncanonical_artifacts(p), [])

    def test_missing_dir(self):
        self.assertEqual(sc.find_noncanonical_artifacts(Path("Z:/no/such/dir")), [])

    def test_sorted_and_complete(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            touch(p, "2026-10-30-v2.md", "2026-05-19-v2.md")
            names = [n for n, _ in sc.find_noncanonical_artifacts(p)]
            self.assertEqual(names, sorted(names))
            self.assertEqual(len(names), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
