#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snapshot.py — 独立于发布的每日快照（D1，2026-10-22）

只读打包，不改源文件：
  - 技能目录（排除 .git / __pycache__ / *.bak*）
  - archive/daily
  - manifest.md（版本、commit、文件数、大小、sha256）

用法：
    python eval/snapshot.py [--dest DIR] [--keep 30]
默认 dest = F:/WorkBuddy/history-today/archive/backups/YYYYMMDD
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
WORKSPACE = Path("F:/WorkBuddy/history-today")
DAILY = WORKSPACE / "archive" / "daily"
EXCLUDE_DIRS = {".git", "__pycache__"}
EXCLUDE_SUFFIX = {".bak", ".pyc"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def add_tree(zf: zipfile.ZipFile, root: Path, arc_prefix: str) -> int:
    n = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in EXCLUDE_SUFFIX or ".bak-" in p.name:
            continue
        zf.write(p, arc_prefix + "/" + p.relative_to(root).as_posix())
        n += 1
    return n


def git(*args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=str(SKILL), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=15)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="")
    ap.add_argument("--keep", type=int, default=30)
    args = ap.parse_args()

    now = datetime.now()
    dest = Path(args.dest) if args.dest else WORKSPACE / "archive" / "backups" / now.strftime("%Y%m%d")
    dest.mkdir(parents=True, exist_ok=True)

    skill_zip = dest / "skill_snapshot.zip"
    daily_zip = dest / "daily_snapshot.zip"

    with zipfile.ZipFile(skill_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        n_skill = add_tree(zf, SKILL, "skill")
    with zipfile.ZipFile(daily_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        n_daily = add_tree(zf, DAILY, "daily")

    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"\*Version:\s*(v\d+\.\d+\.\d+)", skill_text)
    version = m.group(1) if m else "unknown"
    head = git("rev-parse", "--short", "HEAD")
    branch = git("branch", "--show-current")

    manifest = {
        "created_at": now.isoformat(timespec="seconds"),
        "skill_version": version,
        "git_head": head,
        "git_branch": branch,
        "skill_files": n_skill,
        "daily_files": n_daily,
        "skill_zip_bytes": skill_zip.stat().st_size,
        "daily_zip_bytes": daily_zip.stat().st_size,
        "skill_zip_sha256": sha256(skill_zip),
        "daily_zip_sha256": sha256(daily_zip),
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "manifest.md").write_text(
        "# 快照清单\n\n"
        f"- 时间：{manifest['created_at']}\n"
        f"- 版本：{version}\n"
        f"- commit：{head}（{branch}）\n"
        f"- 技能文件：{n_skill} 个，{skill_zip.stat().st_size} 字节\n"
        f"- 日更文件：{n_daily} 个，{daily_zip.stat().st_size} 字节\n"
        f"- skill sha256：`{manifest['skill_zip_sha256']}`\n"
        f"- daily sha256：`{manifest['daily_zip_sha256']}`\n",
        encoding="utf-8")

    # 只保留最近 N 个日期目录（按目录名排序，名字为 YYYYMMDD）
    backups = sorted([p for p in dest.parent.iterdir() if p.is_dir() and p.name.isdigit()])
    removed = []
    if args.keep > 0 and len(backups) > args.keep:
        for p in backups[:-args.keep]:
            shutil.rmtree(p)
            removed.append(p.name)

    print(json.dumps({**manifest, "dest": str(dest), "removed": removed},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
