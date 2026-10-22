#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_review.py — review.json 契约校验（D2，2026-10-22）

只读校验，stdin/stdout 无副作用。支持 JSON Schema 子集：
type / required / properties / enum / pattern / minimum / minLength / items / $ref。

用法：
    python eval/validate_review.py                 # 最近 10 份，核心字段
    python eval/validate_review.py --strict        # 最近 10 份，核心 + 推荐字段
    python eval/validate_review.py --all           # 全部 97 份
    python eval/validate_review.py --file a.json --file b.json
    python eval/validate_review.py --all --report-only   # 只报告，不因失败退出 1

退出码：0 = 全部通过；1 = 有失败；2 = 参数错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "review" / "schema" / "review_output.v2.json"
DAILY = Path("F:/WorkBuddy/history-today/archive/daily")
STRICT_REQUIRED = ["independence", "reviewer_model"]


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


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_files(args) -> list[Path]:
    if args.file:
        return [Path(f) for f in args.file]
    files = sorted(DAILY.glob("*_review.json"))
    if args.all:
        return files
    return files[-args.last:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--last", type=int, default=10)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    schema_path = Path(args.schema)
    if not schema_path.is_file():
        print(json.dumps({"error": f"schema 不存在: {schema_path}"}, ensure_ascii=False))
        return 2
    root = load_schema(schema_path)

    files = collect_files(args)
    results = []
    missing = Counter()
    for p in files:
        rec = {"file": p.name, "ok": False, "errors": []}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            rec["errors"] = [f"invalid_json: {str(e)[:120]}"]
            results.append(rec)
            continue
        errs = validate(data, root, root, strict=args.strict)
        rec["ok"] = not errs
        rec["errors"] = errs
        for e in errs:
            m = re.search(r"缺少必填字段 (\w+)", e)
            if m:
                missing[m.group(1)] += 1
        results.append(rec)

    passed = sum(1 for r in results if r["ok"])
    summary = {
        "schema": schema_path.name,
        "mode": "strict" if args.strict else "core",
        "total": len(results),
        "pass": passed,
        "fail": len(results) - passed,
        "compliance_rate": round(passed / len(results), 4) if results else 0,
        "missing_fields": dict(missing.most_common()),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report_only:
        return 0
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
