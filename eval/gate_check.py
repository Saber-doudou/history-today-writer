#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_check.py — Tier A 机器硬门禁（D7，2026-10-22）

零 token 的确定性检查，不调用模型。已实现 9 项，3 项显式 skip：
  A1 字数 500-800（正文汉字，排除标题/副标题）
  A2 双破折号（U+2014 连用两次）为 0
  A3 结尾无字数/领域脚注（F19）
  A4 标题格式 `# On This Day | ...`
  A5 副标题含日期 + 地点（· 分隔）
  A6 核心意象只出现 1 次（需 --core-image，否则 skip）
  A7 禁用短语命中为 0
  A8 数字可追溯到 claims（claims 缺失时 skip）
  A9 人名/地名在 claims 中（v0.2，skip）
  A10 日期链自洽（月日范围、无未来年份）
  A11 引语有出处标记（warn，不阻断）
  A12 政治敏感类比（人工审校，skip）

用法：
    python eval/gate_check.py --article archive/daily/2026-10-21_v2.md
    python eval/gate_check.py --recent 10 --report eval/reports/gate_recent10.json
    python eval/gate_check.py --article ... --core-image "灯" --claims ...

退出码：0 = P0 检查全过；1 = 有 P0 失败；2 = 参数/文件错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_claims as vc  # noqa: E402

ROOT = HERE.parent
DAILY = Path("F:/WorkBuddy/history-today/archive/daily")
CONFIG = HERE / "gate_config.json"
HANZI = re.compile(r"[\u4e00-\u9fff]")
DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_article(text: str) -> tuple[str, str, str]:
    lines = text.splitlines()
    title = ""
    idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            title = line.strip()
            idx = i
            break
    subtitle = ""
    if idx >= 0:
        for line in lines[idx + 1:]:
            if line.strip():
                subtitle = line.strip()
                break
    # 正文：标题之后、跳过副标题
    body_lines = lines[idx + 1:] if idx >= 0 else lines
    if subtitle and body_lines and body_lines[0].strip() == subtitle:
        body_lines = body_lines[1:]
    return title, subtitle, "\n".join(body_lines)


def check(article_path: Path, cfg: dict, core_image: str = "", claims_path: Path | None = None) -> dict:
    text = article_path.read_text(encoding="utf-8")
    title, subtitle, body = parse_article(text)
    checks = []

    def add(cid, status, detail):
        checks.append({"id": cid, "status": status, "detail": detail})

    m = re.search(r"(\d{4}-\d{2}-\d{2})", article_path.name)
    article_date = m.group(1) if m else ""

    n_hanzi = len(HANZI.findall(body))
    lo, hi = cfg["word_count"]["min"], cfg["word_count"]["max"]
    add("A1", "pass" if lo <= n_hanzi <= hi else "fail",
        f"正文汉字 {n_hanzi}（要求 {lo} 至 {hi}）")

    n_dash = body.count("——")
    add("A2", "pass" if n_dash == 0 else "fail", f"双破折号 {n_dash} 处")

    tail = "\n".join([l for l in body.splitlines() if l.strip()][-4:])
    f19 = bool(re.search(r"(字数\s*[:：]\s*\d+|全文约\s*\d+\s*字|约\s*\d+\s*字\s*$)", tail))
    add("A3", "fail" if f19 else "pass", "结尾出现字数/领域脚注" if f19 else "结尾无 F19 脚注")

    add("A4", "pass" if re.match(r"^# On This Day \| .+", title) else "fail",
        f"标题：{title[:40] or '未找到'}")

    # 兼容两种版式：显式副标题行，或日期/地点写在开头两句里
    open_text = subtitle if (subtitle and (DATE_CN.search(subtitle) or DATE_ISO.search(subtitle) or "·" in subtitle)) else "\n".join([l for l in body.splitlines() if l.strip()][:2])
    has_date = bool(DATE_CN.search(open_text) or DATE_ISO.search(open_text) or re.search(r"\d{1,2}月\d{1,2}日", open_text))
    place_markers = ("市", "州", "省", "国", "港", "城", "村", "镇", "岛", "宫", "院", "馆", "厅",
                     "实验室", "广场", "河", "桥", "山", "海", "机场", "车站", "大街", "大道", "路")
    has_place = ("·" in open_text or "｜" in open_text or any(k in open_text for k in place_markers))
    if has_date and has_place:
        add("A5", "pass", f"开头含日期与地点：{open_text[:60]}")
    elif has_date:
        add("A5", "warn", f"开头有日期但未识别地点：{open_text[:60]}")
    else:
        add("A5", "fail", f"开头无日期：{open_text[:60]}")

    if core_image:
        n = body.count(core_image)
        add("A6", "pass" if n == 1 else "fail", f"核心意象「{core_image}」出现 {n} 次")
    else:
        add("A6", "skip", cfg["deferred_checks"]["A6"])

    hits = [p for p in cfg.get("forbidden_phrases", []) if p in body]
    add("A7", "pass" if not hits else "fail", f"禁用短语：{hits or '无'}")

    if claims_path and claims_path.is_file():
        claims = vc.load_claims(claims_path)
        if claims:
            r = vc.verify(text, claims, 0.9)
            add("A8", "pass" if r["pass"] else "fail",
                f"覆盖率 {r['coverage']:.2%}，未匹配 {r['unmatched']} 项")
        else:
            add("A8", "skip", "claims 数组为空")
    else:
        add("A8", "skip", "claims 账本不存在")

    add("A9", "skip", cfg["deferred_checks"]["A9"])

    bad_dates = []
    for y, mo, d in [(int(a), int(b), int(c)) for a, b, c in DATE_CN.findall(body)] + \
                    [(int(a), int(b), int(c)) for a, b, c in DATE_ISO.findall(body)]:
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            bad_dates.append(f"{y}-{mo}-{d}")
        elif article_date and y > int(article_date[:4]) + 1:
            bad_dates.append(f"{y}-{mo}-{d} 晚于文章年份")
    add("A10", "pass" if not bad_dates else "fail",
        f"异常日期：{bad_dates[:5] or '无'}")

    win = cfg.get("quote_attribution_window", 30)
    raw_quotes = re.findall(r"“([^”]{2,80})”", body) + re.findall(r'"([^"]{2,80})"', body)
    # 只检「像话语」的引语：长度 >= 12 且含句读或人称；术语/单词/铭文不算
    quotes = [q for q in raw_quotes if len(q) >= 12 and re.search(r"[，。！？；：]|[我你他她它]", q)]
    unattributed = 0
    for q in quotes:
        pos = body.find(q)
        window = body[max(0, pos - win): pos + len(q) + win]
        if not re.search(r"(说|道|写道|回忆|据|称|问|答|表示|指出|记载)", window):
            unattributed += 1
    add("A11", "warn" if unattributed else "pass",
        f"长引语 {len(quotes)} 处（原引号 {len(raw_quotes)} 处），疑似无出处 {unattributed} 处")

    add("A12", "skip", cfg["deferred_checks"]["A12"])

    fail = [c for c in checks if c["status"] == "fail"]
    warn = [c for c in checks if c["status"] == "warn"]
    return {
        "article": str(article_path),
        "date": article_date,
        "pass": not fail,
        "p0_fail": fail,
        "warnings": warn,
        "checks": checks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article")
    ap.add_argument("--recent", type=int, default=0)
    ap.add_argument("--core-image", default="")
    ap.add_argument("--claims", default="")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    if args.article:
        p = Path(args.article)
        if not p.is_file():
            print(json.dumps({"error": f"文章不存在: {p}"}, ensure_ascii=False))
            return 2
        claims = Path(args.claims) if args.claims else None
        if claims is None:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            if m:
                cand = p.parent / f"topic_result_{m.group(1)}.json"
                claims = cand if cand.is_file() else None
        result = check(p, cfg, args.core_image, claims)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            Path(args.report).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0 if result["pass"] else 1

    if args.recent:
        files = sorted(DAILY.glob("*_v2.md"))[-args.recent:]
        results = [check(p, cfg) for p in files]
        summary = {
            "total": len(results),
            "pass": sum(1 for r in results if r["pass"]),
            "fail": sum(1 for r in results if not r["pass"]),
            "results": results,
        }
        text = json.dumps(summary, ensure_ascii=False, indent=2)
        if args.report:
            Path(args.report).write_text(text + "\n", encoding="utf-8")
        print(json.dumps({k: summary[k] for k in ("total", "pass", "fail")}, ensure_ascii=False, indent=2))
        return 0 if summary["fail"] == 0 else 1

    print(json.dumps({"error": "需要 --article 或 --recent"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    sys.exit(main())
