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

# 契约生效日从 eval/contract_dates.json 单一源读取，不再本地硬编码。
# 背景：2026-11-10 曾在 sync_check.v2_review_since 与 gate_check.V2_REVIEW_SINCE
# 各写死一份 "2026-11-10"，靠注释要求人肉同步；任何一处改动都会让同一契约出现
# 两套时间线（一处放过、一处报红）。现由 sync_check ⑪-F 校验本文件被两处引用。
# 容错（2026-11-11 修第三轮 M3）：此前是裸 json.loads，该文件损坏/缺键/被删时
# import 阶段即抛异常，A8/M1/全部 gate 检查崩溃而 sync_check 可能仍绿。
# 现与 sync_check 同款降级：读取失败或缺键 → 哨兵日期「永不强制」，
# 由 ⑪-F 的键值合法性校验报红，不崩门禁也不静默沿用旧阈值。
def _load_contract() -> dict:
    path = HERE / "contract_dates.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 损坏/缺失/编码错统一降级
        return {"v2_review_since": "9999-12-31", "claims_since": "9999-12-31",
                "_load_error": f"{path.name} 读取失败"}
    out = dict(d)
    for k in ("v2_review_since", "claims_since"):
        v = out.get(k)
        if not (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v or "")):
            out[k] = "9999-12-31"
            out["_load_error"] = f"{k}={v!r} 非法，已降级为永不强制"
    return out


CONTRACT = _load_contract()
V2_REVIEW_SINCE = CONTRACT["v2_review_since"]
# 事实账本（topic_result_{date}.json）强制落盘生效日。此前账本缺失一律 skip，
# 造成激励倒挂：不写账本放行、写了账本反被五态严判（2026-11-11 修 N1）。
CLAIMS_SINCE = CONTRACT["claims_since"]


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
        claims, cstate = vc.probe_claims(claims_path)
        # 2026-11-10 起按状态分支，不再一律 skip：键缺失/null 是违约（fail），
        # 空数组但 key_facts 有已核事实是「核实了没入账」（fail），
        # 真正的空账本（无 key_facts）才 skip。此前全部 skip，等于给违约放行。
        if cstate in ("absent", "null", "not_list", "not_object"):
            add("A8", "fail", f"claims 契约违约：状态={cstate}（顶层 claims 缺失/为空值/类型错）")
        elif claims:
            r = vc.verify(text, claims, 0.9)
            add("A8", "pass" if r["pass"] else "fail",
                f"覆盖率 {r['coverage']:.2%}，未匹配 {r['unmatched']} 项")
        else:
            try:
                raw = json.loads(claims_path.read_text(encoding="utf-8"))
                kf = raw.get("fact_check", {}).get("key_facts") if isinstance(raw, dict) else None
                n_kf = len(kf) if isinstance(kf, (dict, list)) else 0
            except Exception:
                n_kf = 0
            if n_kf:
                add("A8", "fail", f"claims 为空，但 fact_check.key_facts 有 {n_kf} 条已核事实未入账")
            else:
                add("A8", "skip", "claims 为空且无 key_facts（合法空账本）")
    else:
        # 账本文件不存在。此前一律 skip，导致激励倒挂：不写账本反而放行、
        # 写了账本却被五态严判（2026-11-11 修 N1，实锤于 11-10 那篇：
        # A8=skip 使 pass=True，而同期 11-06/11-09 因有账本反被报 fail）。
        # 现按 CLAIMS_SINCE 设阈值：该日及之后缺账本 = 违约（fail），历史不追溯。
        if article_date and article_date >= CLAIMS_SINCE:
            add("A8", "fail",
                f"claims 账本不存在（{article_date} 起强制落盘 topic_result_{article_date}.json）")
        else:
            add("A8", "skip", "claims 账本不存在（早于强制日，历史不追溯）")

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

    # ── 产物齐备性（M1-M3，2026-10-30，B-13）──
    # 补的是「内容检查全过、但产物本身缺件/错配」这一类洞：
    #   M1 本阶段应存在的审校件是否落盘   M2 review.date 是否等于文章日期
    #   M3 v2 与 v2_review 是否成对（2026-10-30 起的新约定，历史篇不追溯，故只 warn）
    art_dir = article_path.parent
    is_v2 = bool(re.search(r"_v\d+(?:\.\d+)*\.md$", article_path.name))
    review_f = art_dir / f"{article_date}_review.json"
    v2_f = art_dir / f"{article_date}_v2.md"
    v2_review_f = art_dir / f"{article_date}_v2_review.json"

    if not article_date:
        add("M1", "skip", "文件名无日期，跳过产物检查")
        add("M2", "skip", "同上")
        add("M3", "skip", "同上")
    else:
        need = v2_review_f if is_v2 else review_f
        # 2026-11-10 修：M1 原先无日期阈值，导致「v2 复检件」这一份契约有两套
        # 时间线——sync_check ⑫ 自 V2_REVIEW_SINCE 起强制、历史放过，而 M1 逐篇
        # 报 fail，使 `gate_check --recent N` 对历史篇永远全红、新信号被噪音淹没。
        # 现与 ⑫ 同口径：件存在即 pass；缺件且早于强制日 → skip；强制日及之后缺件 → fail。
        if need.is_file():
            add("M1", "pass", f"{need.name} 存在")
        elif is_v2 and article_date < V2_REVIEW_SINCE:
            add("M1", "skip", f"{need.name} 缺失，但 {article_date} 早于强制日 {V2_REVIEW_SINCE}（历史不追溯）")
        else:
            add("M1", "fail", f"{need.name} 缺失")
        if review_f.is_file():
            try:
                rdate = json.loads(review_f.read_text(encoding="utf-8")).get("date")
                add("M2", "pass" if rdate == article_date else "fail",
                    f"review.date={rdate}，文章 date={article_date}")
            except Exception as e:
                add("M2", "fail", f"review 不可解析: {str(e)[:60]}")
        else:
            add("M2", "skip", "review.json 不存在")
        if v2_f.is_file():
            add("M3", "pass" if v2_review_f.is_file() else "warn",
                f"v2 存在；{'复检件齐备' if v2_review_f.is_file() else '缺 ' + v2_review_f.name}")
        else:
            add("M3", "skip", "尚未生成 v2 定稿")

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
        # 2026-11-10 修：原为 `check(p, cfg)` 直呼，不传 claims，A8 一律走「账本不存在
        # → skip」，导致 `--recent` 的汇总恒为假绿（实测 11-09、11-06 明明 A8=fail，
        # --recent 却报 pass 3/fail 0）。现与 --article 分支同口径：按文件名自动关联
        # 同目录的 topic_result_{date}.json。
        results = []
        for p in files:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            cand = p.parent / f"topic_result_{m.group(1)}.json" if m else None
            cl = cand if (cand and cand.is_file()) else None
            results.append(check(p, cfg, claims_path=cl))
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
