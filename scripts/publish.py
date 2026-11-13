#!/usr/bin/env python3
"""Pre-push audit and publish: check, then create the repo and push.

    python publish.py <root> --name my-project [--private|--public] [--dry-run]

Audit always runs. Without --dry-run it then creates the GitHub repo (when no
remote exists) and pushes. Nothing is uploaded when the audit fails.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

# Patterns are regexes, not bare substrings: `sk-` alone would hit every
# "task-" in the tree. Each pair is (label, compiled pattern).
SECRET_RE = [
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("fine_grained_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("assignment", re.compile(r"(?i)\b(password|passwd|api[_-]?key|secret|token)"
                              r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}")),
]
SELF = Path(__file__).resolve()
IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
               ".idea", ".vscode", "dist", "build", "target"}
MAX_FILE_MB = 50


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def tracked_files(root):
    r = run(["git", "-C", str(root), "ls-files"], cwd=root)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.splitlines() if p.strip()]


def audit(root, allow_big):
    errs, warns, notes = [], [], []
    root = Path(root)

    if not (root / ".git").exists():
        errs.append("不是 git 仓库：先 git init（或 bootstrap.py --git）")
        return errs, warns, notes

    dirty = run(["git", "-C", str(root), "status", "--porcelain"]).stdout.strip()
    if dirty:
        errs.append(f"有未提交改动（{len(dirty.splitlines())} 个文件）：先 commit，别推半成品")

    files = tracked_files(root)
    if not files:
        errs.append("没有任何已跟踪文件")
        return errs, warns, notes
    notes.append(f"将上传 {len(files)} 个文件")

    gi = root / ".gitignore"
    if not gi.is_file():
        warns.append("没有 .gitignore，确认没把 .env / 虚拟环境 / 数据目录带上去")
    else:
        text = gi.read_text(encoding="utf-8", errors="replace")
        for pat in (".env", "node_modules", ".venv", "__pycache__"):
            if pat not in text:
                warns.append(f".gitignore 未包含 {pat}")

    big = []
    for rel in files:
        p = root / rel
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size > MAX_FILE_MB * 1024 * 1024:
            big.append((rel, round(size / 1024 / 1024, 1)))
    if big:
        msg = "超过 50MB 的文件（GitHub 单文件上限 100MB）: " + \
              ", ".join(f"{n}({s}MB)" for n, s in big[:5])
        (warns if allow_big else errs).append(msg)

    allow = []
    ignore_file = root / ".publishignore"
    if ignore_file.is_file():
        allow = [ln.strip() for ln in ignore_file.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]

    hits = []
    for rel in files:
        p = root / rel
        if not p.is_file() or p.stat().st_size > 1_000_000:
            continue
        if p.resolve() == SELF:
            continue
        if allow and any(fnmatch(rel, pat) for pat in allow):
            continue
        if any(fnmatch(part, d) for part in Path(rel).parts for d in IGNORE_DIRS):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for label, rx in SECRET_RE:
            if rx.search(text):
                hits.append((rel, label))
                break
    if hits:
        errs.append("疑似密钥/凭证: " + ", ".join(f"{f}({p})" for f, p in hits[:8])
                    + "（误报可写进 .publishignore）")

    for required, label in (("README.md", "README"), ("LICENSE", "LICENSE")):
        if not (root / required).exists():
            warns.append(f"缺少 {label}（公开仓库建议补上）")

    return errs, warns, notes


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="publish.py")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--name", default="")
    ap.add_argument("--public", action="store_true", help="公开（默认私有）")
    ap.add_argument("--dry-run", action="store_true", help="只审计，不建仓不推送")
    ap.add_argument("--allow-big", action="store_true", help="允许 >50MB 文件通过审计")
    ap.add_argument("--yes", action="store_true", help="审计通过后不再确认")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    name = args.name or root.name

    errs, warns, notes = audit(root, args.allow_big)
    print(f"预检: {root}")
    for n in notes:
        print(f"  · {n}")
    for w in warns:
        print(f"  [WARN] {w}")
    for e in errs:
        print(f"  [FAIL] {e}")

    if errs:
        print("\n预检未通过，未上传任何内容。")
        return 1
    print("预检通过。")

    if args.dry_run:
        print("--dry-run：到此为止，未建仓、未推送。")
        return 0

    remote = run(["git", "-C", str(root), "remote"]).stdout.strip()
    if not remote:
        vis = "--public" if args.public else "--private"
        cmd = ["gh", "repo", "create", name, vis, "--source=.", "--remote=origin",
               "--push", "--description", f"{name}"]
        print(f"建仓并推送: gh repo create {name} {vis} --source=. --push")
        r = run(cmd, cwd=root)
        if r.returncode != 0:
            print("FAIL: " + (r.stderr or r.stdout).strip()[:500])
            return 1
        url = run(["gh", "repo", "view", name, "--json", "url"]).stdout.strip()
        print("完成: " + (url or "(gh repo view 未返回地址)"))
        return 0

    print("已有 remote，直接推送: git push -u origin HEAD")
    r = run(["git", "-C", str(root), "push", "-u", "origin", "HEAD"])
    if r.returncode != 0:
        print("FAIL: " + (r.stderr or r.stdout).strip()[:500])
        return 1
    print("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
