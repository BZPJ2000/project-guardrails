#!/usr/bin/env python3
"""Rebuild the global skill index so new skills get remembered.

    python skill-index.py                       # ~/.agents/skills -> ~/.agents/SKILLS-INDEX.md
    python skill-index.py --skills-root X --out Y
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path


def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return {}
    data, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            data[key] = kv.group(2).strip()
        elif key and line.strip():
            data[key] = (data.get(key, "") + " " + line.strip()).strip()
    for k, v in list(data.items()):
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        data[k] = v
    return data


def split_summary(desc):
    """Return (summary, trigger)."""
    trigger = ""
    m = re.search(r"Use when\s+(.+?)(?:\.\s|\.$|$)", desc, re.S)
    if m:
        trigger = " ".join(m.group(1).split())[:160]
        desc_head = desc[: m.start()].strip()
    else:
        desc_head = desc
    summary = " ".join(desc_head.split())
    if len(summary) > 110:
        summary = summary[:107].rstrip() + "..."
    return summary, (trigger or "—")


def build(skills_root, out):
    rows = []
    for d in sorted(skills_root.iterdir()):
        f = d / "SKILL.md"
        if not d.is_dir() or not f.is_file():
            continue
        fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        name = fm.get("name") or d.name
        summary, trigger = split_summary(fm.get("description", ""))
        rows.append((name, summary, trigger.replace("|", "/")))

    stamp = _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    lines = [
        "# 技能索引",
        "",
        f"由 `skill-index.py` 生成于 {stamp}，共 {len(rows)} 个技能。不要手改：新增或修改技能后重新运行本脚本。",
        "",
        "开工前先查这张表；没有合适的再联网找；都没有才自己写。",
        "",
        "| 技能 | 摘要 | 触发时机 |",
        "|---|---|---|",
    ]
    for name, summary, trigger in rows:
        lines.append(f"| `{name}` | {summary} | {trigger} |")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return rows


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    home = Path.home()
    ap = argparse.ArgumentParser(prog="skill-index.py")
    ap.add_argument("--skills-root", default=str(home / ".agents" / "skills"))
    ap.add_argument("--out", default=str(home / ".agents" / "SKILLS-INDEX.md"))
    args = ap.parse_args(argv)

    root, out = Path(args.skills_root), Path(args.out)
    if not root.is_dir():
        print(f"FAIL: 技能目录不存在 {root}")
        return 1
    rows = build(root, out)
    print(f"已索引 {len(rows)} 个技能 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
