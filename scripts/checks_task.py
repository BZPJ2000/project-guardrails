"""Task gate: one task at a time, bounded blast radius, review note present."""
from __future__ import annotations

from pathlib import Path

import tasklib
from common import finding, git_changed, git_head, section


def check_task(root, cfg):
    root = Path(root)
    tcfg = section(cfg, "task")
    tier = str(cfg.get("tier", "M"))
    out = []

    task = tasklib.load_current(root, cfg)
    changed = git_changed(root)
    if changed is None:
        if tier == "S":
            return [finding("task", ".", True, "S 档且非 git 仓库：不要求任务记录")]
        return [finding("task", ".", False, "不是 git 仓库，无法记录任务")]
    if task is None:
        if not changed:
            return [finding("task", "current-task", True, "无进行中任务，工作区干净")]
        if tcfg.get("requireTask", True) and tier != "S":
            return [finding("task", "current-task", False,
                            f"有 {len(changed)} 个未提交改动但没有 current-task.json：先 task.py start")]
        return [finding("task", "current-task", True, "未声明任务（S 档或 requireTask=false）")]

    tid = task.get("id") or "?"
    if not task.get("base"):
        out.append(finding("task", tid, False, "task 没有 base 提交：先做基线提交再 start"))

    data = tasklib.changes(root, cfg, task)
    max_files = int(tcfg.get("maxFiles", 15))
    max_syms = int(tcfg.get("maxSymbols", 20))
    out.append(finding("task", "改动面",
                       data["fileCount"] <= max_files,
                       f"{data['fileCount']} 个文件（上限 {max_files}）"))
    out.append(finding("task", "改动面",
                       data["symbolCount"] <= max_syms,
                       f"{data['symbolCount']} 个符号（上限 {max_syms}）"))
    if data["rewritten"]:
        out.append(finding("task", data["rewritten"][0], False,
                           "整文件重写（删除超过原文 60% 且改了 3 个以上符号）：拆成多个任务"))
    else:
        out.append(finding("task", "重写检测", True, "没有整文件重写"))

    sections = tcfg.get("reviewSections") or ["改了什么", "为什么改", "影响哪些模块", "如何验证"]
    rp = tasklib.review_path(root, cfg, tid)
    if not rp.is_file():
        out.append(finding("task", f".agent/tasks/{tid}.md", False,
                           "缺少变更说明：" + " / ".join(sections)))
    else:
        from common import read_text
        missing = tasklib.review_missing_sections(read_text(rp), sections)
        out.append(finding("task", f".agent/tasks/{tid}.md", not missing,
                           ("缺少小节: " + ", ".join(missing)) if missing else "四节齐全"))

        logp = tasklib.tasks_dir(root, cfg) / f"{tid}.log.jsonl"
        out.append(finding("task", f".agent/tasks/{tid}.log.jsonl", logp.is_file(),
                           "有任务日志" if logp.is_file() else "缺少任务日志：task.py start 会建"))

    head = git_head(root)
    out.append(finding("task", "基线", True, f"base={data['base']} head={head or '无提交'}"))
    return out
