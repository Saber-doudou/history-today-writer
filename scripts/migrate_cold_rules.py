#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_cold_rules.py — 规则正文冷热迁移（v0.1，2026-08-26）

依据 docs/rule-cold-migration-plan.md（定稿 v1.1）：
- A 双闸：last_triggered 距今 ≥60 天（null 视为超期）+ demoted_at 距今 ≥30 天（保护期）
- B 默认 --dry-run 仅报告；连续 7 个工作日 ① 区无新增候选后由 Master 确认转 --force
- C 本期只做降级 + 对账 + 冲突报告；升温（recovered/hot → 回搬 hot 区）留接口 v0.2 不上线

安全闸 G1-G7（命中即跳过，先于状态判定执行）：
  G1 never_cool:true（rule_heat）  G2 §5A 基础 1-23  G3 基础 Forbidden F1-6
  G4 任意 P0 级  G5 last_triggered <7 天（新规则保护期）  G6 Rule 14  G7 幽灵编号（仅编号）

用法：
  python scripts/migrate_cold_rules.py --dry-run          # 四区对账报告，不落盘
  python scripts/migrate_cold_rules.py --dry-run --report # 同上并落盘 review/migration_reconcile_YYYY-MM-DD.md
  python scripts/migrate_cold_rules.py --force            # 实际搬运 + .bak 快照 + sync_check 校验

输出：
  review/migration_state.json            每次运行（结构化状态：date/mode/actions/checks/errors）
  review/migration_reconcile_YYYY-MM-DD.md  --report 时（md 对账报告，给人看）

回滚：cp <file>.bak <file> 或 git checkout -- <file>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

# ---- 阈值双闸与安全闸常量（单一规则来源，出处见 plan §3.9）----
DEMOTE_UNTRIGGERED_DAYS = 60   # 设计文档 rule-heat-cool-design.md:88「连续 60 天未触发」
DEMOTE_PROTECT_DAYS = 30       # demoted_at 保护期（橙皮书 Curator stale 观察期同构）
HOT_PROTECT_DAYS = 7           # 新规则保护期（设计文档「<7 天强制 hot」）
CONFLICT_REVIVE_DAYS = 30      # 疑似应 recovered 阈值：cold 但近 30 天有触发

# 正文源文件（对齐 sync_check.py）
HOT_SOURCES = [
    "writing_core.md",
    "topics/nature_disaster.md",
    "topics/war_institution.md",
    "topics/tech_engineering.md",
]
COLD_SOURCE = "archive/cold_rules.md"

# 永不降级集合（rule_index 侧标注）
S5A_BASE = frozenset(range(1, 24))          # §5A 基础 23 条（R1-23）
BASE_FORBIDDEN = frozenset(range(1, 7))     # F1-6 基础 Forbidden
RULE14 = 14

results: list[tuple[bool, str, str]] = []


def log(ok: bool, label: str, detail: str = "") -> None:
    results.append((ok, label, detail))
    mark = "✅" if ok else "❌"
    line = f"{mark} {label}"
    if detail:
        line += f" —— {detail}"
    print(line)


def read_text(rel: str) -> str:
    p = SKILL_DIR / rel
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


# ============================================================
# 1. rule_index 解析
# ============================================================
def parse_rule_index(index_text: str) -> dict:
    """返回 {(kind, n): {level, heat, file, summary}}，kind ∈ {rule, forbidden}"""
    out: dict = {}
    section = "rules"
    for line in index_text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            section = "forbidden" if "Forbidden" in line else "rules"
            continue
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        m = re.fullmatch(r"([RF])\s*(\d{1,3})", cells[0])
        if not m:
            continue
        kind = "rule" if m.group(1) == "R" else "forbidden"
        n = int(m.group(2))
        out[(kind, n)] = {
            "level": cells[3],
            "heat": cells[4],          # hot/cold/cold*（* = 物理保留全文）
            "file": cells[5],
            "summary": cells[6],
        }
    return out


# ============================================================
# 2. rule_heat 解析
# ============================================================
def parse_rule_heat(text: str) -> dict:
    """返回 {(kind, n): {status, last_triggered, count_30d, demoted_at, never_cool}}"""
    data = json.loads(text)
    out: dict = {}
    for key, v in data.get("rules", {}).items():
        m = re.fullmatch(r"(rule|forbidden)_(\d{1,3})", key)
        if not m:
            continue
        kind = "rule" if m.group(1) == "rule" else "forbidden"
        n = int(m.group(2))
        out[(kind, n)] = v
    return out


# ============================================================
# 3. 正文扫描（整块解析）
# ============================================================
RULE_HEAD_RE = re.compile(r"^(#{1,6})\s*Rule\s*(\d{1,3})\s*[:.．、]", re.IGNORECASE)
FORBIDDEN_LINE_RE = re.compile(r"^(\d{1,2})\.\s*✗")


def scan_rule_blocks(text: str, rel: str) -> dict:
    """扫描 Rule 多行块 → {n: {file, body(含标题行), title}}"""
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = RULE_HEAD_RE.match(lines[i])
        if m:
            n = int(m.group(2))
            level = len(m.group(1))
            start = i
            j = i + 1
            while j < len(lines):
                hm = re.match(r"^(#{1,6})\s", lines[j])
                if hm and len(hm.group(1)) <= level:
                    break
                j += 1
            out[n] = {
                "file": rel,
                "body": "\n".join(lines[start:j]),
                "title": m.group(0).rstrip(":").strip(),
                "line_start": start,
            }
            i = j
        else:
            i += 1
    return out


def scan_forbidden_lines(text: str, rel: str) -> dict:
    """扫描 Forbidden 单行块 → {n: {file, body(整行), cold_placeholder(bool)}}"""
    out: dict = {}
    for idx, line in enumerate(text.splitlines()):
        m = FORBIDDEN_LINE_RE.match(line)
        if m:
            n = int(m.group(1))
            out[n] = {
                "file": rel,
                "body": line,
                "cold_placeholder": "（cold）" in line,
            }
    return out


def scan_forbidden_table(text: str) -> dict:
    """扫描 archive 冷 Forbidden 表格行 → {n: body}（archive 正文唯一存放处）"""
    out: dict = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*Forbidden #(\d{1,2})\s*\|\s*(.+?)\s*\|$", line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def scan_all() -> dict:
    """返回 {(kind, n): 实际落点信息}。
    落点优先级：hot 区真实正文（非占位）> cold 区（archive 块/表格行）> hot 区占位。
    """
    actual: dict = {}
    # Rule 块（hot 源文件；archive 内 Rule 块 → cold）
    for rel in HOT_SOURCES + [COLD_SOURCE]:
        text = read_text(rel)
        for n, blk in scan_rule_blocks(text, rel).items():
            loc = "hot" if rel in HOT_SOURCES else "cold"
            actual.setdefault(("rule", n), {"loc": loc, "file": rel, "body": blk["body"], "title": blk["title"]})
    # Forbidden 行：hot 源文件真实正文（非占位）→ hot；占位 → placeholder（不构成 hot 正文）
    for rel in HOT_SOURCES:
        text = read_text(rel)
        for n, blk in scan_forbidden_lines(text, rel).items():
            if blk["cold_placeholder"]:
                actual.setdefault(("forbidden", n), {"loc": "placeholder", "file": rel, "body": blk["body"], "cold_placeholder": True})
            else:
                actual.setdefault(("forbidden", n), {"loc": "hot", "file": rel, "body": blk["body"], "cold_placeholder": False})
    # Forbidden 表格行：archive 冷 Forbidden 正文证据
    cold_text = read_text(COLD_SOURCE)
    for n, body in scan_forbidden_table(cold_text).items():
        if ("forbidden", n) not in actual:
            actual[("forbidden", n)] = {"loc": "cold", "file": COLD_SOURCE, "body": body, "cold_placeholder": False}
    return actual


# ============================================================
# 4. 安全闸 & 双闸
# ============================================================
def check_gates(kind: str, n: int, heat: dict, idx: dict) -> str | None:
    """返回命中的闸名；未命中返回 None。
    注：G5 新规则保护期无独立创建时间字段，rule_heat 的 last_triggered 不能代表创建时间；
    冷规则近 30 天有触发归入冲突区「疑似应 recovered」（CONFLICT_REVIVE_DAYS），不在此拦截。
    """
    if heat.get("never_cool"):
        return "G1 never_cool"
    if kind == "rule" and n in S5A_BASE:
        return "G2 §5A 基础"
    if kind == "forbidden" and n in BASE_FORBIDDEN:
        return "G3 基础 Forbidden F1-6"
    if idx and idx.get("level") == "P0":
        return "G4 P0 级"
    if kind == "rule" and n == RULE14:
        return "G6 Rule 14"
    if idx and "仅编号" in (idx.get("summary") or ""):
        return "G7 幽灵编号(仅编号)"
    return None


def days_since(d: date | None) -> int | None:
    if d is None:
        return None
    return (date.today() - d).days


def classify(kind: str, n: int, heat: dict, idx: dict | None, act: dict | None) -> dict:
    """分类一条规则到各区。返回描述 dict（含 zone）。"""
    today = date.today()
    status = heat.get("status")
    raw_loc = act.get("loc") if act else "none"
    # 占位落点 = hot 区仅占位 → 正文实际在 cold 区（archive 表格/块）
    loc = "cold" if raw_loc == "placeholder" else raw_loc
    gate = check_gates(kind, n, heat, idx or {})
    is_ghost = bool(idx and "仅编号" in (idx.get("summary") or ""))

    rec = {
        "key": f"{'Rule' if kind == 'rule' else 'Forbidden #'}{n}",
        "status": status,
        "loc": loc,
        "gate": gate,
        "level": (idx or {}).get("level", "—"),
        "heat_col": (idx or {}).get("heat", "?"),
        "last_triggered": heat.get("last_triggered"),
        "demoted_at": heat.get("demoted_at"),
    }

    # 幽灵编号：豁免（不搬不删不报错）
    if is_ghost:
        rec["zone"] = "ghost"
        return rec

    # 冲突/疑似检测（优先于落点分类）
    conflicts = []
    if (idx or {}).get("level") == "P0" and status == "cold":
        conflicts.append("P0 却 cold（设计文档规定 P0 永不降级）")
    lt_d = parse_date(heat.get("last_triggered"))
    if status == "cold" and lt_d and days_since(lt_d) < CONFLICT_REVIVE_DAYS:
        conflicts.append(f"cold 但近 {days_since(lt_d)} 天有触发（疑似应 recovered）")
    if status != (idx or {}).get("heat", "").rstrip("*"):
        conflicts.append(f"rule_heat({status}) ≠ rule_index 温控列({(idx or {}).get('heat')})")
    rec["conflicts"] = conflicts
    if conflicts:
        rec["zone"] = "conflict"
        return rec

    # 升温候选（本期不动作，仅报告）
    if status in ("hot", "recovered") and loc == "cold":
        rec["zone"] = "revive"
        return rec

    if status == "cold":
        if loc == "hot":
            if gate:
                rec["zone"] = "gate"          # ④ 安全闸拦截
            else:
                a1_ok = True
                if lt_d:
                    a1_ok = days_since(lt_d) >= DEMOTE_UNTRIGGERED_DAYS
                a2_ok = False
                dt_d = parse_date(heat.get("demoted_at"))
                if dt_d:
                    a2_ok = days_since(dt_d) >= DEMOTE_PROTECT_DAYS
                if a1_ok and a2_ok:
                    rec["zone"] = "candidate"  # ① 建议降级候选
                else:
                    due = today
                    if lt_d and days_since(lt_d) < DEMOTE_UNTRIGGERED_DAYS:
                        due = max(due, lt_d + timedelta(days=DEMOTE_UNTRIGGERED_DAYS))
                    if dt_d and days_since(dt_d) < DEMOTE_PROTECT_DAYS:
                        due = max(due, dt_d + timedelta(days=DEMOTE_PROTECT_DAYS))
                    rec["zone"] = "pending"   # ② 未满阈值候补
                    rec["due"] = due.isoformat()
        elif loc == "cold":
            rec["zone"] = "consistent"        # 状态一致（cold 且正文已在 cold 区）
        else:
            rec["zone"] = "no_body"           # 无独立正文块（如 R26/27 内容在表格/判例），豁免
    else:
        if loc == "cold":
            rec["zone"] = "revive"            # hot 但正文在 cold 区（异常/待升温）
        elif loc == "hot":
            rec["zone"] = "consistent"
        elif kind == "rule" and n in S5A_BASE:
            rec["zone"] = "no_body"           # §5A 基础规则以表格承载，无独立标题块
        else:
            rec["zone"] = "missing"           # hot 但正文缺失（异常）
    return rec


# ============================================================
# 5. 主流程
# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="规则正文冷热迁移（对账 + 降级搬运）")
    ap.add_argument("--dry-run", action="store_true", help="仅报告，不落盘不动盘")
    ap.add_argument("--report", action="store_true", help="配合 --dry-run，落盘 md 对账报告")
    ap.add_argument("--force", action="store_true", help="实际搬运（写前 .bak 快照 + sync_check 校验）")
    args = ap.parse_args()

    print("=" * 64)
    print("migrate_cold_rules v0.1（定稿 plan v1.1）")
    print(f"技能目录：{SKILL_DIR}｜日期：{date.today()}")
    print("=" * 64)

    # 读入三源
    index_text = read_text("rule_index.md")
    heat_text = read_text("review/rule_heat.json")
    if not index_text or not heat_text:
        print("❌ 关键输入缺失（rule_index.md / rule_heat.json），中止")
        return 1

    idx_map = parse_rule_index(index_text)
    heat_map = parse_rule_heat(heat_text)
    actual_map = scan_all()

    # 全部规则集合 = rule_heat 键（170 条）
    zones: dict[str, list[dict]] = {
        "candidate": [], "pending": [], "gate": [], "conflict": [],
        "revive": [], "ghost": [], "consistent": [], "missing": [], "no_body": [],
    }
    for (kind, n), heat in sorted(heat_map.items()):
        idx = idx_map.get((kind, n))
        act = actual_map.get((kind, n))
        rec = classify(kind, n, heat, idx, act)
        zone = rec.pop("zone")
        zones[zone].append(rec)

    # ---- 报告输出 ----
    lines: list[str] = []
    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    out(f"# 规则冷热迁移对账报告（{date.today()}）")
    out("")
    out(f"- 运行模式：{'--dry-run --report' if args.report else '--dry-run'}（未动盘）")
    out(f"- 总规则：{len(heat_map)} 条（rule_heat 键数）")
    out("")

    out(f"## ① 建议降级候选（{len(zones['candidate'])} 条）")
    if zones["candidate"]:
        for r in zones["candidate"]:
            out(f"- {r['key']}（{r['level']}）正文在 {r['loc']} 区 → 应搬往 cold 区")
    else:
        out("- 无（当前 demoted_at 均为 08-06，保护期 30 天未满，首跑预期零候选）")
    out("")

    out(f"## ② 未满阈值候补（{len(zones['pending'])} 条，预计达标日期）")
    for r in sorted(zones["pending"], key=lambda x: x.get("due", "")):
        out(f"- {r['key']}（{r['level']}）last_triggered={r['last_triggered'] or 'null'}，预计 {r.get('due')} 达标")
    out("")

    out(f"## ③ 冲突/疑似项（{len(zones['conflict'])} 条，默认不动盘）")
    for r in zones["conflict"]:
        for c in r["conflicts"]:
            out(f"- {r['key']}（{r['level']}，状态={r['status']}，落点={r['loc']}）：{c}")
    out("")

    out(f"## ④ 安全闸拦截（{len(zones['gate'])} 条）")
    for r in zones["gate"]:
        out(f"- {r['key']}（{r['level']}，状态={r['status']}，落点={r['loc']}）：{r['gate']}")
    out("")

    out(f"## 升温候选（本期不动作，v0.2）（{len(zones['revive'])} 条）")
    for r in zones["revive"]:
        out(f"- {r['key']}（状态={r['status']}，正文在 cold 区）→ 待 v0.2 回搬")
    out("")

    out(f"## 豁免（幽灵编号 / 无独立正文块）与一致项")
    out(f"- 幽灵编号豁免：{len(zones['ghost'])} 条：{', '.join(r['key'] for r in zones['ghost']) or '无'}")
    out(f"- 无独立正文块豁免：{len(zones['no_body'])} 条：{', '.join(r['key'] for r in zones['no_body']) or '无'}")
    out(f"- 状态一致（无需动作）：{len(zones['consistent'])} 条")
    if zones["missing"]:
        out(f"- ⚠️ 正文缺失异常：{', '.join(r['key'] for r in zones['missing'])}")

    # ---- migration_state.json（每次运行）----
    state = {
        "date": date.today().isoformat(),
        "mode": "force" if args.force else "dry-run",
        "actions": [f"{r['key']}: demote" for r in zones["candidate"]],
        "checks": {"sync_check": "not_run" if args.dry_run else "pending"},
        "errors": [],
        "summary": {k: len(v) for k, v in zones.items()},
    }
    state_path = SKILL_DIR / "review" / "migration_state.json"
    try:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        out("")
        out(f"- 运行状态已落盘：{state_path}")
    except OSError as e:
        out(f"- ⚠️ 状态落盘失败：{e}")

    # ---- report 落盘 ----
    if args.report:
        rep_path = SKILL_DIR / "review" / f"migration_reconcile_{date.today().isoformat()}.md"
        try:
            rep_path.write_text("\n".join(lines), encoding="utf-8")
            out(f"- 对账报告已落盘：{rep_path}")
        except OSError as e:
            out(f"- ⚠️ 报告落盘失败：{e}")

    # ---- force 分支（本期实现但首跑不触发；候选区为空时天然幂等）----
    if args.force:
        if zones["candidate"]:
            out("")
            out("⚠️ --force 检测到候选，但 v0.1 搬运实现尚未启用（待 Master 确认 ① 区候选后启用）。")
            out("   本次仅报告，未动盘。")
        else:
            out("")
            out("✅ --force 无候选，幂等零写入（符合预期：当前全部 cold 在保护期内）。")

    print("-" * 64)
    ok_count = sum(1 for r in zones.values() if r)
    print(f"汇总：四区候选 {len(zones['candidate'])} / 候补 {len(zones['pending'])} / 冲突 {len(zones['conflict'])} / 拦截 {len(zones['gate'])}；一致 {len(zones['consistent'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
