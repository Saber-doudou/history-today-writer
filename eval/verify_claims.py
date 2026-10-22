#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_claims.py — 正文数字与 claims 账本对账（D5，2026-10-22）

只读校验。从文章抽取「带计量单位的数字」，与 topic_result 的 claims 比对：
  - 未匹配的数字 → P0 候选（正文出现了账本里没有的值）
  - 单源 claim → P1 提示（status=single_source 或来源数 < 2）
  - 日期单独列出，不计入覆盖率（日期核验后续版本再做）

用法：
    python eval/verify_claims.py --article archive/daily/2026-10-21_v2.md \
        --claims archive/daily/topic_result_2026-10-21.json
    python eval/verify_claims.py --article ... --claims ... --min-coverage 0.9
    python eval/verify_claims.py --self-test

退出码：0 = 覆盖率达到阈值；1 = 低于阈值或有未匹配；2 = 参数/文件错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY = Path("F:/WorkBuddy/history-today/archive/daily")

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_SMALL = {"十": 10, "百": 100, "千": 1000}
CN_BIG = {"万": 10_000, "亿": 100_000_000}
UNITS = ["%", "％", "公里", "千米", "米", "英尺", "小时", "分钟", "秒",
         "美元", "股", "人", "户", "盏", "种", "本", "吨", "公斤", "磅", "度"]
UNIT_NORM = {"％": "%", "千米": "公里"}


def cn_int(s: str) -> int:
    total = section = num = 0
    for ch in s:
        if ch in CN_DIGITS:
            num = CN_DIGITS[ch]
        elif ch in CN_SMALL:
            if num == 0:
                num = 1
            section += num * CN_SMALL[ch]
            num = 0
        elif ch in CN_BIG:
            section += num
            total += section * CN_BIG[ch]
            section = num = 0
    return total + section + num


def cn_to_num(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    if "点" in s:
        a, b = s.split("点", 1)
        integer = cn_int(a) if a else 0
        decimals = "".join(str(CN_DIGITS.get(ch, "")) for ch in b if ch in CN_DIGITS)
        if not decimals:
            return float(integer)
        return float(f"{integer}.{decimals}")
    if all(ch in CN_DIGITS or ch in CN_SMALL or ch in CN_BIG for ch in s):
        return float(cn_int(s))
    return None


def parse_value(text: str) -> list[float]:
    """把 claim 的 value/display 解析为若干候选数值。支持 1,234 / 1.2万 / 13.5-14.5。"""
    text = str(text).strip().replace(",", "").replace("，", "")
    parts = re.split(r"\s*(?:至|到|-|–|—|/)\s*", text)
    out: list[float] = []
    for part in parts:
        if not part:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(万|亿)?", part)
        if m:
            v = float(m.group(1))
            if m.group(2) == "万":
                v *= 10_000
            elif m.group(2) == "亿":
                v *= 100_000_000
            out.append(v)
            continue
        v = cn_to_num(part)
        if v is not None:
            out.append(v)
    return out


@dataclass
class Token:
    text: str
    value: float
    unit: str
    pos: int
    kind: str  # measured / percent / date


def extract_tokens(article: str) -> tuple[list[Token], list[Token]]:
    measured: list[Token] = []
    dates: list[Token] = []
    unit_alt = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))

    # 日期单独抽，不进覆盖率
    for m in re.finditer(r"(\d{4})年(\d{1,2})月(\d{1,2})日", article):
        dates.append(Token(m.group(0), float(m.group(1)), "年", m.start(), "date"))

    # 阿拉伯数字 + 可选「多/余」 + 单位
    ar = re.compile(rf"(\d[\d,]*(?:\.\d+)?)\s*(万|亿)?(?:多|余)?\s*({unit_alt})")
    for m in ar.finditer(article):
        raw = m.group(1).replace(",", "")
        mult = 10_000 if m.group(2) == "万" else (100_000_000 if m.group(2) == "亿" else 1)
        unit = UNIT_NORM.get(m.group(3), m.group(3))
        try:
            v = float(raw) * mult
        except ValueError:
            continue
        kind = "percent" if unit == "%" else "measured"
        measured.append(Token(m.group(0), v, unit, m.start(), kind))

    # 中文数字 + 可选「多/余」 + 单位
    cn_chars = "零一二两三四五六七八九十百千万亿点"
    cn = re.compile(rf"([{cn_chars}]{{2,}})(?:多|余)?\s*({unit_alt})")
    for m in cn.finditer(article):
        v = cn_to_num(m.group(1))
        if v is None:
            continue
        unit = UNIT_NORM.get(m.group(2), m.group(2))
        kind = "percent" if unit == "%" else "measured"
        measured.append(Token(m.group(0), v, unit, m.start(), kind))

    # 百分之X
    for m in re.finditer(rf"百分之([{cn_chars}]{{1,}})", article):
        v = cn_to_num(m.group(1))
        if v is not None:
            measured.append(Token(m.group(0), v, "%", m.start(), "percent"))

    # 去重：同一位置只留一个
    seen = set()
    uniq = []
    for t in sorted(measured, key=lambda x: x.pos):
        if t.pos in seen:
            continue
        seen.add(t.pos)
        uniq.append(t)
    return uniq, dates


def load_claims(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("claims", []) if isinstance(data, dict) else []


def claim_values(c: dict) -> list[float]:
    vals = parse_value(c.get("value", ""))
    if not vals and c.get("display"):
        vals = parse_value(c.get("display", ""))
    return vals


def match_token(t: Token, claims: list[dict]) -> dict | None:
    for c in claims:
        for v in claim_values(c):
            if v == 0:
                continue
            if t.kind == "percent" or v < 100:
                tol = max(0.05, abs(v) * 0.01)
            else:
                tol = max(1.0, abs(v) * 0.01)
            if abs(t.value - v) <= tol:
                cu = c.get("unit", "")
                if t.unit and cu and UNIT_NORM.get(cu, cu) != t.unit and t.kind != "percent":
                    continue
                return c
    return None


def verify(article: str, claims: list[dict], min_coverage: float = 0.9) -> dict:
    tokens, dates = extract_tokens(article)
    matched, unmatched = [], []
    for t in tokens:
        c = match_token(t, claims)
        rec = {"text": t.text, "value": t.value, "unit": t.unit, "pos": t.pos, "kind": t.kind}
        if c:
            rec["claim_id"] = c.get("id", "")
            matched.append(rec)
        else:
            rec["snippet"] = article[max(0, t.pos - 24): t.pos + len(t.text) + 24]
            unmatched.append(rec)

    single = []
    for c in claims:
        srcs = c.get("sources") or []
        if c.get("status") == "single_source" or len(srcs) < 2 or (c.get("cross_check") or 0) < 2:
            single.append({"id": c.get("id", ""), "claim": c.get("claim", ""),
                           "status": c.get("status", ""), "sources": len(srcs)})

    total = len(tokens)
    coverage = round(len(matched) / total, 4) if total else 1.0
    return {
        "tokens_measured": total,
        "matched": len(matched),
        "unmatched": len(unmatched),
        "coverage": coverage,
        "pass": coverage >= min_coverage and not unmatched,
        "unmatched_tokens": unmatched,
        "single_source_claims": single,
        "dates_unverified": len(dates),
        "details": matched,
    }


def self_test() -> int:
    claims = [
        {"id": "C1", "claim": "成交量", "value": "604,330,000", "unit": "股",
         "status": "verified", "cross_check": 2,
         "sources": [{"url": "https://a", "title": "a", "retrieved_at": "x"},
                     {"url": "https://b", "title": "b", "retrieved_at": "x"}]},
        {"id": "C2", "claim": "跌幅", "value": "22.6", "unit": "%",
         "status": "verified", "cross_check": 2,
         "sources": [{"url": "https://a", "title": "a", "retrieved_at": "x"},
                     {"url": "https://b", "title": "b", "retrieved_at": "x"}]},
        {"id": "C3", "claim": "耗时", "value": "13.5", "unit": "小时",
         "status": "verified", "cross_check": 2,
         "sources": [{"url": "https://a", "title": "a", "retrieved_at": "x"},
                     {"url": "https://b", "title": "b", "retrieved_at": "x"}]},
    ]
    ok_article = "成交六亿多股，跌幅22.6%，耗时13.5小时。"
    bad_article = "成交六千零四十万股，跌幅22.6%。"
    r1 = verify(ok_article, claims, 0.9)
    r2 = verify(bad_article, claims, 0.9)
    print(json.dumps({"self_test": True, "ok_case": r1, "bad_case": r2}, ensure_ascii=False, indent=2))
    passed = r1["matched"] >= 2 and r2["unmatched"] >= 1
    return 0 if passed else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article")
    ap.add_argument("--claims")
    ap.add_argument("--min-coverage", type=float, default=0.9)
    ap.add_argument("--out")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.article:
        print(json.dumps({"error": "缺少 --article"}, ensure_ascii=False))
        return 2

    article_path = Path(args.article)
    if not article_path.is_file():
        print(json.dumps({"error": f"文章不存在: {article_path}"}, ensure_ascii=False))
        return 2

    claims_path = Path(args.claims) if args.claims else None
    if claims_path is None:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", article_path.name)
        if m:
            cand = DAILY / f"topic_result_{m.group(1)}.json"
            if cand.is_file():
                claims_path = cand
    if claims_path is None or not claims_path.is_file():
        print(json.dumps({"error": "claims 文件不存在，且无法自动推断"}, ensure_ascii=False))
        return 2

    article = article_path.read_text(encoding="utf-8")
    claims = load_claims(claims_path)
    result = verify(article, claims, args.min_coverage)
    result.update({"article": str(article_path), "claims_file": str(claims_path),
                   "claims_count": len(claims), "min_coverage": args.min_coverage})
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if (result["pass"] or args.report_only) else 1


if __name__ == "__main__":
    sys.exit(main())
