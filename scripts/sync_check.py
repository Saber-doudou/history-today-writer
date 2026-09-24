#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py — 一键核验 history-today-writer 技能文件一致性（v10.1.0）

核对项：
    ① 规则数：writing_core.md + topics/* + archive/cold_rules.md 的规则编号并集
     vs rule_index.md 索引行数 vs SKILL.md 声称数（193 = 135 Rule + 58 Forbidden）；
     另含 rule_index 小节标题声称（Rules/Forbidden N 条）与 SKILL.md 判例声称
     （= CASE_STUDIES 实际最大 CASE 编号）核验
  ② Forbidden 数（58）
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
  ⑫ 记忆分片新鲜度（2026-09-10 新增，防「分片切出即冻结」复发）：
     .workbuddy/memory/topics/exec_log.md 须覆盖最近 10 篇定稿日期；
     topics/publish_history.md 须覆盖最近 10 篇中已产生 IMA 收据的日期。
     缺行即 ❌（维护工具：F:/WorkBuddy/history-today/scripts/sync_topics.py --sync）。
  ⑪ 游离声称/版本漂移一致性（2026-09-08 新增，防「升版漏改注记/游离声称」复发）：
     rule_index.md 尾注首段版本 / CHANGELOG.md 最新条目 / feed-learning 引用行 的
     当前版本号须 == EXPECT_VERSION；SKILL「索引：N条规则编号」== EXPECT_TOTAL；
     SKILL「题材专项 hot N 条」== 实跑题材专项数。历史注记叙述天然豁免（只查当前状态声称位）。

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

EXPECT_RULES = 144       # R1-R144
EXPECT_FORBIDDEN = 55    # F1-F58 扣除已删空洞 23/49/50（F23 并入 R14，F49/F50 并入 R94/R95，Curator 棘轮 A/B 档）
EXPECT_TOTAL = 199       # 144 + 55
EXPECT_VERSION = "v10.2.0"  # SKILL.md 末尾 Version 行的期望版本号

# ⑬ 校验基线：权威 automation memory 于 2026-09-07 建立，此前记录已归档至
# archive/automation-memory-A-precompress-2026-09-07.md，不做追溯校验
AM_BASELINE_DATE = "2026-09-07"

# 规则数治理上限（P1-1 2026-09-08，方案决策 D1-A：仅监管输出 + 入库前置强制平衡闸，非硬 fail）
HOT_LIMIT = 90           # hot 规则上限（当前 85，留 5 余量）
TOTAL_LIMIT = 200        # 总规则上限（沿用昨日方案 4.3）

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


AUTO_ID = "automation-1778209807842"


def _read_automation_prompt(auto_id: str) -> str | None:
    """只读读取 automation prompt（DB），不可读/不存在时返回 None。

    DB 路径硬编码于本技能（history-today-writer 专用），与 ⑦⑨ 共用，
    避免重复连接逻辑（2026-09-06 抽取）。
    """
    import sqlite3

    db_path = Path("C:/Users/admin/.workbuddy/workbuddy.db")
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT prompt FROM automations WHERE id = ?", (auto_id,)).fetchone()
        conn.close()
    except Exception:  # noqa: BLE001 — 只读核验，任何异常均降级为提示
        return None
    return row[0] if row else None


def check_automation_prompt() -> None:
    """⑦ automation prompt 版本与规则数一致性核验（DB 读取，标准库 sqlite3）。

    - 版本号：prompt 开头 vX.Y[.Z] 须等于 EXPECT_VERSION
    - 规则数：prompt 须含 EXPECT_TOTAL 与 EXPECT_RULES+EXPECT_FORBIDDEN 引用，且不含已知旧值（176/122+54）
    - DB 不可读时降级为提示（不判失败），避免脚本在无 DB 环境挂掉
    """
    prompt = _read_automation_prompt(AUTO_ID)
    if prompt is None:
        print(f"   ⚠️ ⑦ automation prompt 核验：DB 不可读或 automation {AUTO_ID} 不存在，请人工核对")
        return
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


def check_prompt_structure() -> None:
    """⑨ automation prompt 结构核验（引用式，防双源漂移，2026-09-06 新增）。

    背景：ASO 事件暴露 SKILL.md 与 automation prompt 双源漂移——prompt 曾复制
    SKILL 的阶段细节（加载哪些规则文件/审校几维度），源头一改副本就漂移且无检测。
    根治方向：prompt 只做「引用式」声明（按 SKILL.md Phase 0-6 执行），不复制细节。

    - 引用声明：prompt 须显式含「SKILL.md … 单一事实源/按 SKILL.md」引用
    - 无阶段副本：prompt 不得出现阶段资源文件（writing_core/rule_index/review_rules/
      review/prompts/topic_rules/craft_optional/fact_checklist/CASE_STUDIES）——
      出现即说明仍复制了阶段细节，存在漂移风险
    - DB 不可读时降级为提示（与 ⑦ 同策略）
    """
    prompt = _read_automation_prompt(AUTO_ID)
    if prompt is None:
        print(f"   ⚠️ ⑨ automation prompt 结构核验：DB 不可读或 automation {AUTO_ID} 不存在，请人工核对")
        return
    # ① 引用式声明（SKILL.md 为阶段/规则唯一事实源）
    ref_ok = ("SKILL.md" in prompt) and ("单一事实源" in prompt or "按 SKILL.md" in prompt)
    # ② 阶段副本检测：这些文件名若出现在 prompt 中，说明复制了 SKILL 的阶段资源加载指令
    stage_copy_files = [
        "writing_core.md", "rule_index.md", "review_rules.md", "review/prompts",
        "topic_rules.md", "craft_optional.md", "fact_checklist.md", "CASE_STUDIES.md",
    ]
    copy_hits = [f for f in stage_copy_files if f in prompt]
    detail = (
        f"引用声明 = {'含（单一事实源）' if ref_ok else '缺失'}；"
        f"阶段副本 = {copy_hits or '无'}"
    )
    check(ref_ok and not copy_hits, "⑨ automation prompt 结构（引用式无阶段副本）", detail)


def check_meta_schema() -> None:
    """⑩ 元数据一致性（2026-09-07 新增，A3/A5 机械门禁）。

    目标一（A3）：权威 automation memory 最近 L1 执行块须含必填要素
    （选题 / 审校 / sync_check / 宿主状态）。宿主状态为 2026-09-07 新增字段，
    防「摘要称正常、宿主实际失败」的对账盲区再犯。
    目标二（A5）：陈旧编号「Phase 6b」残留 grep（选题索引模板头已修为 5b；
    防模板/流程文件再次带出旧编号）。SKILL.md 的 Version 叙述行豁免（历史记录文字）。
    """
    problems = []

    # 目标一：最近 L1 触发块必填要素（仅含「L1」标题的块，取日期最新；
    # 旧「执行摘要」块为 2026-09-07 前历史格式，不要求新字段）
    auth = Path("F:/WorkBuddy/history-today/.workbuddy/memory/automations/automation-1778209807842/memory.md")
    if auth.exists():
        txt = auth.read_text(encoding="utf-8", errors="replace")
        l1_blocks = []
        for m in re.finditer(r"## .*?(?=\n## |\Z)", txt, re.S):
            head = m.group(0).splitlines()[0]
            if "L1" in head:
                dm = re.search(r"(\d{4}-\d{2}-\d{2})", head)
                l1_blocks.append((dm.group(1) if dm else "", m.group(0)))
        if l1_blocks:
            latest = max(l1_blocks, key=lambda x: x[0])[1]
            required = ["选题", "审校", "sync_check", "宿主状态"]
            missing = [k for k in required if k not in latest]
            if missing:
                problems.append(f"最近 L1 块缺必填要素: {missing}")
        else:
            problems.append("未找到 L1 触发摘要块")
    else:
        problems.append("权威 automation memory 缺失")

    # 目标二：6b 残留 grep（选题索引模板 + SKILL 流程区，Version 叙述行豁免）
    idx = Path("F:/WorkBuddy/history-today/archive/daily/选题索引.md")
    if idx.exists() and "Phase 6b" in idx.read_text(encoding="utf-8", errors="replace"):
        problems.append("选题索引.md 头部仍含 Phase 6b 旧编号")
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    for ln in skill_text.splitlines():
        if ln.startswith("*Version:") or ln.startswith("# "):
            continue
        if "Phase 6b" in ln or "Phase6b" in ln:
            problems.append(f"SKILL.md 含陈旧编号: {ln.strip()[:40]}")
            break

    if problems:
        check(False, "⑩ 元数据一致性（摘要要素+编号残留）", "；".join(problems))
        return
    check(True, "⑩ 元数据一致性（摘要要素+编号残留）", "最近 L1 块要素齐全 / 无 6b 残留")


def check_claim_drift(topics_actual: int) -> None:
    """⑪ 游离声称/版本漂移检测（2026-09-08 新增，昨天复核 P1-1 建议落地 + Test Escalation）。

    只查「当前状态声称位」——历史注记叙述（SKILL footer 累积 v9.x 段、CHANGELOG 旧条目、
    rule_index 尾注「基于 v9.x」段）天然豁免，避免全文件扫描误伤历史文字：
      A) rule_index.md 尾注首段 `*版本：vX` == EXPECT_VERSION（09-08 曾滞留 v10.0.0，20/20 全绿未抓）
      B) CHANGELOG.md 最新 `## vX` 条目 == EXPECT_VERSION
      C) feed-learning SKILL.md 引用行「N条规则（X Rule + Y Forbidden，当前 vX.Y）」== 期望
         （跨技能引用滞留防再犯，07 ⑦ 不覆盖此文件）
      D) SKILL.md「索引：N条规则编号」== EXPECT_TOTAL（昨日 P1-1 三处游离声称之一）
      E) SKILL.md「题材专项 hot N 条」== 实跑题材专项 hot 数（昨日 P1-1 三处之一）
    """
    problems = []
    # A rule_index 尾注首段版本
    idx_text = read_text("rule_index.md")
    m = re.search(r"\*版本：\s*(v[\d.]+)", idx_text)
    if not m:
        problems.append("rule_index.md 未找到「版本：」注记行")
    elif m.group(1) != EXPECT_VERSION:
        problems.append(f"rule_index 尾注版本 {m.group(1)} ≠ 期望 {EXPECT_VERSION}（升版漏改注记）")
    # B CHANGELOG 最新条目
    cl_text = read_text("CHANGELOG.md")
    cm = re.search(r"^##\s*(v[\d.]+)", cl_text, re.MULTILINE)
    if not cm:
        problems.append("CHANGELOG.md 未找到「## vX」条目")
    elif cm.group(1) != EXPECT_VERSION:
        problems.append(f"CHANGELOG 最新条目 {cm.group(1)} ≠ 期望 {EXPECT_VERSION}")
    # C feed-learning 跨技能引用行
    fl = SKILL_DIR.parent / "history-today-feed-learning" / "SKILL.md"
    if fl.exists():
        fl_text = fl.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r"(\d+)\s*条规则（\s*(\d+)\s*Rule\s*\+\s*(\d+)\s*Forbidden，当前\s*v([\d.]+)", fl_text)
        for total_s, rules_s, fb_s, ver in refs:
            if (int(total_s), int(rules_s), int(fb_s)) != (EXPECT_TOTAL, EXPECT_RULES, EXPECT_FORBIDDEN) or f"v{ver}" != EXPECT_VERSION:
                problems.append(f"feed-learning 引用行 {total_s}条（{rules_s}+{fb_s}，当前 v{ver}）≠ 期望 {EXPECT_TOTAL}=({EXPECT_RULES}+{EXPECT_FORBIDDEN}，当前 {EXPECT_VERSION})")
    # D SKILL「索引：N条规则编号」
    skill_text = read_text("SKILL.md")
    idx_claim = re.search(r"索引：(\d+)\s*条规则编号", skill_text)
    if idx_claim and int(idx_claim.group(1)) != EXPECT_TOTAL:
        problems.append(f"SKILL「索引：{idx_claim.group(1)}条规则编号」≠ 期望 {EXPECT_TOTAL}")
    # E SKILL「题材专项 hot N 条」
    bad_hot = [int(h) for h in re.findall(r"题材专项\s*hot\s*(\d+)\s*条", skill_text) if int(h) != topics_actual]
    if bad_hot:
        problems.append(f"SKILL「题材专项 hot {bad_hot} 条」≠ 实跑 {topics_actual}")
    if problems:
        check(False, "⑪ 游离声称/版本漂移一致性", "；".join(problems))
        return
    detail = (f"rule_index 尾注={EXPECT_VERSION} / CHANGELOG 最新={EXPECT_VERSION} / "
              f"feed-learning 引用一致 / SKILL 索引={EXPECT_TOTAL} / 题材专项 hot={topics_actual}")
    check(True, "⑪ 游离声称/版本漂移一致性", detail)


def check_memory_size() -> None:
    """⑧ 记忆体积与单一路径检查（2026-09-07 升级：主记忆硬门禁 + 权威路径 + 分裂检测）。

    目标一（硬）：主记忆 MEMORY.md 注入上限 3000 字符，超限即 ❌（D2 直接硬，防"越压越大"日循环）。
    目标二（建议上限 warn）：权威 automation memory 建议上限 20 KB / 1000 行。
        —— 2026-09-18 复核修正：docstring 原始定位为「建议上限（warn）」，原代码误将体积超 20KB
           也实现为硬失败，与文档矛盾且对 11 天滚动记录（约 21.7KB）频繁误伤。现改为：
           行数 > 1000 仍判 ❌（硬门禁，捕捉真正失控的无限增长）；
           体积 > 20KB 仅记 ⚠️ 提示（滚动累积属正常，未达真正失控），不再阻断 sync_check。
           防失控的真正硬门禁由「主记忆 3000 字符 + automation 1000 行 + 旧路径分裂检测」三重兜底。
    目标三（分裂检测）：旧路径 .workbuddy/automations/.../memory.md 若再增长（超过归档说明文件体积），
    说明有旧逻辑仍在写旧路径，双写分裂复发，即 ❌。
    """
    base = Path("F:/WorkBuddy/history-today")
    mem = base / ".workbuddy/memory/MEMORY.md"
    auth = base / ".workbuddy/memory/automations/automation-1778209807842/memory.md"
    legacy = base / ".workbuddy/automations/automation-1778209807842/memory.md"
    problems: list[str] = []
    warns: list[str] = []
    chars = 0
    kb = 0.0
    if mem.exists():
        chars = len(mem.read_text(encoding="utf-8", errors="replace"))
        if chars > 3000:
            problems.append(f"主记忆 MEMORY.md {chars} 字符 > 3000 硬上限")
    else:
        problems.append("主记忆 MEMORY.md 缺失")
    if auth.exists():
        kb = auth.stat().st_size / 1024
        lines = auth.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        if lines > 1000:
            problems.append(f"automation memory {lines} 行超硬上限 1000（需归档历史块）")
        elif kb > 20.0:
            # 目标二为「建议上限」（docstring 标注 warn）：体积超建议值仅提示、不判失败
            warns.append(f"automation memory {kb:.1f} KB 超 20 KB 建议上限（滚动累积，持续观察，未达硬门禁）")
    else:
        problems.append("权威 automation memory 缺失")
    if legacy.exists():
        if legacy.stat().st_size > 700:  # 归档说明文件约 500 字节，超过即疑分裂复发
            problems.append("旧路径 automation memory 出现增长（双写分裂复发），请排查写入方")
    if problems:
        check(False, "⑧ 记忆体积与单一路径", "；".join(problems))
        return
    detail = f"主记忆 {chars} 字符 / automation {kb:.1f} KB（{'；'.join(warns) if warns else '体积正常'}） / 旧路径静态"
    check(True, "⑧ 记忆体积与单一路径", detail)


def check_topics_freshness() -> None:
    """⑫ 记忆分片新鲜度（2026-09-10 新增）。

    根因：topics/*.md 是 09-07 记忆治理时从 MEMORY.md 一次性切出的静态快照，无写入方，
    09-08 起 exec_log / publish_history 停更而无人察觉（09-10 审计发现）。
    本项把「分片须跟上归档」变成硬校验，维护动作由 scripts/sync_topics.py --sync 执行。
    """
    base = Path("F:/WorkBuddy/history-today")
    art = base / "archive/daily"
    topics = base / ".workbuddy/memory/topics"

    dates: list[str] = []
    for p in art.glob("*_v2.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_v2\.md$", p.name)
        if m:
            dates.append(m.group(1))
    dates = sorted(dates, reverse=True)[:10]

    rc_dates: set[str] = set()
    for p in art.glob("*_ima_receipt.json"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_ima_receipt\.json$", p.name)
        if m:
            rc_dates.add(m.group(1))

    problems = []
    for name, need in (("exec_log.md", set(dates)),
                       ("publish_history.md", set(dates) & rc_dates)):
        f = topics / name
        if not f.exists():
            problems.append(f"{name} 缺失")
            continue
        have = set(re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|",
                              f.read_text(encoding="utf-8", errors="replace"), re.M))
        miss = sorted(need - have, reverse=True)
        if miss:
            problems.append(f"{name} 缺 {len(miss)} 行 {miss}（跑 scripts/sync_topics.py --sync）")

    check(not problems, "⑫ 记忆分片新鲜度（exec_log / publish_history）",
          "；".join(problems) or f"最近 {len(dates)} 篇定稿均已登记")


def check_receipt_consistency() -> None:
    """⑬ IMA 收据 ↔ automation memory 一致性（2026-09-10 新增）。

    背景：收据按日期单文件存，同日二次备份会用新 note_id 覆盖旧值；而 automation memory
    走「字段级补全、不覆盖已有值」，两者必然漂移且此前无检查项覆盖。
    配合 write_ima_receipt 的 note_ids 留痕，本项拦截「最新 note_id 未回记到 automation memory」。
    """
    base = Path("F:/WorkBuddy/history-today")
    art = base / "archive/daily"
    am = base / ".workbuddy/memory/automations/automation-1778209807842/memory.md"
    if not am.exists():
        check(False, "⑬ IMA 收据↔automation memory 一致性", "权威 automation memory 缺失")
        return
    am_text = am.read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []
    checked = 0
    for p in sorted(art.glob("*_ima_receipt.json"))[-10:]:
        m = re.match(r"(\d{4}-\d{2}-\d{2})_ima_receipt\.json$", p.name)
        if not m:
            continue
        date = m.group(1)
        if date < AM_BASELINE_DATE:
            continue  # 权威 automation memory 建立于该日，此前记录在归档文件，不究
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            problems.append(f"{date} 收据 JSON 解析失败")
            continue
        nid = str(d.get("note_id") or "")
        if not nid:
            continue
        # 按日期取该日所有块（同日可能有「L3 收据补记」+「L3 二次备份」多个块，09-07 有先例）
        day_blocks = [s for s in re.split(r"^## ", am_text, flags=re.M) if s.startswith(date)]
        if not day_blocks:
            problems.append(f"{date} automation memory 无该日记录（note_id={nid}）")
            continue
        checked += 1
        if nid not in " ".join(day_blocks):
            problems.append(f"{date} 收据 note_id {nid} 未回记到 automation memory（漂移）")
    check(not problems, "⑬ IMA 收据↔automation memory 一致性",
          "；".join(problems) or f"最近 {checked} 条收据 note_id 均已回记")


def main() -> int:
    print("=" * 64)
    print("history-today-writer sync_check（v10.0.1）")
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
    # KNOWN_FB_GAPS（2026-09-11 Curator 棘轮 A 档配套）：F49/F50 自指残留已删（约束并入 R94/R95），
    # 编号空洞不回填——新增 Forbidden 自 F59 续号，防历史编号歧义。原「编号连续 1..N」假设与
    # 空洞冲突（删中间编号后尾部编号必被判越界），故合法全集 = 1..KNOWN_FB_MAX 扣除已知空洞。
    KNOWN_FB_GAPS = frozenset({23, 49, 50})   # 已删除且不复用的 Forbidden 编号（F23→R14，F49/F50→R94/R95）
    KNOWN_FB_MAX = 58                     # 现存最大 Forbidden 编号（F58 现代名词时代错置）
    allowed_fb = set(range(1, KNOWN_FB_MAX + 1)) - KNOWN_FB_GAPS
    missing_fb = sorted(allowed_fb - forbid_nums)
    extra_fb = sorted(forbid_nums - allowed_fb)
    check(
        not missing_fb and not extra_fb and idx_forbidden == EXPECT_FORBIDDEN,
        "② Forbidden 数",
        f"正文并集 {len(forbid_nums)} 个唯一编号（期望 {EXPECT_FORBIDDEN}）；"
        f"缺失: {missing_fb or '无'}；越界: {extra_fb or '无'}；索引 {idx_forbidden} 行",
    )

    # ---- ③ 版本号 ----
    vm = re.search(r"Version:\s*(v[\d.]+)", skill_text)
    version = vm.group(1) if vm else "未找到"
    # 逢十进位合法性（2026-09-07 正名后新增：v9.8.10~v9.9.4 期间偏离「每级 0-9、patch 逢 10 进位」
    # 约定（9.8.9+1 应为 9.9.0 却写成 9.8.10），靠此闸防再犯——minor/patch 出现 ≥10 的段直接判违规。
    # 2026-09-07 修正（v10.0.0 配套）：major 段豁免 0-9 限制——「MINOR=结构性变化」逢十进 major 后
    # major 可超 9（v9.9.5 彻底优化 → v10.0.0），原闸 all(0<=p<=9) 过紧会误伤 v10+ 纪元）
    if version != "未找到" and re.fullmatch(r"v\d+(?:\.\d+){1,2}", version):
        parts = [int(x) for x in version.lstrip("v").split(".")]
    else:
        parts = []
    dec_ok = bool(parts) and all(0 <= p <= 9 for p in parts[1:])
    check(
        vm is not None and version == EXPECT_VERSION and dec_ok,
        "③ 版本号（Version 行 + 逢十进位合法性）",
        f"SKILL.md = {version}（期望 {EXPECT_VERSION}）；"
        f"逢十合法性 = {'合规（minor/patch 各段 0-9，major 可超 9）' if dec_ok else '违规（minor/patch 存在 ≥10 段，应按逢十进位改写）' if parts else '无法解析'}",
    )

    # ---- ⑦ automation prompt 版本与规则数一致性（2026-09-01 新增，消除「人工核对」盲区；P2-2 遗留项落地）----
    check_automation_prompt()

    # ---- ⑧ automation memory 体积上限（warn-only，2026-09-02 C 项：防运行前读入成本膨胀）----
    check_memory_size()

    # ---- ⑨ automation prompt 结构（引用式无阶段副本，2026-09-06 新增：防 SKILL 与 prompt 双源漂移复发）----
    check_prompt_structure()

    # ---- ⑩ 元数据一致性（2026-09-07 新增：执行摘要要素 + 陈旧编号残留门禁）----
    check_meta_schema()

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

    # ---- ⑪ 游离声称/版本漂移一致性（2026-09-08 新增，Test Escalation：全绿仍漏网 → 升级考卷）----
    check_claim_drift(topics_actual)

    # ---- ⑫ 记忆分片新鲜度（2026-09-10 新增：分片切出即冻结 → 硬校验 + 脚本维护）----
    check_topics_freshness()

    # ---- ⑬ IMA 收据 ↔ automation memory 一致性（2026-09-10 新增：同日二次备份 note_id 覆盖）----
    check_receipt_consistency()

    # ---- 规则数监管仪表（P1-1 2026-09-08：不 fail 的监管输出；超限时的强制减法是 L2 入库前置流程闸，
    #      见 feed-learning SKILL Phase 4 平衡自查；此处仅让 hot/上限 每次 L1 都可见）----
    hot_now = core_actual + topics_actual
    print(f"📊 规则数监管：hot {hot_now}（core {core_actual} + 题材专项 {topics_actual}）/ 上限 {HOT_LIMIT}；"
          f"总规则 {EXPECT_TOTAL} / 上限 {TOTAL_LIMIT} —— hot 或总规则达上限后，L2 新增规则须伴随合并/降级/删除（强制平衡）")

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
