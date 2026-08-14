#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py — 一键核验 history-today-writer 技能文件一致性（v9.7.8）

核对项：
  ① 规则数：writing_core.md + topics/* + archive/cold_rules.md 的规则编号并集
     vs rule_index.md 索引行数 vs SKILL.md 声称数（155 = 104 Rule + 51 Forbidden）
  ② Forbidden 数（51）
  ③ 版本号：SKILL.md 末尾 Version 行（automation prompt 引用需人工核对）
  ④ 文件路径可达性：topics×3、review/prompts×6、craft_optional.md、
     archive/cold_rules.md、review/CASE_STUDIES.md、review_rules.md、
     rule_index.md、topic_rules.md 等是否存在

运行：在技能目录下执行  python scripts/sync_check.py
依赖：仅 Python 标准库（os/re/pathlib），Windows 路径兼容。
退出码：0 = 全部通过；1 = 存在失败项。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

EXPECT_RULES = 104       # R1-R104
EXPECT_FORBIDDEN = 51    # F1-F51
EXPECT_TOTAL = 155       # 104 + 51

# 规则正文来源文件（规则编号并集由此统计）
RULE_SOURCE_PATHS = [
    "writing_core.md",
    "topics/nature_disaster.md",
    "topics/war_institution.md",
    "topics/tech_engineering.md",
    "archive/cold_rules.md",
]

# 路径可达性检查清单
EXIST_PATHS = [
    "SKILL.md",
    "topic_rules.md",
    "writing_core.md",
    "rule_index.md",
    "review_rules.md",
    "craft_optional.md",
    "archive/cold_rules.md",
    "review/CASE_STUDIES.md",
    "topics/nature_disaster.md",
    "topics/war_institution.md",
    "topics/tech_engineering.md",
    "review/prompts/01_language.md",
    "review/prompts/02_fact_accuracy.md",
    "review/prompts/03_narrative_logic.md",
    "review/prompts/04_terminology.md",
    "review/prompts/05_structure.md",
    "review/prompts/06_expression.md",
]

results: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    """记录并打印一条检查结果。"""
    results.append((ok, label, detail))
    mark = "✅" if ok else "❌"
    line = f"{mark} {label}"
    if detail:
        line += f" —— {detail}"
    print(line)


def read_text(rel_path: str) -> str:
    """以 UTF-8（容错）读取技能目录下的相对路径文件。"""
    p = SKILL_DIR / rel_path
    return p.read_text(encoding="utf-8", errors="replace")


def extract_rule_numbers(text: str) -> set[int]:
    """提取文本中的 Rule 编号（Rule N / R N，忽略大小写）。"""
    nums = set()
    for m in re.finditer(r"(?:Rule|R)\s*(\d{1,3})", text, re.IGNORECASE):
        nums.add(int(m.group(1)))
    return nums


def extract_forbidden_numbers(text: str) -> set[int]:
    """提取文本中的 Forbidden 编号（Forbidden #N / 列表行 'N. ✗'）。"""
    nums = set()
    for m in re.finditer(r"Forbidden\s*#\s*(\d{1,2})", text, re.IGNORECASE):
        nums.add(int(m.group(1)))
    for m in re.finditer(r"^(\d{1,2})\.\s*✗", text, re.MULTILINE):
        nums.add(int(m.group(1)))
    return nums


def extract_s5a_base_rules(text: str) -> set[int]:
    """提取 writing_core §5A 表中编号 1-23（基础强制规则，无 'Rule' 前缀）。"""
    nums = set()
    m = re.search(r"## 5A\..*?## 5B\.", text, re.DOTALL)
    if not m:
        return nums
    section = m.group(0)
    for row in re.finditer(r"^\|\s*(\d{1,2})\s*\|", section, re.MULTILINE):
        n = int(row.group(1))
        if 1 <= n <= 23:
            nums.add(n)
    return nums


def count_index_rows(index_text: str, table_header: str) -> int:
    """统计 rule_index 中 '| R' 或 '| F' 开头的索引行数。"""
    m = re.search(re.escape(table_header) + r".*?(?=\n## |\Z)", index_text, re.DOTALL)
    if not m:
        return 0
    section = m.group(0)
    if table_header.startswith("## Rules"):
        return len(re.findall(r"^\|\s*R\d", section, re.MULTILINE))
    return len(re.findall(r"^\|\s*F\d", section, re.MULTILINE))


def main() -> int:
    print("=" * 64)
    print("history-today-writer sync_check（v9.7.8）")
    print(f"技能目录：{SKILL_DIR}")
    print("=" * 64)

    # ---- ① 规则数 ----
    rule_nums: set[int] = set()
    forbid_nums: set[int] = set()
    for rel in RULE_SOURCE_PATHS:
        text = read_text(rel)
        rule_nums |= extract_rule_numbers(text)
        forbid_nums |= extract_forbidden_numbers(text)
        if rel == "writing_core.md":
            rule_nums |= extract_s5a_base_rules(text)

    missing_rules = sorted(set(range(1, EXPECT_RULES + 1)) - rule_nums)
    extra_rules = sorted(rule_nums - set(range(1, EXPECT_RULES + 1)))
    check(
        not missing_rules and not extra_rules,
        "① 规则数（正文文件并集）",
        f"共 {len(rule_nums)} 个唯一编号（期望 {EXPECT_RULES}）；"
        f"缺失: {missing_rules or '无'}；越界: {extra_rules or '无'}",
    )

    # rule_index 索引行数
    index_text = read_text("rule_index.md")
    idx_rules = count_index_rows(index_text, "## Rules")
    idx_forbidden = count_index_rows(index_text, "## Forbidden")
    check(
        idx_rules == EXPECT_RULES,
        "① rule_index Rules 索引行数",
        f"{idx_rules} 行（期望 {EXPECT_RULES}）",
    )
    check(
        idx_forbidden == EXPECT_FORBIDDEN,
        "① rule_index Forbidden 索引行数",
        f"{idx_forbidden} 行（期望 {EXPECT_FORBIDDEN}）",
    )

    # SKILL.md 声称数
    skill_text = read_text("SKILL.md")
    claim_total = 0
    cm = re.search(r"总规则数\s*\|\s*(\d+)", skill_text)
    if cm:
        claim_total = int(cm.group(1))
    claim_match = claim_total == EXPECT_TOTAL
    check(
        claim_match,
        "① SKILL.md 声称规则数",
        f"总规则数 = {claim_total}（期望 {EXPECT_TOTAL} = {EXPECT_RULES} Rule + {EXPECT_FORBIDDEN} Forbidden）",
    )

    # 三方一致：正文并集 == 索引 == SKILL 声称
    check(
        len(rule_nums) == EXPECT_RULES and idx_rules == EXPECT_RULES and claim_total == EXPECT_TOTAL,
        "① 三方一致性（正文并集 / rule_index / SKILL.md）",
        f"正文 {len(rule_nums)} = 索引 {idx_rules} = 声称 {claim_total}",
    )

    # ---- ② Forbidden 数 ----
    missing_fb = sorted(set(range(1, EXPECT_FORBIDDEN + 1)) - forbid_nums)
    extra_fb = sorted(forbid_nums - set(range(1, EXPECT_FORBIDDEN + 1)))
    check(
        not missing_fb and not extra_fb and idx_forbidden == EXPECT_FORBIDDEN,
        "② Forbidden 数",
        f"正文并集 {len(forbid_nums)} 个唯一编号（期望 {EXPECT_FORBIDDEN}）；"
        f"缺失: {missing_fb or '无'}；越界: {extra_fb or '无'}；索引 {idx_forbidden} 行",
    )

    # ---- ③ 版本号 ----
    vm = re.search(r"Version:\s*(v[\d.]+)", skill_text)
    version = vm.group(1) if vm else "未找到"
    check(vm is not None, "③ 版本号（SKILL.md Version 行）", f"SKILL.md = {version}")
    print("   ℹ️ automation prompt 中的版本引用需人工核对（脚本无法读取 automation prompt 文件）")

    # ---- ④ 文件路径可达性 ----
    missing_paths = [p for p in EXIST_PATHS if not (SKILL_DIR / p).exists()]
    check(
        not missing_paths,
        "④ 文件路径可达性",
        f"共 {len(EXIST_PATHS)} 个路径；缺失: {missing_paths or '无'}",
    )

    # ---- 附加信息：关键文件体积（供字符数校准参考，不影响通过/失败） ----
    print("-" * 64)
    print("关键文件体积（字节）：")
    for rel in EXIST_PATHS:
        p = SKILL_DIR / rel
        if p.exists():
            print(f"   {rel}: {p.stat().st_size}")
    print("-" * 64)

    # ---- 汇总 ----
    passed = sum(1 for ok, _, _ in results if ok)
    failed = len(results) - passed
    print(f"汇总：{passed}/{len(results)} 项通过，{failed} 项失败")
    if failed:
        print("存在失败项，请人工核查后重跑。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
