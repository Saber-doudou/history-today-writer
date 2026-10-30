#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_review.py — 审校产物契约校验（D2 起，2026-10-22；2026-10-30 分族路由）

只读校验，stdin/stdout 无副作用。支持 JSON Schema 子集：
type / required / properties / enum / pattern / minimum / minLength / items / $ref。

两种审校产物、两套契约（2026-10-30 起）：
    {YYYY-MM-DD}_review.json        L1 审校       → review_output.v2.json
    {YYYY-MM-DD}_v2_review.json     v2 改后复检   → review_recheck.v1.json
文件名是路由依据（产物命名即契约）。旧的连字符写法 `-v2_review.json` 仍能识别，
但会在 sync_check ⑫ 命名检查中报 ❌（入库宽容、门禁严格）。

归一化（防腐层）：把生产者写法差异适配到规范形态后再判合规，避免把「写法差异」
误判成「契约失败」。规范动作只有三类，且必须是等价变换：
    - independence 连字符/空格/大小写 → 下划线小写别名
    - severity 大小写 → 小写
不做猜测性补字段。raw 与 normalized 两套结果都输出，raw 违规进 warnings。

用法：
    python eval/validate_review.py                 # 最近 10 份，核心字段
    python eval/validate_review.py --strict        # 核心 + 推荐字段
    python eval/validate_review.py --all           # 全部
    python eval/validate_review.py --file a.json --file b.json
    python eval/validate_review.py --all --report-only
    python eval/validate_review.py --no-normalize  # 关闭归一化，看原始形态

退出码：0 = 全部通过；1 = 归一化后仍有失败；2 = 参数或 schema 错误
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "review" / "schema"
SCHEMA_REVIEW = SCHEMA_DIR / "review_output.v2.json"
SCHEMA_RECHECK = SCHEMA_DIR / "review_recheck.v1.json"
DAILY = Path("F:/WorkBuddy/history-today/archive/daily")
STRICT_REQUIRED = ["independence", "reviewer_model"]

# 复检产物的文件名特征：日期后接 -v2 / _v2 / -v2.1 再跟 _review.json
RECHECK_NAME = re.compile(r"(?:^|[-_])v\d+(?:\.\d+)*_review\.json$")

INDEPENDENCE_ALIASES = {
    "independent-subprocess": "independent_subprocess",
    "independent_subprocess": "independent_subprocess",
    "independent subprocess": "independent_subprocess",
}


def route_schema(path: Path) -> str:
    """按文件名判定产物族：recheck / review。"""
    return "recheck" if RECHECK_NAME.search(path.name) else "review"


def schema_path_for(family: str) -> Path:
    return SCHEMA_RECHECK if family == "recheck" else SCHEMA_REVIEW


def normalize(data):
    """等价形态归一（不改语义、不补字段）。返回 (归一化副本, 变换记录)。"""
    d = copy.deepcopy(data)
    changes: list[str] = []
    ind = d.get("independence")
    if isinstance(ind, str):
        key = ind.strip().lower().replace("  ", " ")
        alias = INDEPENDENCE_ALIASES.get(key)
        if alias and alias != ind:
            changes.append(f"independence: {ind!r} → {alias!r}")
            d["independence"] = alias
    issues = d.get("issues")
    if isinstance(issues, list):
        for i, it in enumerate(issues):
            if isinstance(it, dict) and isinstance(it.get("severity"), str):
                low = it["severity"].strip().lower()
                if low != it["severity"]:
                    changes.append(f"issues[{i}].severity: {it['severity']!r} → {low!r}")
                    it["severity"] = low
    return d, changes


def type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def resolve(schema: dict, root: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/"):
        return schema
    node = root
    for part in ref[2:].split("/"):
        node = node.get(part, {})
    return node


def validate(instance, schema: dict, root: dict, path: str = "$", strict: bool = False) -> list[str]:
    errors: list[str] = []
    schema = resolve(schema, root)

    expected = schema.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        if not any(type_ok(instance, t) for t in types):
            errors.append(f"{path}: 类型应为 {expected}，实际 {type(instance).__name__}")
            return errors

    enum = schema.get("enum")
    if enum is not None and instance not in enum:
        errors.append(f"{path}: 值 {instance!r} 不在枚举 {enum}")

    if isinstance(instance, str):
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, instance):
            errors.append(f"{path}: 字符串 {instance!r} 不匹配 {pattern}")
        min_len = schema.get("minLength")
        if min_len is not None and len(instance) < min_len:
            errors.append(f"{path}: 长度 {len(instance)} < {min_len}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: 值 {instance} < 最小值 {minimum}")

    if isinstance(instance, dict):
        required = list(schema.get("required", []))
        if strict and path == "$":
            required += [k for k in STRICT_REQUIRED if k not in required]
        for key in required:
            if key not in instance:
                errors.append(f"{path}: 缺少必填字段 {key}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                errors.extend(validate(instance[key], sub, root, f"{path}.{key}", strict=False))

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], root, f"{path}[{i}]", strict=False))

    return errors


def count_mismatch(data) -> list[str]:
    """计数与 issues 列表是否对账（只做提示，不阻断：历史文件存在口径差异）。"""
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        return []
    sev = Counter()
    for it in data["issues"]:
        if isinstance(it, dict):
            s = str(it.get("severity", "")).strip().lower()
            if s in ("p0", "p1", "p2"):
                sev[s] += 1
    out = []
    for key in ("p0_count", "p1_count", "p2_count"):
        declared = data.get(key)
        sev_key = key.split("_")[0]  # p0 / p1 / p2
        actual = sev.get(sev_key, 0)
        if isinstance(declared, int) and declared != actual:
            out.append(f"{key}={declared} 但 issues 中 {sev_key} 有 {actual} 条")
    return out


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_files(args) -> list[Path]:
    if args.file:
        return [Path(f) for f in args.file]
    files = [p for p in sorted(DAILY.glob("*_review.json")) if p.is_file()]
    if args.all:
        return files
    return files[-args.last:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--last", type=int, default=10)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--schema", default=None, help="强制单 schema（覆盖自动路由）")
    ap.add_argument("--no-normalize", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    forced = Path(args.schema) if args.schema else None
    if forced and not forced.is_file():
        print(json.dumps({"error": f"schema 不存在: {forced}"}, ensure_ascii=False))
        return 2

    files = collect_files(args)
    roots: dict[str, dict] = {}
    results = []
    missing = Counter()
    by_family = Counter()
    raw_only = []

    for p in files:
        family = route_schema(p)
        by_family[family] += 1
        sp = forced or schema_path_for(family)
        if family not in roots:
            if not sp.is_file():
                print(json.dumps({"error": f"schema 不存在: {sp}"}, ensure_ascii=False))
                return 2
            roots[family] = load_schema(sp)
        root = roots[family]

        rec = {"file": p.name, "schema": sp.name, "family": family,
               "ok": False, "errors": [], "raw_errors": [], "warnings": []}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            rec["errors"] = [f"invalid_json: {str(e)[:120]}"]
            results.append(rec)
            continue

        raw_errs = validate(data, root, root, strict=args.strict)
        norm, changes = (copy.deepcopy(data), []) if args.no_normalize else normalize(data)
        errs = validate(norm, root, root, strict=args.strict)

        rec["ok"] = not errs
        rec["errors"] = errs
        rec["raw_errors"] = raw_errs
        if raw_errs and not errs:
            rec["warnings"].extend(f"归一化已吸收：{c}" for c in changes)
            raw_only.append(p.name)
        rec["warnings"].extend(count_mismatch(norm))
        for e in errs:
            m = re.search(r"缺少必填字段 (\w+)", e)
            if m:
                missing[m.group(1)] += 1
        results.append(rec)

    passed = sum(1 for r in results if r["ok"])
    raw_passed = sum(1 for r in results if not r["raw_errors"])
    summary = {
        "mode": "strict" if args.strict else "core",
        "normalize": not args.no_normalize,
        "routed": dict(by_family),
        "total": len(results),
        "pass": passed,
        "fail": len(results) - passed,
        "compliance_rate": round(passed / len(results), 4) if results else 0,
        "raw_compliance_rate": round(raw_passed / len(results), 4) if results else 0,
        "raw_only_fail": raw_only,
        "missing_fields": dict(missing.most_common()),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report_only:
        return 0
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
