#!/usr/bin/env python3
"""project-guardrails gate. Exit 0 = all pass, 1 = at least one failure.

    python gate.py all <project-root>
    python gate.py docs|contracts|params|evidence|index|scope|flows <root> [--json] [--record]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    git_changed,
    git_head,
    load_config,
    params_hash,
    paths_of,
    write_json,
)
from checks import TIER_GATES, run_gate  # noqa: E402

GATES = ["all", "docs", "contracts", "params", "evidence", "index",
         "task", "design", "scope", "flows"]


def write_report(root, gate, tier, findings):
    cfg, _ = load_config(root)
    base = Path(root) / paths_of(cfg or {}).get("reports", "reports/gate")
    stamp = _dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    fails = [f for f in findings if not f["ok"]]
    payload = {
        "generatedAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate": gate,
        "tier": tier,
        "passed": len(findings) - len(fails),
        "failed": len(fails),
        "commit": git_head(root),
        "paramsHash": params_hash(root, cfg or {}),
        "changedFiles": git_changed(root) or [],
        "findings": findings,
    }
    path = base / f"{stamp}-{gate}.json"
    i = 1
    while path.exists():  # 同一秒内多次运行也不覆盖历史报告
        i += 1
        path = base / f"{stamp}-{gate}-{i}.json"
    write_json(path, payload)
    return path


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
    ap.add_argument("--record", action="store_true", help="落盘报告到 reports/gate/")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    findings = run_gate(root, args.gate)
    fails = [f for f in findings if not f["ok"]]

    cfg, _ = load_config(root)
    tier = (cfg or {}).get("tier", "?")

    report = write_report(root, args.gate, tier, findings) if args.record else None

    if args.json:
        print(json.dumps({
            "root": str(root),
            "gate": args.gate,
            "tier": tier,
            "total": len(findings),
            "failed": len(fails),
            "report": str(report) if report else None,
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
    if report:
        print(f"报告: {report}")
    if fails:
        print("门禁未通过：停下，把上面的失败项交回给人，不许绕过。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
