"""Shared helpers for project-guardrails gates. Standard library only."""
from __future__ import annotations

import json
import re
from pathlib import Path

PLACEHOLDER = "__TBD__"
TYPES = {"string", "int", "float", "bool", "array", "object"}
NUMERIC = {"int", "float"}


def finding(gate, target, ok, msg):
    return {"gate": gate, "target": str(target), "ok": bool(ok), "msg": msg}


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def count_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return len(f.read().splitlines())


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_config(root):
    p = Path(root) / "guardrails.json"
    if not p.is_file():
        return None, finding("config", "guardrails.json", False,
                             "缺少 guardrails.json，先跑 bootstrap.py")
    try:
        cfg = read_json(p)
    except Exception as e:  # noqa: BLE001
        return None, finding("config", "guardrails.json", False, f"解析失败: {e}")
    if not isinstance(cfg, dict):
        return None, finding("config", "guardrails.json", False, "顶层必须是对象")
    return cfg, None


def paths_of(cfg):
    return cfg.get("paths") or {}


def unit_ids(root, cfg):
    p = Path(root) / paths_of(cfg).get("units", "tests/units.json")
    if not p.is_file():
        return set()
    try:
        data = read_json(p)
    except Exception:  # noqa: BLE001
        return set()
    return {u.get("id") for u in data.get("units", []) if isinstance(u, dict)}


def doc_field_names(text):
    """Field names from the first column of the table under '## 字段'."""
    m = re.search(r"^##\s*字段\s*$", text, re.M)
    if not m:
        return None
    tail = text[m.end():]
    stop = re.search(r"^##\s", tail, re.M)
    if stop:
        tail = tail[: stop.start()]
    names = []
    for line in tail.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].strip("`").strip()
        if not first or set(first) <= set("-: "):
            continue
        if first in ("字段", "field", "Field"):
            continue
        names.append(first)
    return names


def doc_version(text):
    m = re.search(r"^##\s*版本\s*$", text, re.M)
    if not m:
        return None
    for line in text[m.end():].splitlines():
        s = line.strip()
        if s:
            return s.strip("`").strip()
    return None
