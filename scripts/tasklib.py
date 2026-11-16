"""Task state and change fingerprint: what one task actually touched."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

from common import (
    git_changed,
    git_head,
    read_json,
    read_text,
    rel_posix,
    symbol_hashes,
    write_json,
)

TASK_FILE = ".agent/current-task.json"
TASKS_DIR = ".agent/tasks"


def state_path(root, cfg):
    p = (cfg.get("task") or {}).get("taskFile", TASK_FILE)
    return Path(root) / p


def tasks_dir(root, cfg):
    return Path(root) / (cfg.get("task") or {}).get("tasksDir", TASKS_DIR)


def task_id(goal):
    stamp = _dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", goal).strip("-")[:24]
    return f"{stamp}-{slug or 'task'}"


def load_current(root, cfg):
    p = state_path(root, cfg)
    if not p.is_file():
        return None
    try:
        return read_json(p)
    except Exception:  # noqa: BLE001
        return None


def start(root, cfg, goal, files=None):
    root = Path(root)
    tid = task_id(goal)
    task = {
        "id": tid,
        "task": goal,
        "inScope": files or ["**"],
        "outOfScope": (cfg.get("task") or {}).get("outOfScope", []),
        "base": git_head(root),
        "startedAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(state_path(root, cfg), task)
    tdir = tasks_dir(root, cfg)
    tdir.mkdir(parents=True, exist_ok=True)
    log(tdir, tid, "start", {"goal": goal, "inScope": task["inScope"], "base": task["base"]})
    return task


def log(tdir, tid, event, data=None):
    entry = {"at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
             "event": event, "data": data or {}}
    with open(Path(tdir) / f"{tid}.log.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _git_show(root, base, rel):
    r = subprocess.run(["git", "-C", str(root), "show", f"{base}:{rel}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def _numstat(root, base):
    r = subprocess.run(["git", "-C", str(root), "diff", "--numstat", base],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            out[parts[2].replace("\\", "/")] = (int(parts[0]), int(parts[1]))
    return out


def _line_overlap(old_text, new_text):
    old = {ln.strip() for ln in old_text.splitlines() if ln.strip()}
    new = {ln.strip() for ln in new_text.splitlines() if ln.strip()}
    union = old | new
    if not union:
        return 1.0
    return len(old & new) / len(union)


def changes(root, cfg, task=None):
    """What the current task touched, at file and symbol level."""
    root = Path(root)
    task = task or load_current(root, cfg) or {}
    base = task.get("base") or git_head(root)
    changed = git_changed(root) or []
    # 任务自身的记录不算进改动面：否则写变更说明本身就会撑爆上限
    changed = [c for c in changed if not c.startswith(".agent/")]
    stats = _numstat(root, base) if base else {}

    entries, total_syms, rewritten = [], 0, []
    for rel in changed:
        p = root / rel
        cur_text = read_text(p) if p.is_file() else ""
        old_text = _git_show(root, base, rel) if base else None
        cur = symbol_hashes(cur_text, rel)
        old = symbol_hashes(old_text, rel) if old_text is not None else {}
        added = [n for n in cur if n not in old]
        removed = [n for n in old if n not in cur]
        modified = [n for n in cur if n in old and cur[n] != old[n]]
        sym_count = len(added) + len(removed) + len(modified)
        total_syms += sym_count

        add_l, del_l = stats.get(rel, (len(cur_text.splitlines()), 0))
        base_lines = len(old_text.splitlines()) if old_text else 0
        ratio = (del_l / base_lines) if base_lines else 0.0
        # 整文件重写：改动符号多，且新旧内容几乎没有共同行。
        # 只看删除行数不够——git diff 会最大化匹配，重写也常常只报少量删除。
        overlap = _line_overlap(old_text or "", cur_text)
        min_syms = int((cfg.get("task") or {}).get("rewriteMinSymbols", 3))
        max_overlap = float((cfg.get("task") or {}).get("rewriteMaxOverlap", 0.6))
        is_rewrite = bool(base_lines and sym_count >= min_syms
                          and (ratio >= 0.6 or overlap < max_overlap))
        if is_rewrite:
            rewritten.append(rel)
        entries.append({
            "path": rel, "addedLines": add_l, "deletedLines": del_l,
            "symbols": {"added": added, "removed": removed, "modified": modified},
            "symbolCount": sym_count, "deletionRatio": round(ratio, 2),
            "lineOverlap": round(overlap, 2),
            "rewrite": is_rewrite,
        })
    return {"base": base, "files": entries, "fileCount": len(entries),
            "symbolCount": total_syms, "rewritten": rewritten}


def save_snapshot(root, cfg, tid, data):
    tdir = tasks_dir(root, cfg)
    tdir.mkdir(parents=True, exist_ok=True)
    write_json(tdir / f"{tid}.json", data)


def review_path(root, cfg, tid):
    return tasks_dir(root, cfg) / f"{tid}.md"


def review_missing_sections(text, sections):
    return [s for s in sections if f"## {s}" not in text]


def digest(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False)
                        .encode("utf-8")).hexdigest()[:12]
