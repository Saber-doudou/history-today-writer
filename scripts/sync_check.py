#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py — 一键核验 history-today-writer 技能文件一致性（v9.8.6）

核对项：
  ① 规则数：writing_core.md + topics/* + archive/cold_rules.md 的规则编号并集
     vs rule_index.md 索引行数 vs SKILL.md 声称数（169 = 116 Rule + 53 Forbidden）
  ② Forbidden 数（53）
  ③ 版本号：SKILL.md 末尾 Version 行须等于 EXPECT_VERSION（automation prompt 引用需人工核对）
  ④ 文件路径可达性：topics×3、review/prompts×6、craft_optional.md、
     archive/cold_rules.md、review/CASE_STUDIES.md、review_rules.md、
     rule_index.md、topic_rules.md 等是否存在
  ⑤ hot 规则正文完整性：rule_index 标记 hot 的规则（文件=core/nat/war/tech），
     在对应文件定位 `### Rule {n}.` / `### Rule {n}:` 标题，检查标题后 1-5 行内
     存在非空正文行（防「标题/引用保留、正文删除」假阳性）；「仅编号」幽灵编号
     （R24/25/28/29/30 等）与 §5A 表格式基础规则（1-23）除外

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

EXPECT_RULES = 116       # R1-R116
EXPECT_FORBIDDEN = 53    # F1-F53
EXPECT_TOTAL = 169       # 116 + 53
EXPECT_VERSION = "v9.8.6"  # SKILL.md 末尾 Version 行的期望版本号

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
    """以 UTF-8（容错）读取技能目录下的相对路径文件。

    文件缺失时打印 ⚠️ 提示并返回空字符串（调用方据此判 ❌），避免脚本 traceback 崩溃。
    """
    p = SKILL_DIR / rel_path
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print(f"   ⚠️ 文件缺失：{rel_path}")
        return ""


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


# ---- ⑤ hot 规则正文完整性检查（v9.7.9 新增）----

# rule_index 文件代码 → 相对文件路径
FILE_CODE_TO_PATH = {
    "core": "writing_core.md",
    "nat": "topics/nature_disaster.md",
    "war": "topics/war_institution.md",
    "tech": "topics/tech_engineering.md",
}

# §5A 基础规则以表格行呈现（无 "### Rule N" 标题），由 extract_s5a_base_rules 覆盖，不参与正文检查
S5A_TABLE_RULES = frozenset(range(1, 24))


def parse_hot_rule_targets(index_text: str) -> list[tuple[int, str]]:
    """从 rule_index 解析 hot 规则目标：(编号, 相对文件路径)。

    匹配表格行 `| R<数字> | 题材 | 性质 | 级别 | hot | (core|nat|war|tech) | 摘要 |`，
    注意 R 后数字可能带空格（`| R 36 |`）。摘要含「仅编号」的幽灵编号
    （R24/25/28/29/30 等，无独立正文）自动排除；§5A 表格式基础规则（1-23，core）
    由 extract_s5a_base_rules 覆盖，一并排除，避免误报。
    """
    targets: list[tuple[int, str]] = []
    for line in index_text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        m = re.fullmatch(r"R\s*(\d{1,3})", cells[0])
        if not m:
            continue
        n = int(m.group(1))
        if cells[4] != "hot":          # 温控列
            continue
        file_code = cells[5]           # 文件列
        if file_code not in FILE_CODE_TO_PATH:
            continue
        if "仅编号" in cells[6]:       # 幽灵编号：仅编号、无独立正文
            continue
        if file_code == "core" and n in S5A_TABLE_RULES:
            continue
        targets.append((n, FILE_CODE_TO_PATH[file_code]))
    return targets


def is_body_line(line: str) -> bool:
    """判断一行是否为规则正文行。

    排除：空行、标题行、自检清单/列表项、纯分隔行、判例来源行、引用行、表格行。
    """
    s = line.strip()
    if not s:
        return False
    if re.match(r"^#{1,6}\s", s):              # 标题行
        return False
    if re.match(r"^[-*]\s", s) or s.startswith("□") or s.startswith("○"):  # 自检清单 / 列表项（注意 `**加粗**` 不以空格开头，不误伤）
        return False
    if re.match(r"^[—\-]{3,}$", s):            # 纯分隔行
        return False
    if re.match(r"^\*\*判例来源", s) or re.match(r"^判例来源", s):  # 判例来源行
        return False
    if re.match(r"^>\s*", s):                  # 引用行
        return False
    if s.startswith("|"):                      # 表格行
        return False
    return True


def verify_hot_rule_bodies(targets: list[tuple[int, str]]) -> list[int]:
    """核验 hot 规则正文完整性：以 `### Rule {n}.` 或 `### Rule {n}:` 定位标题，
    检查标题行之后至下一个标题前的 1-5 行内是否存在非空正文行。

    标题不存在（正文整段被删），或标题后至下一标题间无正文行 → 记为缺失。
    返回正文缺失的规则编号列表。
    """
    missing: list[int] = []
    for n, rel in targets:
        text = read_text(rel)
        if not text:
            missing.append(n)
            continue
        heading = re.compile(
            rf"^#{{1,6}}\s*Rule\s*{n}\s*[:.．、]",
            re.MULTILINE | re.IGNORECASE,
        )
        hm = heading.search(text)
        if not hm:
            missing.append(n)
            continue
        # 跳过标题行残余（分隔符后的标题文字），从下一行开始扫描，最多 5 行
        tail_lines = text[hm.end():].splitlines()
        tail_lines = tail_lines[1:] if tail_lines else []
        found_body = False
        for line in tail_lines[:5]:
            s = line.strip()
            if re.match(r"^#{1,6}\s", s):   # 已到下一个标题 → 本规则无正文
                break
            if is_body_line(line):
                found_body = True
                break
        if not found_body:
            missing.append(n)
    return missing


def main() -> int:
    print("=" * 64)
    print("history-today-writer sync_check（v9.8.6）")
    print(f"技能目录：{SKILL_DIR}")
    print("=" * 64)

    # ---- ① 规则数 ----
    rule_nums: set[int] = set()
    forbid_nums: set[int] = set()
    missing_sources: list[str] = []
    for rel in RULE_SOURCE_PATHS:
        text = read_text(rel)
        if not text and not (SKILL_DIR / rel).exists():
            missing_sources.append(rel)
        rule_nums |= extract_rule_numbers(text)
        forbid_nums |= extract_forbidden_numbers(text)
        if rel == "writing_core.md":
            rule_nums |= extract_s5a_base_rules(text)

    missing_rules = sorted(set(range(1, EXPECT_RULES + 1)) - rule_nums)
    extra_rules = sorted(rule_nums - set(range(1, EXPECT_RULES + 1)))
    check(
        not missing_rules and not extra_rules and not missing_sources,
        "① 规则数（正文文件并集）",
        f"共 {len(rule_nums)} 个唯一编号（期望 {EXPECT_RULES}）；"
        f"缺失: {missing_rules or '无'}；越界: {extra_rules or '无'}；"
        f"源文件缺失: {missing_sources or '无'}",
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
    check(
        vm is not None and version == EXPECT_VERSION,
        "③ 版本号（SKILL.md Version 行）",
        f"SKILL.md = {version}（期望 {EXPECT_VERSION}）",
    )
    print("   ℹ️ automation prompt 中的版本引用需人工核对（脚本无法读取 automation prompt 文件）")

    # ---- ④ 文件路径可达性 ----
    missing_paths = [p for p in EXIST_PATHS if not (SKILL_DIR / p).exists()]
    check(
        not missing_paths,
        "④ 文件路径可达性",
        f"共 {len(EXIST_PATHS)} 个路径；缺失: {missing_paths or '无'}",
    )

    # ---- ⑤ hot 规则正文完整性（v9.7.9 新增，防「标题保留、正文删除」假阳性）----
    hot_targets = parse_hot_rule_targets(index_text)
    core_targets = [t for t in hot_targets if t[1] == "writing_core.md"]
    topics_targets = [t for t in hot_targets if t[1] != "writing_core.md"]

    core_missing = verify_hot_rule_bodies(core_targets)
    check(
        not core_missing,
        "⑤ hot 规则正文完整性（core 通用）",
        f"核验 {len(core_targets)} 条 hot 规则；正文缺失: {core_missing or '无'}",
    )

    topics_missing = verify_hot_rule_bodies(topics_targets)
    check(
        not topics_missing,
        "⑤ hot 规则正文完整性（topics 专项）",
        f"核验 {len(topics_targets)} 条 hot 规则；正文缺失: {topics_missing or '无'}",
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
