#!/usr/bin/env python3
"""Self-tests for project-guardrails gates.

Every test builds a throwaway project, so the gates are proven to block,
not assumed to. Run:

    python tests/test_gate.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))

import checks  # noqa: E402

HEADER = '''"""
用途: 任务排序
关键词: 排序, 优先级, sortTask, scheduleSeq
输入: contracts/algo.json
输出: scheduleSeq
文档: docs/parts/algo.md
"""
'''
REVIEW = """## 改了什么
排序逻辑

## 为什么改
优先级权重改为从 params 读

## 影响哪些模块
algo、前端排序展示

## 如何验证
python scripts/gate.py all .
证据 tests/evidence/algo__sortTask.json
"""


def sh(args, cwd=None, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return r


def boot(root, tier="M", parts="algo", git=True):
    cmd = [sys.executable, str(SKILL / "scripts" / "bootstrap.py"),
           "--root", str(root), "--tier", tier, "--parts", parts]
    if git:
        cmd.append("--git")
    sh(cmd)
    if git:
        sh(["git", "-C", str(root), "config", "user.name", "t"])
        sh(["git", "-C", str(root), "config", "user.email", "t@t"])
    return root


def baseline(root):
    sh(["git", "-C", str(root), "add", "-A"])
    sh(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
        "commit", "-qm", "chore: baseline"], check=False)


def run_py(root, script, *args, check=False):
    r = subprocess.run([sys.executable, str(Path(root) / "scripts" / script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check:
        assert r.returncode == 0, r.stdout + r.stderr
    return r


def cfgo(root):
    return checks.load_config(root)[0]


def fails(findings):
    return [f for f in findings if not f["ok"]]


def fill_params(root, value=10):
    (root / "params" / "params.json").write_text(
        json.dumps({"sampleSize": value}), encoding="utf-8")


def params_hash(root):
    return "sha256:" + hashlib.sha256((root / "params" / "params.json").read_bytes()).hexdigest()


def write_unit(root, body=None, unit_id="algo/sortTask"):
    entry = root / "apps" / "algo" / "src" / "sortTask.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(body if body is not None else
                     HEADER + "def sort_tasks(t):\n    return sorted(t)\n", encoding="utf-8")
    (root / "tests" / "units.json").write_text(json.dumps({"units": [
        {"id": unit_id, "entry": "apps/algo/src/sortTask.py", "source": [],
         "budgetMs": 200, "minCases": 5}]}), encoding="utf-8")
    run_py(root, "code-index.py", root, check=True)
    return entry


def add_evidence(root, unit_id="algo/sortTask", **over):
    ev = {"unit": unit_id, "runId": "t-1", "durationMs": 42,
          "command": "python tests/runUnit.py " + unit_id,
          "env": {"language": "python", "version": "3.12", "os": "test"},
          "exitCode": 0, "codeVersion": "test", "paramsHash": params_hash(root),
          "cases": {"total": 7, "passed": 7, "failed": 0, "boundary": 2, "invalidInput": 2}}
    ev.update(over)
    p = root / "tests" / "evidence" / (unit_id.replace("/", "__") + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ev), encoding="utf-8")
    return p


def start_task(root, goal="改排序", files="**"):
    return run_py(root, "task.py", "--root", root, "start", goal, "--files", files)


def task_id(root):
    return json.loads((root / ".agent" / "current-task.json").read_text(encoding="utf-8"))["id"]


def write_review(root):
    p = root / ".agent" / "tasks" / (task_id(root) + ".md")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(REVIEW, encoding="utf-8")
    return p


def green(root):
    """A project that passes every gate."""
    boot(root, git=True)
    fill_params(root)
    baseline(root)
    start_task(root)
    write_unit(root)
    add_evidence(root)
    write_review(root)
    return root


class T(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # ------------------------------------------------------------ 基础

    def test_fresh_project_blocks_on_params_evidence_task(self):
        boot(self.root)
        bad = fails(checks.run_gate(self.root, "all"))
        msgs = " ".join(f["msg"] for f in bad)
        self.assertIn("params.json", msgs)
        self.assertIn("单元", msgs)
        self.assertIn("current-task", msgs)

    def test_placeholder_param_is_blocked(self):
        boot(self.root)
        (self.root / "params" / "params.json").write_text(
            json.dumps({"sampleSize": "__TBD__"}), encoding="utf-8")
        self.assertTrue(fails(checks.check_params(self.root, cfgo(self.root))))

    def test_out_of_range_param_is_blocked(self):
        boot(self.root)
        fill_params(self.root, 99999)
        self.assertTrue(fails(checks.check_params(self.root, cfgo(self.root))))

    def test_unknown_param_key_is_blocked(self):
        boot(self.root)
        (self.root / "params" / "params.json").write_text(
            json.dumps({"sampleSize": 10, "ghost": 1}), encoding="utf-8")
        self.assertTrue(fails(checks.check_params(self.root, cfgo(self.root))))

    def test_green_project_passes_all_gates(self):
        green(self.root)
        bad = fails(checks.run_gate(self.root, "all"))
        self.assertEqual(bad, [], bad)

    # ------------------------------------------------------------ 证据

    def test_stale_evidence_is_blocked(self):
        green(self.root)
        entry = self.root / "apps" / "algo" / "src" / "sortTask.py"
        future = os.path.getmtime(entry) + 600
        os.utime(entry, (future, future))
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("比源码旧" in f["msg"] for f in findings), findings)

    def test_thin_evidence_is_blocked(self):
        green(self.root)
        ev = self.root / "tests" / "evidence" / "algo__sortTask.json"
        data = json.loads(ev.read_text(encoding="utf-8"))
        data["cases"] = {"total": 2, "passed": 2, "failed": 0, "boundary": 0, "invalidInput": 0}
        ev.write_text(json.dumps(data), encoding="utf-8")
        msgs = " ".join(f["msg"] for f in fails(checks.check_evidence(self.root, cfgo(self.root))))
        self.assertIn("下限", msgs)
        self.assertIn("边界", msgs)

    def test_slow_unit_is_blocked(self):
        green(self.root)
        ev = self.root / "tests" / "evidence" / "algo__sortTask.json"
        data = json.loads(ev.read_text(encoding="utf-8"))
        data["durationMs"] = 9999
        ev.write_text(json.dumps(data), encoding="utf-8")
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("预算" in f["msg"] for f in findings), findings)

    def test_evidence_without_provenance_is_blocked(self):
        green(self.root)
        ev = self.root / "tests" / "evidence" / "algo__sortTask.json"
        data = json.loads(ev.read_text(encoding="utf-8"))
        data.pop("paramsHash")
        ev.write_text(json.dumps(data), encoding="utf-8")
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("paramsHash" in f["msg"] for f in findings), findings)

    def test_changing_params_invalidates_evidence(self):
        green(self.root)
        self.assertEqual(fails(checks.check_evidence(self.root, cfgo(self.root))), [])
        fill_params(self.root, 20)
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("paramsHash" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------ 契约

    def test_contract_doc_drift_is_blocked(self):
        boot(self.root)
        doc = self.root / "docs" / "contracts" / "algo.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace(
            "| inputId | string | 是 |", "| ghost | string | 是 |"), encoding="utf-8")
        findings = fails(checks.check_contracts(self.root, cfgo(self.root)))
        self.assertTrue(any("字段不一致" in f["msg"] for f in findings), findings)

    def test_version_drift_is_blocked(self):
        boot(self.root)
        c = self.root / "contracts" / "algo.json"
        data = json.loads(c.read_text(encoding="utf-8"))
        data["version"] = "2.0.0"
        c.write_text(json.dumps(data), encoding="utf-8")
        findings = fails(checks.check_contracts(self.root, cfgo(self.root)))
        self.assertTrue(any("版本" in f["msg"] for f in findings), findings)

    def test_derived_field_needs_produced_by_unit(self):
        boot(self.root)
        c = self.root / "contracts" / "algo.json"
        data = json.loads(c.read_text(encoding="utf-8"))
        data["fields"].append({"name": "scheduleSeq", "type": "int", "required": True,
                               "derived": True, "producedBy": "algo/ghost"})
        c.write_text(json.dumps(data), encoding="utf-8")
        doc = self.root / "docs" / "contracts" / "algo.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace(
            "| inputId | string | 是 | — | 人 | （待填） |",
            "| inputId | string | 是 | — | 人 | （待填） |\n| scheduleSeq | int | 是 | — | 算法 | 派生 |"),
            encoding="utf-8")
        findings = fails(checks.check_contracts(self.root, cfgo(self.root)))
        self.assertTrue(any("producedBy" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------ 文档

    def test_overlong_doc_is_blocked(self):
        boot(self.root)
        p = self.root / "docs" / "parts" / "algo.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n填充\n" * 130, encoding="utf-8")
        findings = fails(checks.check_docs(self.root, cfgo(self.root)))
        self.assertTrue(any("上限" in f["msg"] for f in findings), findings)

    def test_missing_section_is_blocked(self):
        boot(self.root)
        p = self.root / "docs" / "parts" / "algo.md"
        p.write_text(p.read_text(encoding="utf-8").replace("## 变更影响", "## 其它"), encoding="utf-8")
        findings = fails(checks.check_docs(self.root, cfgo(self.root)))
        self.assertTrue(any("缺少小节" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------ 索引

    def test_missing_keyword_header_is_blocked(self):
        green(self.root)
        (self.root / "apps" / "algo" / "src" / "bare.py").write_text(
            "def bare():\n    return 1\n", encoding="utf-8")
        run_py(self.root, "code-index.py", self.root)
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("缺关键词头" in f["msg"] for f in findings), findings)

    def test_stale_index_is_blocked(self):
        green(self.root)
        entry = self.root / "apps" / "algo" / "src" / "sortTask.py"
        future = os.path.getmtime(entry) + 600
        os.utime(entry, (future, future))
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("旧" in f["msg"] for f in findings), findings)

    def test_missing_index_json_is_blocked(self):
        green(self.root)
        (self.root / "docs" / "code-index.json").unlink()
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("缺少代码索引" in f["msg"] for f in findings), findings)

    def test_low_comment_ratio_is_blocked(self):
        boot(self.root)
        body = HEADER + "".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(40))
        (self.root / "apps" / "algo" / "src").mkdir(parents=True, exist_ok=True)
        (self.root / "apps" / "algo" / "src" / "big.py").write_text(body, encoding="utf-8")
        run_py(self.root, "code-index.py", self.root)
        cfg = cfgo(self.root)
        cfg["index"]["minCommentRatio"] = 0.2
        findings = fails(checks.check_index(self.root, cfg))
        self.assertTrue(any("注释率" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------ 范围

    def test_scope_blocks_file_outside_in_scope(self):
        boot(self.root, git=True)
        baseline(self.root)
        start_task(self.root, files="apps/algo/src/**")
        (self.root / "stray.txt").write_text("x", encoding="utf-8")
        findings = fails(checks.check_scope(self.root, cfgo(self.root)))
        self.assertTrue(any("不在 inScope" in f["msg"] for f in findings), findings)

    def test_scope_blocks_protected_path(self):
        boot(self.root, git=True)
        fill_params(self.root)
        baseline(self.root)
        start_task(self.root, files="params/**")
        fill_params(self.root, 33)
        findings = fails(checks.check_scope(self.root, cfgo(self.root)))
        self.assertTrue(any("受保护" in f["msg"] for f in findings), findings)

    def test_scope_exempts_generated_artifacts(self):
        boot(self.root, git=True)
        baseline(self.root)
        start_task(self.root, files="apps/algo/src/**")
        (self.root / "apps" / "algo" / "src" / "n.py").write_text(HEADER, encoding="utf-8")
        (self.root / "docs" / "code-index.json").write_text("{}", encoding="utf-8")
        (self.root / "tests" / "evidence" / "x.json").parent.mkdir(parents=True, exist_ok=True)
        (self.root / "tests" / "evidence" / "x.json").write_text("{}", encoding="utf-8")
        (self.root / "reports" / "gate").mkdir(parents=True, exist_ok=True)
        (self.root / "reports" / "gate" / "r.json").write_text("{}", encoding="utf-8")
        self.assertEqual(fails(checks.check_scope(self.root, cfgo(self.root))), [])

    def test_scope_requires_task_before_coding(self):
        boot(self.root, git=True)
        baseline(self.root)
        (self.root / "x.txt").write_text("x", encoding="utf-8")
        findings = fails(checks.check_scope(self.root, cfgo(self.root)))
        self.assertTrue(any("未声明任务范围" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------ 任务

    def test_task_start_writes_state_and_log(self):
        boot(self.root, git=True)
        baseline(self.root)
        start_task(self.root, "改排序", "apps/algo/src/**")
        tid = task_id(self.root)
        self.assertTrue((self.root / ".agent" / "tasks" / f"{tid}.log.jsonl").is_file())
        state = json.loads((self.root / ".agent" / "current-task.json").read_text(encoding="utf-8"))
        self.assertEqual(state["task"], "改排序")
        self.assertTrue(state["base"])

    def test_task_gate_requires_review_note(self):
        boot(self.root, git=True)
        fill_params(self.root)
        baseline(self.root)
        start_task(self.root)
        write_unit(self.root)
        add_evidence(self.root)
        findings = fails(checks.check_task(self.root, cfgo(self.root)))
        self.assertTrue(any("缺少变更说明" in f["msg"] for f in findings), findings)

    def test_task_gate_rejects_too_many_files(self):
        boot(self.root, git=True)
        baseline(self.root)
        start_task(self.root, files="**")
        for i in range(16):
            (self.root / f"f{i}.txt").write_text("x", encoding="utf-8")
        write_review(self.root)
        findings = fails(checks.check_task(self.root, cfgo(self.root)))
        self.assertTrue(any("上限" in f["msg"] for f in findings), findings)

    def test_task_gate_detects_whole_file_rewrite(self):
        boot(self.root, git=True)
        p = self.root / "apps" / "algo" / "src" / "legacy.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(HEADER + "".join(f"def f{i}():\n    return {i}\n" for i in range(5)),
                     encoding="utf-8")
        run_py(self.root, "code-index.py", self.root)
        baseline(self.root)
        start_task(self.root)
        p.write_text(HEADER + "".join(f"def f{i}():\n    x = {i}\n    return x * 2\n" for i in range(5)),
                     encoding="utf-8")
        write_review(self.root)
        findings = fails(checks.check_task(self.root, cfgo(self.root)))
        self.assertTrue(any("整文件重写" in f["msg"] for f in findings), findings)

    def test_task_finish_commits_and_clears_state(self):
        green(self.root)
        r = run_py(self.root, "task.py", "--root", self.root, "finish")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.root / ".agent" / "current-task.json").exists())
        log = sh(["git", "-C", str(self.root), "log", "-1", "--format=%s"]).stdout
        self.assertIn("task(", log)

    def test_task_revert_undoes_only_one_task(self):
        boot(self.root, git=True)
        fill_params(self.root)
        write_unit(self.root)
        add_evidence(self.root)
        baseline(self.root)
        a = self.root / "a.txt"
        b = self.root / "b.txt"
        a.write_text("v1", encoding="utf-8")
        b.write_text("v1", encoding="utf-8")
        baseline(self.root)

        start_task(self.root, files="a.txt")
        tid1 = task_id(self.root)
        a.write_text("v2", encoding="utf-8")
        write_review(self.root)
        run_py(self.root, "task.py", "--root", self.root, "finish", check=True)

        start_task(self.root, files="b.txt")
        b.write_text("v2", encoding="utf-8")
        write_review(self.root)
        run_py(self.root, "task.py", "--root", self.root, "finish", check=True)

        r = run_py(self.root, "task.py", "--root", self.root, "revert", tid1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(a.read_text(encoding="utf-8"), "v1")
        self.assertEqual(b.read_text(encoding="utf-8"), "v2")

    # ------------------------------------------------------------ 设计

    def test_design_required_for_tier_l(self):
        boot(self.root, tier="L", parts="algo,backend")
        (self.root / "docs" / "design" / "data.md").unlink()
        findings = fails(checks.check_design(self.root, cfgo(self.root)))
        self.assertTrue(any("缺少设计说明书" in f["msg"] for f in findings), findings)

    def test_design_skipped_for_tier_m(self):
        boot(self.root, tier="M")
        findings = checks.check_design(self.root, cfgo(self.root))
        self.assertTrue(all(f["ok"] for f in findings), findings)

    # ------------------------------------------------------------ 发布

    def test_release_requires_rollback_plan(self):
        boot(self.root, git=True)
        (self.root / "CHANGELOG.md").write_text("## 1.0.0\n- init\n", encoding="utf-8")
        baseline(self.root)
        r = run_py(self.root, "release.py", "--version", "1.0.0", "--root", self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("回滚", r.stdout)
        tags = sh(["git", "-C", str(self.root), "tag", "-l"]).stdout.strip()
        self.assertEqual(tags, "")

    def test_release_rejects_bad_semver(self):
        boot(self.root, git=True)
        r = run_py(self.root, "release.py", "--version", "1.0", "--root", self.root)
        self.assertEqual(r.returncode, 1)

    # ------------------------------------------------------------ CLI

    def test_cli_exit_codes_and_report(self):
        boot(self.root)
        cli = self.root / "scripts" / "gate.py"
        r = subprocess.run([sys.executable, str(cli), "all", str(self.root), "--record"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 1)
        green_root = Path(self._tmp.name) / "green"
        green_root.mkdir()
        green(green_root)
        r = subprocess.run([sys.executable, str(green_root / "scripts" / "gate.py"),
                            "all", str(green_root), "--record"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        reports = list((green_root / "reports" / "gate").glob("*.json"))
        self.assertGreaterEqual(len(reports), 1)
        payload = json.loads(reports[-1].read_text(encoding="utf-8"))
        for key in ("gate", "tier", "passed", "failed", "findings", "paramsHash"):
            self.assertIn(key, payload)

    def test_tier_s_skips_heavy_gates(self):
        boot(self.root, tier="S", parts="tool", git=True)
        cfg = cfgo(self.root)
        self.assertTrue(all(f["ok"] for f in checks.check_contracts(self.root, cfg)))
        self.assertTrue(all(f["ok"] for f in checks.check_design(self.root, cfg)))

    def test_tier_l_requires_flow_docs(self):
        boot(self.root, tier="L", parts="algo")
        for f in (self.root / "docs" / "flows").glob("*.md"):
            f.unlink()
        self.assertTrue(fails(checks.check_flows(self.root, cfgo(self.root))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
