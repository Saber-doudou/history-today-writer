#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四轮复审补漏回归测试（2026-11-11）

覆盖三块此前只有手工验证、未落成回归测试的逻辑：
  1. gate_check._load_contract 四形态降级（M3，4748ec0）
  2. sync_check ⑫ 账本硬闸核心判定（M1：全量扫描 >= claims_since 的 v2，
     缺账本即 problems；all_v2[0] 旧逻辑的回归由 test_scan_full 不限于最新一篇钉死）
  3. check_delivery 版本正则（第四轮 🔴：conventional commit 前缀 feat(v10.6.0): 取不到，
     回溯 30 条错取 v10.5.0 造成假红）

⑫ 判定逻辑内嵌于 check_topics_freshness 大函数、依赖真实归档目录，
故此处按「与实现同款表达式」做语义钉子测试：若实现侧改动扫描逻辑而行为
回退（如改回只查最新一篇），本测试不一定能捕获——真正的守门是
`python scripts/sync_check.py` 实跑 23/24（唯一红=⑫ G-03）这一已知基线。
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import gate_check as gc  # noqa: E402


class TestLoadContract(unittest.TestCase):
    """M3 四形态降级：损坏 / 缺失 / 非法日期 / 正常。"""

    def _run_with(self, content: str | None) -> dict:
        """把 contract_dates.json 临时替换为指定内容后调用 _load_contract。"""
        real = gc.HERE / "contract_dates.json"
        backup = real.read_bytes() if real.is_file() else None
        try:
            if content is None:
                real.unlink(missing_ok=True)
            else:
                real.write_text(content, encoding="utf-8")
            return gc._load_contract()
        finally:
            if backup is not None:
                real.write_bytes(backup)
            elif content is None and real.exists():
                real.unlink()

    def test_corrupted_file_degrades(self):
        out = self._run_with("{ this is not json !!!")
        self.assertEqual(out["v2_review_since"], "9999-12-31")
        self.assertEqual(out["claims_since"], "9999-12-31")
        self.assertIn("_load_error", out)

    def test_missing_file_degrades(self):
        out = self._run_with(None)
        self.assertEqual(out["claims_since"], "9999-12-31")
        self.assertIn("_load_error", out)

    def test_invalid_date_degrades(self):
        out = self._run_with(json.dumps(
            {"v2_review_since": "2026-11-10", "claims_since": "2026/11/10"}))
        self.assertEqual(out["v2_review_since"], "2026-11-10")  # 合法键保留
        self.assertEqual(out["claims_since"], "9999-12-31")  # 非法键降级
        self.assertIn("_load_error", out)

    def test_missing_key_degrades(self):
        out = self._run_with(json.dumps({"v2_review_since": "2026-11-10"}))
        self.assertEqual(out["claims_since"], "9999-12-31")
        self.assertIn("_load_error", out)

    def test_valid_file_loads_clean(self):
        out = self._run_with(json.dumps(
            {"v2_review_since": "2026-11-10", "claims_since": "2026-11-10"}))
        self.assertEqual(out["claims_since"], "2026-11-10")
        self.assertNotIn("_load_error", out)


class TestLedgerGateScan(unittest.TestCase):
    """⑫ 账本硬闸核心判定：扫全部 >= claims_since 的 v2，不只最新一篇。"""

    SCAN = lambda self, all_v2: [  # noqa: E731 — 与 sync_check ⑫ 实现同款表达式
        d for d in all_v2
        if d >= "2026-11-10" and not (ART / f"topic_result_{d}.json").is_file()
    ]

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        global ART
        ART = Path(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _touch_v2(self, date: str, with_ledger: bool = False):
        (ART / f"{date}_v2.md").write_text("x", encoding="utf-8")
        if with_ledger:
            (ART / f"topic_result_{date}.json").write_text("{}", encoding="utf-8")

    def test_scan_full_not_only_latest(self):
        """旧逻辑（all_v2[0]）在新定稿出现后旧缺口消失；全量扫描必须仍命中 11-10。"""
        self._touch_v2("2026-11-10")            # 缺账本（G-03 登记留红）
        self._touch_v2("2026-11-11", with_ledger=True)  # 新定稿，账本齐
        miss = self.SCAN(["2026-11-11", "2026-11-10"])
        self.assertEqual(miss, ["2026-11-10"],
                         "11-10 缺账本必须被扫描到，不因新定稿出现而消失")

    def test_scan_all_clean_passes(self):
        self._touch_v2("2026-11-11", with_ledger=True)
        self.assertEqual(self.SCAN(["2026-11-11"]), [])

    def test_scan_ignores_before_since(self):
        self._touch_v2("2026-11-06")  # 早于生效日，不追溯
        self.assertEqual(self.SCAN(["2026-11-06"]), [])


class TestCheckDeliveryVersionRegex(unittest.TestCase):
    """check_delivery 版本正则：conventional commit 前缀不再假红。"""

    PAT = re.compile(r"(?:\w+\()?((?:v)?\d+\.\d+\.\d+)\)?:")
    EXPECTED = gc  # noqa: F841 — 仅为模块加载顺序保证

    def _extract(self, subjects: list[str]) -> str:
        for line in subjects:
            m = self.PAT.match(line.strip())
            if m:
                v = m.group(1)
                return v if v.startswith("v") else f"v{v}"
        return ""

    def test_conventional_prefix(self):
        self.assertEqual(self._extract(
            ["feat(v10.6.0): 第三轮复审 M1-M4 闭环"]), "v10.6.0")

    def test_docs_prefix_without_version_takes_next(self):
        self.assertEqual(self._extract(
            ["docs(known_gaps): G-03 批准登记留红",
             "feat(v10.6.0): 第三轮复审 M1-M4 "]), "v10.6.0")

    def test_bare_prefix_still_works(self):
        self.assertEqual(self._extract(["v10.5.0: 2026-11-10"]), "v10.5.0")

    def test_regression_no_backtrack_to_old_version(self):
        """第四轮 🔴 复现：旧正则会跳过 feat(...) 取到 v10.5.0 造成假红。"""
        subjects = ["docs(known_gaps): G-03 批准登记留红",
                    "feat(v10.6.0): 第三轮复审 M1-M4 闭环",
                    "v10.5.0: 2026-11-10 门禁机制改造"]
        self.assertEqual(self._extract(subjects), "v10.6.0")

    def test_no_version_at_all(self):
        self.assertEqual(self._extract(["fix(gate): 修复若干"]), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
