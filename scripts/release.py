#!/usr/bin/env python3
"""Release gate: version + changelog + rollback plan, then tag.

    python release.py --version 1.2.0            # dry-run: 只检查，不打 tag
    python release.py --version 1.2.0 --apply    # 打 tag 并推送
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, read_text  # noqa: E402

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def check(root, version):
    errs, warns = [], []
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        errs.append(f"工作区不干净（{len(r.stdout.strip().splitlines())} 个文件）：先提交再发版")

    rb = root / "docs" / "flows" / "rollback.md"
    if not rb.is_file():
        errs.append("缺少 docs/flows/rollback.md：没有回滚方案不许上线")
    else:
        text = read_text(rb)
        if "## 回滚" not in text:
            errs.append("rollback.md 缺少「## 回滚」小节")
        if "```" not in text:
            errs.append("rollback.md 必须写出可执行的回滚命令（代码块）")
        if "```" in text and "git " not in text and "docker " not in text and "kubectl" not in text:
            warns.append("回滚命令里没看到 git/docker/kubectl，确认它真的能执行")

    ch = root / "CHANGELOG.md"
    if not ch.is_file():
        errs.append("缺少 CHANGELOG.md")
    else:
        text = read_text(ch)
        if version not in text:
            errs.append(f"CHANGELOG.md 里没有 {version} 的段落")

    tag = f"v{version}"
    t = subprocess.run(["git", "-C", str(root), "tag", "-l", tag],
                       capture_output=True, text=True)
    if t.stdout.strip():
        errs.append(f"tag {tag} 已存在")

    g = subprocess.run([sys.executable, str(root / "scripts" / "gate.py"), "all", ".", "--quiet"],
                       cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if g.returncode != 0:
        errs.append("门禁未通过，不能发版：" + (g.stdout or "").strip().splitlines()[-1])
    return errs, warns


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="release.py")
    ap.add_argument("--version", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--apply", action="store_true", help="真的打 tag 并推送")
    ap.add_argument("--push", action="store_true", help="同时 push tag")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    cfg, err = load_config(root)
    if err:
        print("FAIL: " + err["msg"])
        return 1
    if not SEMVER.match(args.version):
        print("FAIL: 版本号必须是 X.Y.Z")
        return 1

    errs, warns = check(root, args.version)
    for w in warns:
        print(f"  [WARN] {w}")
    for e in errs:
        print(f"  [FAIL] {e}")
    if errs:
        print("\n发版预检未通过，什么都没打。")
        return 1

    tag = f"v{args.version}"
    if not args.apply:
        print(f"预检通过。将打 tag {tag}（dry-run，未执行）")
        return 0

    r = subprocess.run(["git", "-C", str(root), "tag", "-a", tag, "-m", f"release {tag}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FAIL: " + (r.stderr or "").strip())
        return 1
    print(f"已打 tag {tag}")
    if args.push:
        p = subprocess.run(["git", "-C", str(root), "push", "origin", tag],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("已推送" if p.returncode == 0 else "推送失败: " + (p.stderr or "").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
