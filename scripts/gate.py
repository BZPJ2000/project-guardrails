#!/usr/bin/env python3
"""project-guardrails gate. Exit 0 = all pass, 1 = at least one failure.

    python gate.py all <project-root>
    python gate.py docs|contracts|params|evidence|flows <project-root> [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checks import TIER_GATES, load_config, run_gate  # noqa: E402

GATES = ["all", "docs", "contracts", "params", "evidence", "flows"]


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="gate.py", description="project-guardrails gates")
    ap.add_argument("gate", choices=GATES)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="machine readable output")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    findings = run_gate(root, args.gate)
    fails = [f for f in findings if not f["ok"]]

    cfg, _ = load_config(root)
    tier = (cfg or {}).get("tier", "?")

    if args.json:
        print(json.dumps({
            "root": str(root),
            "gate": args.gate,
            "tier": tier,
            "total": len(findings),
            "failed": len(fails),
            "findings": findings,
        }, ensure_ascii=False, indent=2))
        return 1 if fails else 0

    print(f"gate={args.gate}  root={root}  tier={tier}")
    for f in findings:
        if args.quiet and f["ok"]:
            continue
        mark = "PASS" if f["ok"] else "FAIL"
        target = f["target"]
        prefix = f["gate"] + "/"
        if not target.startswith(prefix):
            target = prefix + target
        print(f"  [{mark}] {target} - {f['msg']}")
    print(f"结果: 通过 {len(findings) - len(fails)} / 失败 {len(fails)}")
    if fails:
        print("门禁未通过：停下，把上面的失败项交回给人，不许绕过。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
