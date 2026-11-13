#!/usr/bin/env python3
"""Impact analysis: given the current diff, what must be read, checked, re-run.

    python impact.py <project-root> [--json]

Read-only helper: it never fails the build, it tells you what the change touches.
Exit 1 only when the project has no guardrails.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import git_changed, load_config, paths_of, read_json, section  # noqa: E402


def part_of(path, parts, root):
    for p in parts:
        if (root / "apps" / p).is_dir() and path.startswith(f"apps/{p}/"):
            return p
        if not (root / "apps" / p).is_dir() and path.startswith("src/"):
            return p
    return None


def build(root):
    root = Path(root)
    cfg, err = load_config(root)
    if err:
        print("FAIL: " + err["msg"])
        return 1
    parts = cfg.get("parts") or []
    paths = paths_of(cfg)
    changed = git_changed(root) or []
    task_file = section(cfg, "policy").get("taskFile", ".agent/current-task.json")
    changed = [c for c in changed if c != task_file]

    units = []
    up = root / paths.get("units", "tests/units.json")
    if up.is_file():
        try:
            units = read_json(up).get("units") or []
        except Exception:  # noqa: BLE001
            units = []

    rows, affected_parts = [], []
    for path in changed:
        part = part_of(path, parts, root)
        if part is None:
            rows.append({"path": path, "part": None, "docs": [], "contracts": [], "units": []})
            continue
        if part not in affected_parts:
            affected_parts.append(part)
        docs = [f"docs/parts/{part}.md"]
        contracts = [f"contracts/{part}.json", f"docs/contracts/{part}.md"]
        rerun = [u["id"] for u in units
                 if isinstance(u, dict) and u.get("id")
                 and (part in str(u.get("entry", "")) or part in str(u.get("id", "")))]
        rows.append({"path": path, "part": part, "docs": docs,
                     "contracts": contracts, "units": rerun})

    rerun_all = sorted({u for r in rows for u in r["units"]})
    contracts_all = sorted({c for r in rows for c in r["contracts"]})
    docs_all = sorted({d for r in rows for d in r["docs"]})
    return {
        "changed": rows,
        "parts": affected_parts,
        "docs": docs_all,
        "contracts": contracts_all,
        "units": rerun_all,
        "unknown": [r["path"] for r in rows if r["part"] is None],
    }


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="impact.py")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    data = build(root)
    if isinstance(data, int):
        return data

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    rows = data["changed"]
    if not rows:
        print("没有未提交的改动。")
        return 0

    print(f"改动 {len(rows)} 个文件，涉及部件: {', '.join(data['parts']) or '（无）'}")
    print("\n| 改动文件 | 部件 | 必读文档 | 必重跑单元 |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| `{r['path']}` | {r['part'] or '?'} | "
              f"{', '.join(r['docs']) or '—'} | {', '.join(r['units']) or '—'} |")

    if data["docs"]:
        print("\n必读:")
        for d in data["docs"]:
            print(f"  - {d}")
    if data["contracts"]:
        print("必查契约:")
        for c in data["contracts"]:
            print(f"  - {c}")
    if data["units"]:
        print("必重跑:")
        for u in data["units"]:
            print(f"  - {u}")
    if data["unknown"]:
        print("\n未归属任何部件（检查是否越界或漏登记）:")
        for p in data["unknown"]:
            print(f"  - {p}")
    print("\n跑完记得刷新证据: 重跑单元 -> python scripts/gate.py evidence .")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
