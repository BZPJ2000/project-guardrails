#!/usr/bin/env python3
"""Build the keyword -> code index.

    python code-index.py <project-root>

Reads every source file's keyword header plus its top-level symbols, then writes
docs/code-index.md (human) and docs/code-index.json (machine).
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    comment_ratio,
    load_config,
    parse_header,
    read_text,
    section,
    source_files,
    write_json,
)

JAVA = re.compile(r"^\s*(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
                  r"(?:abstract\s+)?(?:class|interface|enum|record)\s+(\w+)")
JAVA_METHOD = re.compile(r"^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?"
                         r"[\w<>\[\],\.\s]+?\s+(\w+)\s*\(")
RUST = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:const\s+)?(?:unsafe\s+)?fn\s+(\w+)")
RUST_TYPE = re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)")
JS_FUNC = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)")
JS_CLASS = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)")
GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)")
CPP_FUNC = re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?[\w:<>,\*&\s]+?\s+(\w+)\s*\([^;]*\)\s*(?:const\s*)?\{?\s*$")
CPP_TYPE = re.compile(r"^\s*(?:class|struct)\s+(\w+)")
BANNED = {"if", "for", "while", "switch", "return", "else", "catch", "sizeof", "new", "delete"}


def _py_symbols(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    return [(n.name, n.lineno) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]


def _generic_symbols(text, ext):
    rules = {
        ".java": (JAVA, JAVA_METHOD),
        ".rs": (RUST, RUST_TYPE),
        ".js": (JS_FUNC, JS_CLASS),
        ".ts": (JS_FUNC, JS_CLASS),
        ".go": (GO_FUNC,),
        ".c": (CPP_TYPE, CPP_FUNC),
        ".h": (CPP_TYPE, CPP_FUNC),
        ".cpp": (CPP_TYPE, CPP_FUNC),
        ".cc": (CPP_TYPE, CPP_FUNC),
        ".hpp": (CPP_TYPE, CPP_FUNC),
    }.get(ext, ())
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for rx in rules:
            m = rx.match(line)
            if m and m.group(1) not in BANNED:
                out.append((m.group(1), i))
                break
    return out


def build(root):
    root = Path(root)
    cfg, err = load_config(root)
    if err:
        print("FAIL: " + err["msg"])
        return 1
    icfg = section(cfg, "index")
    files = source_files(root, cfg)
    if not files:
        print("FAIL: index.sources 没有匹配到任何源文件")
        return 1

    entries, keywords, mtimes = [], [], []
    for rel in files:
        p = root / rel
        text = read_text(p)
        header = parse_header(text)
        ext = p.suffix.lower()
        syms = _py_symbols(text) if ext == ".py" else _generic_symbols(text, ext)
        ratio, _ = comment_ratio(text)
        purpose = header.get("用途", "")
        terms = [t.strip() for t in re.split(r"[,，、;；\s]+", header.get("关键词", "")) if t.strip()]
        entries.append({
            "path": rel,
            "purpose": purpose,
            "keywords": terms,
            "symbols": [{"name": n, "line": ln} for n, ln in syms],
            "commentRatio": round(ratio, 3),
        })
        file_line = 1
        for t in terms:
            keywords.append({"term": t, "path": rel, "line": file_line, "purpose": purpose})
        for n, ln in syms:
            keywords.append({"term": n, "path": rel, "line": ln, "purpose": purpose})
        mtimes.append(p.stat().st_mtime)

    payload = {
        "generatedAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sourceMtimeMax": max(mtimes),
        "files": entries,
        "keywords": sorted(keywords, key=lambda k: (k["term"].lower(), k["path"])),
    }
    write_json(root / icfg.get("json", "docs/code-index.json"), payload)

    lines = [
        "# 代码索引",
        "",
        f"由 `scripts/code-index.py` 生成于 {payload['generatedAt']}，"
        f"覆盖 {len(entries)} 个源文件、{len(keywords)} 个关键词。",
        "",
        "查代码的顺序：先在本表按关键词找到文件:行 → 打开那一个文件 → 看文件头的「不变量」确认。",
        "",
        "## 按关键词查",
        "",
        "| 关键词 / 符号 | 文件:行 | 职责 |",
        "|---|---|---|",
    ]
    for k in payload["keywords"]:
        lines.append(f"| `{k['term']}` | `{k['path']}:{k['line']}` | {k['purpose'] or '—'} |")
    lines += ["", "## 文件清单", "", "| 文件 | 职责 | 符号 | 注释率 |", "|---|---|---|---|"]
    for e in entries:
        syms = ", ".join(s["name"] for s in e["symbols"][:6]) or "—"
        lines.append(f"| `{e['path']}` | {e['purpose'] or '—'} | {syms} | {e['commentRatio']:.0%} |")
    lines.append("")

    md = root / icfg.get("out", "docs/code-index.md")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"已生成 {len(entries)} 个文件 / {len(keywords)} 条关键词 -> {md}")
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="code-index.py")
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args(argv)
    return build(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
