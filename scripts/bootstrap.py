#!/usr/bin/env python3
"""Scaffold a project with guardrails: dirs, docs skeleton, params, gates.

    python bootstrap.py --root . --tier M --parts algo,backend --git

Idempotent guard: refuses to overwrite an existing guardrails.json unless --force.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent / "assets" / "templates"


def render(name, mapping):
    text = (TPL / name).read_text(encoding="utf-8")
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def touch_keep(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").write_text("", encoding="utf-8")


def git_init(root):
    if (root / ".git").exists():
        return "已存在 .git，跳过"
    try:
        subprocess.run(["git", "init"], cwd=str(root), check=True,
                       capture_output=True, text=True)
        return "git init 完成"
    except Exception as e:  # noqa: BLE001
        return f"git init 失败（可手动执行）: {e}"


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="bootstrap.py")
    ap.add_argument("--root", default=".")
    ap.add_argument("--tier", default="M", choices=["S", "M", "L"])
    ap.add_argument("--parts", default="", help="逗号分隔，如 algo,backend")
    ap.add_argument("--name", default="", help="项目名，默认取目录名")
    ap.add_argument("--git", action="store_true", help="执行 git init")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = args.name or root.name
    date = _dt.date.today().isoformat()
    tier = args.tier

    if not args.parts.strip():
        parts = ["core"]
    else:
        parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    if tier == "S":
        parts = parts[:1]

    cfg_path = root / "guardrails.json"
    if cfg_path.exists() and not args.force:
        print(f"FAIL: {cfg_path} 已存在。要重建请加 --force。")
        return 1

    created = []
    mapping = {
        "PROJECT_NAME": name,
        "TIER": tier,
        "DATE": date,
        "PARTS": ", ".join(parts),
        "PARTS_JSON": json.dumps(parts, ensure_ascii=False),
        "PART_LIST": "\n".join(f"- `{p}`" for p in parts),
        "INDEX_SOURCES": "src/**" if tier == "S" else "apps/*/src/**",
    }

    # --- part rows + per-part docs
    rows = []
    for p in parts:
        pdir = "src" if tier == "S" else f"apps/{p}/src"
        doc = "—" if tier == "S" else f"[文档](parts/{p}.md)"
        ct = "—" if tier == "S" else f"contracts/{p}.json"
        rows.append(f"| {p} | {pdir} | （待填） | （待填） | {doc} | {ct} | （待填） |")
    created.append(write(root / "docs" / "module-map.md",
                         render("module-map.md.tpl", {**mapping, "PART_ROWS": "\n".join(rows)})))
    created.append(write(root / "AGENTS.md", render("AGENTS.md.tpl", mapping)))
    created.append(write(root / "guardrails.json", render("guardrails.json.tpl", mapping)))
    created.append(write(root / ".gitignore", render("gitignore.tpl", mapping)))
    created.append(write(root / "README.md",
                         f"# {name}\n\n档位 {tier} ｜ 部件: {', '.join(parts)}\n\n先读 `AGENTS.md`，再读 `docs/module-map.md`。\n"))

    for p in parts:
        pmap = {**mapping, "PART": p, "PART_PATH": "src" if tier == "S" else f"apps/{p}"}
        if tier != "S":
            created.append(write(root / "docs" / "parts" / f"{p}.md", render("part.md.tpl", pmap)))
            created.append(write(root / "docs" / "contracts" / f"{p}.md",
                                 render("contract-doc.md.tpl", pmap)))
            created.append(write(root / "contracts" / f"{p}.json", render("contract.json.tpl", pmap)))
            for sub in ("src", "tests", "scripts"):
                touch_keep(root / "apps" / p / sub)
        else:
            for sub in ("src", "tests", "scripts"):
                touch_keep(root / sub)

    if tier == "L":
        created.append(write(root / "docs" / "flows" / "deploy.md",
                             render("flow-deploy.md.tpl", mapping)))
        created.append(write(root / "docs" / "flows" / "rollback.md",
                             render("flow-rollback.md.tpl", mapping)))
        for name, tpl in (("modules", "design-modules.md.tpl"), ("flows", "design-flows.md.tpl"),
                          ("data", "design-data.md.tpl"), ("api", "design-api.md.tpl")):
            created.append(write(root / "docs" / "design" / f"{name}.md", render(tpl, mapping)))

    created.append(write(root / "params" / "params.schema.json",
                         render("params.schema.json.tpl", mapping)))
    created.append(write(root / "params" / "params.example.json",
                         render("params.example.json.tpl", mapping)))
    created.append(write(root / "params" / "CHANGELOG.md",
                         "# 参数变更\n\n| 日期 | 参数 | 旧值 | 新值 | 原因 | 谁改的 |\n|---|---|---|---|---|---|\n"))
    created.append(write(root / "tests" / "units.json", render("units.json.tpl", mapping)))
    touch_keep(root / "tests" / "cases")
    touch_keep(root / "tests" / "evidence")
    touch_keep(root / "data")
    touch_keep(root / ".agent" / "changes")
    created.append(write(root / ".agent" / "changes" / f"{date}-bootstrap.md",
                         f"# 初始化\n\n档位 {tier}，部件 {', '.join(parts)}。\n"))
    created.append(write(root / ".agent" / "current-task.json.example",
                         render("current-task.json.tpl", mapping)))

    # --- copy the gate into the project so it can be moved/zipped standalone
    for f in ("gate.py", "checks.py", "checks_contract.py", "checks_nav.py",
              "checks_scope.py", "checks_task.py", "checks_design.py",
              "common.py", "tasklib.py", "code-index.py",
              "task.py", "release.py", "impact.py", "publish.py", "install-hooks.py"):
        dst = root / "scripts" / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / f, dst)
        created.append(dst)

    if args.git:
        print(git_init(root))

    print(f"已生成 {len(created)} 个文件 -> {root}")
    print(f"档位 {tier} ｜ 部件: {', '.join(parts)}")
    print("\n下一步（按顺序，不许跳）:")
    print("  1. 读 docs/module-map.md，填写各部件「职责 / 不负责 / 通信方式」")
    print("  2. 把 params/params.example.json 交给负责人填写成 params/params.json")
    print("  3. 补齐 contracts/ 与 docs/contracts/ 的字段（两边必须一致）")
    print("  4. 做基线提交：git add -A && git commit -m \"chore: 初始化骨架\"")
    print("  5. 动工前 python scripts/task.py start \"<这一件事>\"  --files \"<inScope>\"")
    print("  6. 在 tests/units.json 登记第一批单元")
    print("  7. python scripts/code-index.py . && python scripts/gate.py all . --record")
    print("  8. python scripts/install-hooks.py .   # 装 pre-commit，绕过需显式 --no-verify")
    print("  9. 写 .agent/tasks/<id>.md（改了什么/为什么改/影响哪些模块/如何验证）")
    print(" 10. python scripts/task.py finish   # 门禁+汇总+提交，一个任务一个 commit")
    print("\n参数待填清单（由人回答，AI 不代填）:")
    schema = json.loads(render("params.schema.json.tpl", mapping))
    for k, v in (schema.get("params") or {}).items():
        print(f"  - {k}: {v.get('question', '')}  范围 {v.get('range')} {v.get('unit', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
