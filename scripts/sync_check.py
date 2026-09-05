#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py — 一键核验 history-today-writer 技能文件一致性（v9.8.14）

核对项：
    ① 规则数：writing_core.md + topics/* + archive/cold_rules.md 的规则编号并集
     vs rule_index.md 索引行数 vs SKILL.md 声称数（186 = 130 Rule + 56 Forbidden）；
     另含 rule_index 小节标题声称（Rules/Forbidden N 条）与 SKILL.md 判例声称
     （= CASE_STUDIES 实际最大 CASE 编号）核验
  ② Forbidden 数（55）
  ③ 版本号：SKILL.md 末尾 Version 行须等于 EXPECT_VERSION（automation prompt 版本/计数一致性由 ⑦ 自动核验）
  ④ 文件路径可达性：topics×3、review/prompts×6、craft_optional.md、
     archive/cold_rules.md、review/CASE_STUDIES.md、review_rules.md、
     rule_index.md、topic_rules.md 等是否存在
  ⑤ hot 规则正文完整性：rule_index 标记 hot 的规则（文件=core/nat/war/tech），
     在对应文件定位 `### Rule {n}.` / `### Rule {n}:` 标题，检查标题后 1-5 行内
     存在非空正文行（防「标题/引用保留、正文删除」假阳性）；「仅编号」幽灵编号
     （R24/25/28/29/30 等）与 §5A 表格式基础规则（1-23）除外；
     另含 SKILL.md hot 声称数（core + 题材专项）与实跑一致核验
  ⑥ rule_heat ↔ rule_index ↔ 正文落点 三向一致性（v0.1 增补，migrate_cold_rules 配套）：
     rule_heat.status 与 rule_index 温控列（去 * 归一化）须一致；rule_index 标 cold 的
     规则（幽灵编号/§5A 除外）正文须已在 archive；rule_index 标 hot 的规则正文须在 hot
     区。已知例外（F1-6 物理保留全文、P0+cold、疑似应 recovered）记 ⚠️ 不判失败。

运行：在技能目录下执行  python scripts/sync_check.py
依赖：仅 Python 标准库（os/re/json/pathlib），Windows 路径兼容。
退出码：0 = 全部通过；1 = 存在失败项。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

EXPECT_RULES = 130       # R1-R130
EXPECT_FORBIDDEN = 56    # F1-F56
EXPECT_TOTAL = 186       # 130 + 56
EXPECT_VERSION = "v9.8.14"  # SKILL.md 末尾 Version 行的期望版本号

# 规则正文来源文件（规则编号并集由此统计）
RULE_SOURCE_PATHS = [
    "writing_core.md",
    "topics/nature_disaster.md",
    "topics/war_institution.md",
    "topics/tech_engineering.md",
    "archive/cold_rules.md",
]

# 判例库文件（SKILL.md 声称的判例数须与此文件实际最大 CASE 编号一致）
CASE_STUDIES_PATH = "review/CASE_STUDIES.md"

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

# 基础 Forbidden F1-6（物理保留全文，不参与冷迁移）
BASE_FORBIDDEN = frozenset(range(1, 7))


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


def cross_check_three_way(index_text: str, heat_text: str) -> tuple[list[str], list[str]]:
    """⑥ 三向一致性（v0.1 增补，migrate_cold_rules 配套）。

    返回 (fail_items, warn_items)：
    - A 向：rule_heat.status 与 rule_index 温控列（去 * 归一化）不一致 → fail
    - B 向：rule_index 标 cold → 正文须已在 archive（幽灵编号/§5A 除外）；
           正文仍在 hot 区 → warn（待 migrate 降级）；无处可寻 → fail
    - C 向：rule_index 标 hot → 正文须在 hot 区；正文在 cold 区 → warn（待 v0.2 升温）
    - 已知例外（F1-6 物理保留全文、P0+cold、疑似应 recovered）记 warn 不判失败
    """
    fails: list[str] = []
    warns: list[str] = []
    try:
        heat = json.loads(heat_text).get("rules", {})
    except (json.JSONDecodeError, AttributeError):
        return ["rule_heat.json 解析失败"], []
    hot_rule_nums: set[int] = set()
    hot_fb_nums: set[int] = set()
    cold_rule_nums: set[int] = set()
    cold_rule_table_nums: set[int] = set()   # archive 表格行承载（无独立标题块）
    cold_fb_nums: set[int] = set()
    for rel in RULE_SOURCE_PATHS:
        text = read_text(rel)
        if rel == "archive/cold_rules.md":
            for m in re.finditer(r"^#{1,6}\s*Rule\s*(\d{1,3})\s*[:.．、]", text, re.MULTILINE | re.IGNORECASE):
                cold_rule_nums.add(int(m.group(1)))
            for m in re.finditer(r"^\|\s*Rule\s*(\d{1,3})\s*\|", text, re.MULTILINE):
                cold_rule_table_nums.add(int(m.group(1)))
            for m in re.finditer(r"^\|\s*Forbidden #(\d{1,2})\s*\|", text, re.MULTILINE):
                cold_fb_nums.add(int(m.group(1)))
        else:
            for m in re.finditer(r"^#{1,6}\s*Rule\s*(\d{1,3})\s*[:.．、]", text, re.MULTILINE | re.IGNORECASE):
                hot_rule_nums.add(int(m.group(1)))
            for line in text.splitlines():
                m = re.match(r"^(\d{1,2})\.\s*✗", line)
                if m and "（cold）" not in line:
                    hot_fb_nums.add(int(m.group(1)))
    for line in index_text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        m = re.fullmatch(r"([RF])\s*(\d{1,3})", cells[0])
        if not m:
            continue
        is_rule = m.group(1) == "R"
        n = int(m.group(2))
        idx_heat_raw = cells[4]
        idx_heat = idx_heat_raw.rstrip("*")
        summary = cells[6]
        is_ghost = "仅编号" in summary
        is_s5a = is_rule and n in S5A_TABLE_RULES
        heat_key = ("rule" if is_rule else "forbidden") + "_" + f"{n:02d}"
        heat_st = heat.get(heat_key, {}).get("status")
        # A 向：rule_heat.status vs rule_index 温控列
        if heat_st and heat_st != idx_heat:
            fails.append(f"{'R' if is_rule else 'F'}{n}：rule_heat={heat_st} ≠ rule_index={idx_heat_raw}")
        # B 向：rule_index 标 cold → 正文须在 archive
        if idx_heat == "cold" and not is_ghost and not is_s5a:
            if is_rule:
                if n not in cold_rule_nums and n not in cold_rule_table_nums:
                    if n in hot_rule_nums:
                        warns.append(f"R{n}：rule_index=cold 但正文仍在 hot 区（待 migrate 降级）")
                    else:
                        fails.append(f"R{n}：rule_index=cold 但正文无处可寻")
            else:
                if n not in cold_fb_nums:
                    if n in hot_fb_nums:
                        if n in BASE_FORBIDDEN:
                            warns.append(f"F{n}：基础 Forbidden 物理保留全文（已知例外）")
                        else:
                            warns.append(f"F{n}：rule_index=cold 但正文仍在 hot 区（待 migrate 降级）")
                    else:
                        fails.append(f"F{n}：rule_index=cold 但正文无处可寻")
        # C 向：rule_index 标 hot → 正文须在 hot 区
        elif idx_heat == "hot" and not is_ghost and not is_s5a:
            if is_rule:
                if n not in hot_rule_nums:
                    if n in cold_rule_nums:
                        warns.append(f"R{n}：rule_index=hot 但正文在 cold 区（待 v0.2 升温）")
                    else:
                        fails.append(f"R{n}：rule_index=hot 但正文无处可寻")
            else:
                if n not in hot_fb_nums:
                    if n in cold_fb_nums:
                        warns.append(f"F{n}：rule_index=hot 但正文在 cold 区（待 v0.2 升温）")
                    else:
                        fails.append(f"F{n}：rule_index=hot 但正文无处可寻")
    return fails, warns


def check_automation_prompt() -> None:
    """⑦ automation prompt 版本与规则数一致性核验（DB 读取，标准库 sqlite3）。

    - 版本号：prompt 开头 vX.Y[.Z] 须等于 EXPECT_VERSION
    - 规则数：prompt 须含 EXPECT_TOTAL 与 EXPECT_RULES+EXPECT_FORBIDDEN 引用，且不含已知旧值（176/122+54）
    - DB 不可读时降级为提示（不判失败），避免脚本在无 DB 环境挂掉
    """
    import sqlite3
    db_path = Path("C:/Users/admin/.workbuddy/workbuddy.db")
    auto_id = "automation-1778209807842"
    if not db_path.exists():
        print("   ⚠️ ⑦ automation prompt 核验：DB 不可读，跳过（请人工核对）")
        return
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT prompt FROM automations WHERE id = ?", (auto_id,)).fetchone()
        conn.close()
    except Exception as e:  # noqa: BLE001 — 只读核验，任何异常均降级为提示
        print(f"   ⚠️ ⑦ automation prompt 核验：读取失败（{e}），请人工核对")
        return
    if not row:
        print(f"   ⚠️ ⑦ automation prompt 核验：automation {auto_id} 不存在，请人工核对")
        return
    prompt = row[0]
    vm = re.search(r"v\d+\.\d+(?:\.\d+)?", prompt[:120])
    ver_ok = bool(vm and vm.group(0) == EXPECT_VERSION)
    count_ok = (f"{EXPECT_TOTAL}" in prompt) and (f"{EXPECT_RULES}+{EXPECT_FORBIDDEN}" in prompt)
    stale = [s for s in ("176", "122+54", "173", "119+54") if s in prompt]
    detail = (
        f"prompt 版本 = {vm.group(0) if vm else '未找到'}（期望 {EXPECT_VERSION}）；"
        f"规则数引用 = {'合规' if count_ok else '需核对'}；"
        f"旧值残留 = {stale or '无'}"
    )
    check(ver_ok and count_ok and not stale, "⑦ automation prompt 版本与规则数一致性", detail)


def check_memory_size() -> None:
    """⑧ automation memory 体积上限检查（warn-only，2026-09-02 C 项）。

    自动化运行前会全文读入 .workbuddy/automations/*/memory.md，体积过大会持续
    推高每次运行的 token 成本。超限时打印 ⚠️ 提示人工归档（不判失败，避免
    因渐进恶化指标直接红掉运行）；正常时记为通过项。
    """
    p = Path("F:/WorkBuddy/history-today/.workbuddy/automations/automation-1778209807842/memory.md")
    limit_kb = 20.0
    if not p.exists():
        print("   ⚠️ ⑧ automation memory 体积：文件缺失（路径可能已变更），请人工核对")
        return
    kb = p.stat().st_size / 1024
    if kb > limit_kb:
        print(f"   ⚠️ ⑧ automation memory 体积：{kb:.1f} KB 超过 {limit_kb:.0f} KB 建议上限，"
              f"请归档瘦身（参照 archive/memory_archive/ 迁移先例，2026-09-02）")
        return
    check(True, "⑧ automation memory 体积上限", f"{kb:.1f} KB（建议上限 {limit_kb:.0f} KB，warn-only）")


def main() -> int:
    print("=" * 64)
    print("history-today-writer sync_check（v9.8.14）")
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

    # rule_index 首行标题声称条数（2026-09-02 A4 新增：防「（180 条）」等标题声称值滞留不更新；
    # 标题形如 `# rule_index — 规则全量索引（182 条，写作阶段加载）`）
    idx_first_line = index_text.splitlines()[0] if index_text.splitlines() else ""
    tm = re.search(r"（\s*(\d+)\s*条", idx_first_line)
    if tm:
        title_claim = int(tm.group(1))
        detail = f"标题「（{title_claim} 条）」 vs 期望 {EXPECT_TOTAL}"
    else:
        title_claim = -1
        detail = f"首行未含「（N 条）」（首行前 60 字符: {idx_first_line[:60]!r}）"
    check(
        tm is not None and title_claim == EXPECT_TOTAL,
        "① rule_index 标题声称条数",
        detail,
    )

    # ① rule_index 小节标题声称条数（2026-09-03 audit-fix：v9.8.12→13 升级曾漏改
    # `## Rules（126 条）`/`## Forbidden（54 条）`，首行标题已更新但小节标题滞留；
    # 首行只声称总数，小节标题分别声称 Rules/Forbidden 数，须与实测行数一致）
    sec_rules_claim, sec_fb_claim = None, None
    for sec_line in index_text.splitlines():
        m_rules = re.match(r"^##\s*Rules（\s*(\d+)\s*条）", sec_line.strip())
        m_fb = re.match(r"^##\s*Forbidden（\s*(\d+)\s*条）", sec_line.strip())
        if m_rules:
            sec_rules_claim = int(m_rules.group(1))
        elif m_fb:
            sec_fb_claim = int(m_fb.group(1))
    check(
        sec_rules_claim is not None and sec_rules_claim == idx_rules,
        "① rule_index Rules 小节标题声称条数",
        f"标题「Rules（{sec_rules_claim if sec_rules_claim is not None else '未找到'} 条）」 vs 实测 {idx_rules} 行",
    )
    check(
        sec_fb_claim is not None and sec_fb_claim == idx_forbidden,
        "① rule_index Forbidden 小节标题声称条数",
        f"标题「Forbidden（{sec_fb_claim if sec_fb_claim is not None else '未找到'} 条）」 vs 实测 {idx_forbidden} 行",
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

    # ① SKILL.md 判例声称 = CASE_STUDIES 实际最大 CASE 编号（2026-09-03 audit-fix：
    # SKILL.md 模块表曾声称「58 条案例」而 CASE_STUDIES 已至 CASE-64，两处声称不一致；
    # 取 SKILL.md 全部「N条案例（续号至N）」声称与判例库实际最大编号比对）
    case_text = read_text(CASE_STUDIES_PATH)
    case_max = max((int(m) for m in re.findall(r"CASE-(\d+)", case_text)), default=0)
    skill_case_claims = [int(m) for m in re.findall(r"(\d+)\s*条案例", skill_text)]
    case_claims_ok = bool(skill_case_claims) and all(c == case_max for c in skill_case_claims)
    check(
        case_claims_ok,
        "① SKILL.md 判例声称数",
        f"SKILL 声称 {sorted(set(skill_case_claims)) if skill_case_claims else '未找到'} vs 判例库实际 CASE-{case_max}",
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

    # ---- ⑦ automation prompt 版本与规则数一致性（2026-09-01 新增，消除「人工核对」盲区；P2-2 遗留项落地）----
    check_automation_prompt()

    # ---- ⑧ automation memory 体积上限（warn-only，2026-09-02 C 项：防运行前读入成本膨胀）----
    check_memory_size()

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

    # ⑤ SKILL.md hot 声称 = 实测（2026-09-03 audit-fix：SKILL.md 模块表曾声称
    # 「77条hot（core 55+22）」与「78条hot（core 56+22）」两处互相矛盾且与实跑不符；
    # 以 parse_hot_rule_targets 实跑 core/topics 数为准，校验 SKILL.md 所有
    # 「N条hot规则（core M + 题材专项 K，sync_check ⑤ 口径）」声称）
    core_actual = len(core_targets)
    topics_actual = len(topics_targets)
    hot_claims = re.findall(r"(\d+)\s*条\s*hot\s*规则（\s*core\s*(\d+)\s*\+\s*题材专项\s*(\d+)", skill_text, re.IGNORECASE)
    if hot_claims:
        hot_ok = all(int(c[0]) == (int(c[1]) + int(c[2])) and int(c[1]) == core_actual
                     and int(c[2]) == topics_actual for c in hot_claims)
        hot_detail = (f"SKILL 声称 {[(int(c[0]), int(c[1]), int(c[2])) for c in hot_claims]} "
                      f"vs 实跑 core {core_actual} + 题材专项 {topics_actual}")
    else:
        hot_ok = False
        hot_detail = f"SKILL.md 未找到「N条hot规则（core M + 题材专项 K）」声称模式"
    check(hot_ok, "⑤ SKILL.md hot 声称数", hot_detail)

    # ---- ⑥ rule_heat ↔ rule_index ↔ 正文落点 三向一致性（v0.1 增补）----
    heat_text6 = read_text("review/rule_heat.json")
    if heat_text6:
        fails6, warns6 = cross_check_three_way(index_text, heat_text6)
        warn_disp = warns6[:6]
        if len(warns6) > 6:
            warn_disp.append(f"…（共 {len(warns6)} 项提示）")
        check(
            not fails6,
            "⑥ rule_heat↔rule_index↔落点 三向一致",
            f"硬不一致 {len(fails6)} 项：{fails6 or '无'}；提示 {len(warns6)} 项：{warn_disp or '无'}",
        )
    else:
        check(False, "⑥ rule_heat↔rule_index↔落点 三向一致", "review/rule_heat.json 缺失")

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
