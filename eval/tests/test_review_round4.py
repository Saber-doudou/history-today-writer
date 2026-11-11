#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四轮复审补漏回归测试（2026-11-11；第五轮复审定稿：全部调用真实现）

覆盖三块此前只有手工验证、未落成回归测试的逻辑：
  1. gate_check._load_contract 四形态降级（M3，4748ec0）
  2. sync_check.missing_ledger_dates ⑫ 账本硬闸核心判定（M1：全量扫描
     >= claims_since 的 v2，缺账本即入列；2026-11-11 第五轮复审把判定从
     check_topics_freshness 内嵌表达式抽出为可导入函数，测试调用真实现，
     改回「只查最新一篇」会红）
  3. check_delivery.extract_version 版本提取（第四轮 🔴：conventional commit
     前缀 feat(v10.6.0): 取不到，回溯 30 条错取 v10.5.0 造成假红；第五轮复审
     抽出为可导入函数，测试调用真实现）

已知基线：`python scripts/sync_check.py` 实跑 **23/24（唯一红=⑫ G-03）**。
注意 24/24 不可达：⑫ 全量扫描生效日（2026-11-10）后所有 v2，11-10 缺账本
永不补（G-03 批准登记留红），新定稿落盘账本也不会让该红消失。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "scripts"))

import gate_check as gc  # noqa: E402
import check_delivery as cd  # noqa: E402
import sync_check as sc  # noqa: E402


class TestLoadContract(unittest.TestCase):
    """M3 四形态降级：损坏 / 缺失 / 非法日期 / 正常。真调用 gc._load_contract()。"""

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
    """⑫ 账本硬闸核心判定：真调用 sync_check.missing_ledger_dates()。"""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.art = Path(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _touch_v2(self, date: str, with_ledger: bool = False):
        (self.art / f"{date}_v2.md").write_text("x", encoding="utf-8")
        if with_ledger:
            (self.art / f"topic_result_{date}.json").write_text("{}", encoding="utf-8")

    def _scan(self, all_v2: list[str], claims_since: str = "2026-11-10") -> list[str]:
        return sc.missing_ledger_dates(all_v2, self.art, claims_since)

    def test_scan_full_not_only_latest(self):
        """旧逻辑（all_v2[0]）在新定稿出现后旧缺口消失；真函数必须仍命中 11-10。"""
        self._touch_v2("2026-11-10")            # 缺账本（G-03 登记留红）
        self._touch_v2("2026-11-11", with_ledger=True)  # 新定稿，账本齐
        miss = self._scan(["2026-11-11", "2026-11-10"])
        self.assertEqual(miss, ["2026-11-10"],
                         "11-10 缺账本必须被扫描到，不因新定稿出现而消失")

    def test_scan_all_clean_passes(self):
        self._touch_v2("2026-11-11", with_ledger=True)
        self.assertEqual(self._scan(["2026-11-11"]), [])

    def test_scan_ignores_before_since(self):
        self._touch_v2("2026-11-06")  # 早于生效日，不追溯
        self.assertEqual(self._scan(["2026-11-06"]), [])

    def test_scan_multiple_missing_reports_all(self):
        self._touch_v2("2026-11-10")
        self._touch_v2("2026-11-11")  # 两篇都缺账本
        self.assertEqual(self._scan(["2026-11-11", "2026-11-10"]),
                         ["2026-11-11", "2026-11-10"])


class TestCheckDeliveryVersionRegex(unittest.TestCase):
    """check_delivery 版本提取：真调用 extract_version()。"""

    def test_conventional_prefix(self):
        self.assertEqual(cd.extract_version(
            ["feat(v10.6.0): 第三轮复审 M1-M4 闭环"]), "v10.6.0")

    def test_docs_prefix_without_version_takes_next(self):
        self.assertEqual(cd.extract_version(
            ["docs(known_gaps): G-03 批准登记留红",
             "feat(v10.6.0): 第三轮复审 M1-M4 "]), "v10.6.0")

    def test_bare_prefix_still_works(self):
        self.assertEqual(cd.extract_version(["v10.5.0: 2026-11-10"]), "v10.5.0")

    def test_regression_no_backtrack_to_old_version(self):
        """第四轮 🔴 复现：旧正则会跳过 feat(...) 取到 v10.5.0 造成假红。"""
        subjects = ["docs(known_gaps): G-03 批准登记留红",
                    "feat(v10.6.0): 第三轮复审 M1-M4 闭环",
                    "v10.5.0: 2026-11-10 门禁机制改造"]
        self.assertEqual(cd.extract_version(subjects), "v10.6.0")

    def test_no_version_at_all(self):
        self.assertEqual(cd.extract_version(["fix(gate): 修复若干"]), "")

    def test_plain_semver_without_v_prefix(self):
        """无 v 前缀的裸语义版本也应规范化为带 v 输出。"""
        self.assertEqual(cd.extract_version(["1.2.3: some change"]), "v1.2.3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
