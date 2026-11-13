"""Scope gate: an agent may only touch what the current task declared,
and may never touch protected paths."""
from __future__ import annotations

import json
from pathlib import Path

from common import finding, git_changed, git_head, match_any, section

TASK_FILE = ".agent/current-task.json"


def check_scope(root, cfg):
    root = Path(root)
    pcfg = section(cfg, "policy")
    task_path = root / pcfg.get("taskFile", TASK_FILE)

    changed = git_changed(root)
    if changed is None:
        return [finding("scope", ".", False, "不是 git 仓库，无法判定改动范围")]

    protected = pcfg.get("protected") or []
    exempt = pcfg.get("exempt") or []
    require_task = bool(pcfg.get("requireTask", False))

    if not task_path.is_file():
        if require_task:
            return [finding("scope", TASK_FILE, False,
                            "未声明任务范围（policy.requireTask=true）：先写 .agent/current-task.json")]
        hit = [p for p in changed if match_any(p, protected) and not match_any(p, exempt)]
        if hit:
            return [finding("scope", p, False, "受保护路径被改动") for p in hit]
        return [finding("scope", TASK_FILE, True,
                        f"未声明任务范围（policy.requireTask=false），已改 {len(changed)} 个文件")]

    try:
        task = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [finding("scope", TASK_FILE, False, f"解析失败: {e}")]

    in_scope = task.get("inScope") or []
    out_scope = task.get("outOfScope") or []
    if not in_scope:
        return [finding("scope", TASK_FILE, False, "current-task.json 里 inScope 为空，等于没有边界")]

    head = git_head(root)
    out = [finding("scope", "task", True,
                   f"任务「{task.get('task', '未命名')}」｜基线 {head or '无提交'}｜改动 {len(changed)} 个文件")]

    for p in changed:
        if p == pcfg.get("taskFile", TASK_FILE):
            continue
        if match_any(p, exempt):
            out.append(finding("scope", p, True, "工作流自动产物，豁免"))
            continue
        if match_any(p, protected):
            out.append(finding("scope", p, False, "受保护路径：只读，需人工放行"))
            continue
        if out_scope and match_any(p, out_scope):
            out.append(finding("scope", p, False, "命中 outOfScope，越界"))
            continue
        if not match_any(p, in_scope):
            out.append(finding("scope", p, False, "不在 inScope 内，越界"))
        else:
            out.append(finding("scope", p, True, "范围内"))
    return out
