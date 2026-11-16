#!/usr/bin/env python3
"""One task at a time: declare, work, verify, commit, or revert exactly one task.

    python task.py start "把优先级权重改成从 params 读" --files "apps/algo/src/**"
    python task.py status
    python task.py finish --no-commit
    python task.py revert 20261116T153012-优先级权重
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasklib  # noqa: E402
from common import git_head, load_config, write_json  # noqa: E402


def run_gate(root):
    r = subprocess.run([sys.executable, str(Path(root) / "scripts" / "gate.py"), "all", ".", "--quiet"],
                       cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def cmd_start(root, cfg, args):
    task = tasklib.start(root, cfg, args.goal, args.files.split(",") if args.files else None)
    print(f"任务已开始: {task['id']}")
    print(f"  inScope : {', '.join(task['inScope'])}")
    print(f"  base    : {task['base'] or '（无提交，先做一次基线 commit）'}")
    print(f"  变更说明: .agent/tasks/{task['id']}.md（四节写全才能 finish）")
    return 0


def cmd_status(root, cfg, args):
    task = tasklib.load_current(root, cfg)
    if not task:
        print("没有进行中的任务。")
        return 0
    data = tasklib.changes(root, cfg, task)
    print(f"任务 {task['id']}: {task['task']}")
    print(f"基线 {data['base']}  改动 {data['fileCount']} 个文件 / {data['symbolCount']} 个符号")
    for e in data["files"]:
        syms = e["symbols"]
        detail = ", ".join(f"+{n}" for n in syms["added"][:3]) or ""
        detail += (", " if detail else "") + ", ".join(f"~{n}" for n in syms["modified"][:3])
        flag = "  [整文件重写]" if e["rewrite"] else ""
        print(f"  {e['path']} (+{e['addedLines']}/-{e['deletedLines']}) {detail}{flag}")
    return 0


def cmd_finish(root, cfg, args):
    task = tasklib.load_current(root, cfg)
    if not task:
        print("FAIL: 没有进行中的任务，先 task.py start")
        return 1

    code, out = run_gate(root)
    if code != 0:
        print("门禁未通过，任务不能结束：\n" + out.strip())
        return 1

    data = tasklib.changes(root, cfg, task)
    data.update({"id": task["id"], "task": task["task"], "finishedAt": task["startedAt"]})
    tasklib.save_snapshot(root, cfg, task["id"], data)
    tasklib.log(tasklib.tasks_dir(root, cfg), task["id"], "finish", data)
    print(f"改动: {data['fileCount']} 个文件 / {data['symbolCount']} 个符号 -> .agent/tasks/{task['id']}.json")

    if args.no_commit:
        print("--no-commit：未提交。")
        return 0

    files = "\n".join(f"  - {e['path']} (+{e['addedLines']}/-{e['deletedLines']})"
                      for e in data["files"]) or "  - （无）"
    msg = (f"task({task['id']}): {task['task']}\n\n"
           f"改动 {data['fileCount']} 个文件 / {data['symbolCount']} 个符号\n{files}\n\n"
           f"验证: gate all 通过，报告见 reports/gate/\n")
    # 先清掉临时状态再 add：否则 current-task.json 会被卷进提交，回退时冲突
    tasklib.state_path(root, cfg).unlink(missing_ok=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True)
    r = subprocess.run(["git", "-C", str(root), "commit", "-m", msg],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FAIL: 提交失败（可能是 pre-commit 拦截）：\n" + (r.stdout or "") + (r.stderr or ""))
        return 1
    print("已提交：一个任务对应一个 commit，回退就 revert 这一个。")
    return 0


def cmd_revert(root, cfg, args):
    r = subprocess.run(["git", "-C", str(root), "log", "--format=%H", "-n", "1",
                        "--grep", f"task({args.task_id})"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    sha = (r.stdout or "").strip().splitlines()
    if not sha:
        print(f"FAIL: 找不到 task({args.task_id}) 对应的提交")
        return 1
    rev = subprocess.run(["git", "-C", str(root), "revert", "--no-edit", sha[0]],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if rev.returncode != 0:
        print("FAIL: 回退有冲突，需要人工确认（后续任务可能依赖它）：\n"
              + (rev.stdout or "") + (rev.stderr or ""))
        return 1
    print(f"已回退 {sha[0][:7]}，只撤这一个任务。")
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="task.py")
    ap.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("goal")
    s.add_argument("--files", default="", help="逗号分隔的 inScope，默认 **")
    s.set_defaults(fn=cmd_start)

    st = sub.add_parser("status")
    st.set_defaults(fn=cmd_status)

    f = sub.add_parser("finish")
    f.add_argument("--no-commit", action="store_true")
    f.set_defaults(fn=cmd_finish)

    rv = sub.add_parser("revert")
    rv.add_argument("task_id")
    rv.set_defaults(fn=cmd_revert)

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg, err = load_config(root)
    if err:
        print("FAIL: " + err["msg"])
        return 1
    return args.fn(root, cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
