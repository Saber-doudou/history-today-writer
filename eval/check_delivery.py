#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_delivery.py — 交付链只读检查（D1 配套，2026-10-22）

检查三件事：
  1. 工作区是否干净（规则文件无未提交改动）
  2. HEAD 提交信息的版本号是否等于 SKILL.md 的 Version
  3. 远端 main 是否与本地 HEAD 一致（git ls-remote；不可达时读本地 remote ref 并标 unverified）

只读，不写任何文件，不改 git 状态。
退出码：0 = 全部通过；1 = 有硬失败；2 = 仅远端不可达（警告）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str, timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def main() -> int:
    checks: list[dict] = []

    rc, status, err = git("status", "--porcelain")
    dirty = [l for l in status.splitlines() if l.strip()]
    checks.append({
        "id": "dirty",
        "ok": rc == 0 and not dirty,
        "detail": f"{len(dirty)} 个未提交文件" if dirty else "工作区干净",
        "files": dirty[:20],
    })

    rc, head_sha, _ = git("rev-parse", "HEAD")
    rc2, subjects, _ = git("log", "-30", "--format=%s", "HEAD")
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    m_skill = re.search(r"\*Version:\s*(v\d+\.\d+\.\d+)", skill_text)
    skill_ver = m_skill.group(1) if m_skill else ""
    head_ver = ""
    for line in subjects.splitlines():
        m_head = re.match(r"(v\d+\.\d+\.\d+):", line.strip())
        if m_head:
            head_ver = m_head.group(1)
            break
    checks.append({
        "id": "version",
        "ok": bool(skill_ver) and skill_ver == head_ver,
        "detail": f"SKILL={skill_ver or '未找到'} / HEAD={head_ver or '未找到'}",
    })

    rc, out, err = git("ls-remote", "origin", "refs/heads/main", timeout=8)
    remote_mode = "ls-remote"
    remote_sha = ""
    if rc == 0 and out:
        remote_sha = out.split()[0]
    else:
        ref_file = ROOT / ".git" / "refs" / "remotes" / "origin" / "main"
        if ref_file.is_file():
            remote_sha = ref_file.read_text(encoding="utf-8").strip()
            remote_mode = "local-ref-unverified"
    checks.append({
        "id": "remote",
        "ok": bool(remote_sha) and remote_sha == head_sha,
        "warn_only": remote_mode == "local-ref-unverified",
        "detail": f"{remote_mode} / 本地={head_sha[:7]} / 远端={remote_sha[:7] or '未知'}",
        "error": err[:120] if err else "",
    })

    hard_fail = [c for c in checks if not c["ok"] and not c.get("warn_only")]
    warn = [c for c in checks if not c["ok"] and c.get("warn_only")]
    result = {
        "pass": not hard_fail,
        "checks": checks,
        "head": head_sha[:7],
        "skill_version": skill_ver,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if hard_fail:
        return 1
    if warn:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
