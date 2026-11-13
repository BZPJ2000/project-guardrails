#!/usr/bin/env python3
"""Install a pre-commit hook that runs the fast gates, so a bypass needs a
deliberate `git commit --no-verify`.

    python install-hooks.py <project-root> [--full]

--full runs `gate.py all` instead of the fast subset (slower, stricter).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FAST = """#!/bin/sh
# project-guardrails pre-commit
[ -f guardrails.json ] || exit 0
PY=python
command -v python >/dev/null 2>&1 || PY=python3
if [ "$1" = "--full" ]; then
  "$PY" scripts/gate.py all . --quiet || exit 1
else
  "$PY" scripts/gate.py params . --quiet || exit 1
  "$PY" scripts/gate.py contracts . --quiet || exit 1
  "$PY" scripts/gate.py index . --quiet || exit 1
fi
exit 0
"""


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="install-hooks.py")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "scripts" / "gate.py").is_file():
        print("FAIL: 项目里没有 scripts/gate.py，先跑 bootstrap.py")
        return 1
    if not (root / ".git").exists():
        print("FAIL: 不是 git 仓库")
        return 1

    hooks = root / ".githooks"
    hooks.mkdir(exist_ok=True)
    target = hooks / "pre-commit"
    body = FAST.replace('if [ "$1" = "--full" ]', 'if [ "%s" = "--full" ]'
                        % ("1" if args.full else "0"))
    target.write_text(body, encoding="utf-8", newline="\n")
    try:
        target.chmod(0o755)
    except Exception:  # noqa: BLE001
        pass

    r = subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", ".githooks"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: " + (r.stderr or "").strip())
        return 1
    print(f"已安装 {target}（core.hooksPath=.githooks，模式={'full' if args.full else 'fast'}）")
    print("绕过需要显式 git commit --no-verify —— 这本身就是一次可追溯的选择。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
