"""Shared helpers for project-guardrails gates. Standard library only."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

PLACEHOLDER = "__TBD__"
TYPES = {"string", "int", "float", "bool", "array", "object"}
NUMERIC = {"int", "float"}
HEADER_KEYS = ["用途", "关键词", "输入", "输出", "文档"]
CODE_EXTS = {".py", ".java", ".rs", ".cpp", ".cc", ".c", ".h", ".hpp", ".js", ".ts", ".go"}
COMMENT_PREFIXES = ("#", "//", "/*", "*", "--", "<!--")


def finding(gate, target, ok, msg):
    return {"gate": gate, "target": str(target), "ok": bool(ok), "msg": msg}


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
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


def section(cfg, name):
    return cfg.get(name) or {}


# ---------------------------------------------------------------- glob

def glob_to_re(pattern):
    """Glob with ** support: ** crosses directories, * stays in one segment."""
    i, out = 0, ""
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 2] == "**":
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                out += ".*"
                continue
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def match_any(path, patterns):
    p = str(path).replace("\\", "/")
    return any(glob_to_re(g).match(p) for g in patterns or [])


def rel_posix(root, path):
    return str(Path(path).relative_to(Path(root))).replace("\\", "/")


# -------------------------------------------------------------- header

def parse_header(text, limit=40):
    """Read the keyword header block from the first lines of a source file."""
    fields = {}
    head = "\n".join(text.splitlines()[:limit])
    for line in head.splitlines():
        s = line.strip()
        for ch in COMMENT_PREFIXES:
            if s.startswith(ch):
                s = s[len(ch):].strip()
        for k in HEADER_KEYS:
            if k in fields:
                continue
            hit = False
            for sep in (":", "：", "|", "="):
                if s.startswith(k + sep):
                    fields[k] = s[len(k) + 1:].strip()
                    hit = True
                    break
            if hit:
                break
    return fields


def comment_ratio(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 1.0, 0
    hits = sum(1 for ln in lines if ln.strip().startswith(COMMENT_PREFIXES))
    return hits / len(lines), len(lines)


def source_files(root, cfg):
    """All source files matched by index.sources, minus index.skip."""
    icfg = section(cfg, "index")
    root = Path(root)
    patterns = icfg.get("sources") or ["apps/*/src/**"]
    skip = icfg.get("skip") or []
    found = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if not p.is_file() or p.suffix.lower() not in CODE_EXTS:
                continue
            rel = rel_posix(root, p)
            if skip and match_any(rel, skip):
                continue
            if rel not in found:
                found.append(rel)
    return found


# ----------------------------------------------------------------- git

def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def git_head(root):
    return _git(root, "rev-parse", "--short", "HEAD")


def git_changed(root):
    """Changed + untracked paths (posix), or None when not a git repo."""
    out = _git(root, "status", "--porcelain")
    if out is None:
        return None
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # [2:] tolerates both " M path" and a leading-stripped "M path"
        p = line[2:].strip().strip('"')
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        paths.append(p.replace("\\", "/"))
    return paths


# ---------------------------------------------------------------- hash

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def params_hash(root, cfg):
    p = Path(root) / paths_of(cfg).get("paramsValues", "params/params.json")
    if not p.is_file():
        return None
    return sha256_file(p)


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
