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


def boot(root, tier="M", parts="algo", git=False):
    cmd = [sys.executable, str(SKILL / "scripts" / "bootstrap.py"),
           "--root", str(root), "--tier", tier, "--parts", parts]
    if git:
        cmd.append("--git")
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def run_py(root, script, *args):
    r = subprocess.run([sys.executable, str(root / "scripts" / script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


def cfgo(root):
    return checks.load_config(root)[0]


def fails(findings):
    return [f for f in findings if not f["ok"]]


def fill_params(root, value=10):
    (root / "params" / "params.json").write_text(
        json.dumps({"sampleSize": value}), encoding="utf-8")


def add_unit(root, unit_id="algo/sortTask", body=None):
    entry = root / "apps" / "algo" / "src" / "sortTask.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(body if body is not None else
                     HEADER + "def sort(tasks):\n    return sorted(tasks)\n",
                     encoding="utf-8")
    data = {"units": [{"id": unit_id, "entry": "apps/algo/src/sortTask.py",
                       "source": [], "budgetMs": 200, "minCases": 5}]}
    (root / "tests" / "units.json").write_text(json.dumps(data), encoding="utf-8")
    r = run_py(root, "code-index.py", root)
    assert r.returncode == 0, r.stdout + r.stderr
    return entry


def params_hash(root):
    data = (root / "params" / "params.json").read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def add_evidence(root, unit_id="algo/sortTask", **over):
    ev = {"unit": unit_id, "runId": "t-1", "startedAt": "2026-11-13T23:00:00+08:00",
          "durationMs": 42, "command": "python tests/runUnit.py " + unit_id,
          "env": {"language": "python", "version": "3.12", "os": "test"},
          "exitCode": 0, "codeVersion": "test", "paramsHash": params_hash(root),
          "cases": {"total": 7, "passed": 7, "failed": 0, "boundary": 2, "invalidInput": 2}}
    ev.update(over)
    p = root / "tests" / "evidence" / (unit_id.replace("/", "__") + ".json")
    p.write_text(json.dumps(ev), encoding="utf-8")
    return p


def commit_all(root):
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-qm", "init"], check=True, capture_output=True)


class T(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # ---------------------------------------------------------- 基础拦截

    def test_bootstrap_then_gate_blocks_missing_params(self):
        boot(self.root)
        findings = checks.run_gate(self.root, "all")
        msgs = " ".join(f["msg"] for f in fails(findings))
        self.assertIn("params.json", msgs)
        self.assertIn("单元", msgs)

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

    def test_full_green_project_passes(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root)
        bad = fails(checks.run_gate(self.root, "all"))
        self.assertEqual(bad, [], bad)

    # ------------------------------------------------------------- 证据

    def test_stale_evidence_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        entry = add_unit(self.root)
        add_evidence(self.root)
        future = os.path.getmtime(entry) + 600
        os.utime(entry, (future, future))
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("比源码旧" in f["msg"] for f in findings), findings)

    def test_thin_evidence_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        ev = add_evidence(self.root)
        data = json.loads(ev.read_text(encoding="utf-8"))
        data["cases"] = {"total": 2, "passed": 2, "failed": 0, "boundary": 0, "invalidInput": 0}
        ev.write_text(json.dumps(data), encoding="utf-8")
        msgs = " ".join(f["msg"] for f in fails(checks.check_evidence(self.root, cfgo(self.root))))
        self.assertIn("下限", msgs)
        self.assertIn("边界", msgs)
        self.assertIn("非法输入", msgs)

    def test_slow_unit_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root, durationMs=9999)
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("预算" in f["msg"] for f in findings), findings)

    def test_evidence_without_provenance_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        ev = add_evidence(self.root)
        data = json.loads(ev.read_text(encoding="utf-8"))
        data.pop("paramsHash")
        ev.write_text(json.dumps(data), encoding="utf-8")
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("paramsHash" in f["msg"] for f in findings), findings)

    def test_changing_params_invalidates_evidence(self):
        boot(self.root)
        fill_params(self.root, 10)
        add_unit(self.root)
        add_evidence(self.root)
        self.assertEqual(fails(checks.check_evidence(self.root, cfgo(self.root))), [])
        fill_params(self.root, 20)
        findings = fails(checks.check_evidence(self.root, cfgo(self.root)))
        self.assertTrue(any("paramsHash" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------- 契约

    def test_contract_doc_drift_is_blocked(self):
        boot(self.root)
        doc = self.root / "docs" / "contracts" / "algo.md"
        text = doc.read_text(encoding="utf-8").replace("| inputId | string | 是 |", "| ghost | string | 是 |")
        doc.write_text(text, encoding="utf-8")
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

    # ------------------------------------------------------------- 文档

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

    # ------------------------------------------------------------- 索引

    def test_missing_keyword_header_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root, body="def sort(tasks):\n    return sorted(tasks)\n")
        r = run_py(self.root, "code-index.py", self.root)
        self.assertEqual(r.returncode, 0)
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("缺关键词头" in f["msg"] for f in findings), findings)

    def test_stale_index_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        entry = add_unit(self.root)
        future = os.path.getmtime(entry) + 600
        os.utime(entry, (future, future))
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("旧" in f["msg"] for f in findings), findings)

    def test_missing_index_json_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        (self.root / "docs" / "code-index.json").unlink()
        findings = fails(checks.check_index(self.root, cfgo(self.root)))
        self.assertTrue(any("缺少代码索引" in f["msg"] for f in findings), findings)

    def test_low_comment_ratio_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        body = HEADER + "".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(40))
        add_unit(self.root, body=body)
        cfg = cfgo(self.root)
        cfg["index"]["minCommentRatio"] = 0.2
        findings = fails(checks.check_index(self.root, cfg))
        self.assertTrue(any("注释率" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------- 范围

    def test_scope_blocks_file_outside_in_scope(self):
        boot(self.root, git=True)
        commit_all(self.root)
        (self.root / ".agent" / "current-task.json").write_text(json.dumps({
            "task": "只改算法", "inScope": ["apps/algo/src/**"], "outOfScope": ["apps/backend/**"],
        }), encoding="utf-8")
        (self.root / "stray.txt").write_text("x", encoding="utf-8")
        findings = fails(checks.check_scope(self.root, cfgo(self.root)))
        self.assertTrue(any("不在 inScope" in f["msg"] for f in findings), findings)

    def test_scope_allows_declared_file(self):
        boot(self.root, git=True)
        commit_all(self.root)
        (self.root / ".agent" / "current-task.json").write_text(json.dumps({
            "task": "改算法", "inScope": ["apps/algo/src/**"],
        }), encoding="utf-8")
        (self.root / "apps" / "algo" / "src" / "new.py").write_text(HEADER, encoding="utf-8")
        self.assertEqual(fails(checks.check_scope(self.root, cfgo(self.root))), [])

    def test_scope_blocks_protected_path(self):
        boot(self.root, git=True)
        fill_params(self.root)
        commit_all(self.root)
        (self.root / ".agent" / "current-task.json").write_text(json.dumps({
            "task": "改算法", "inScope": ["params/**"],
        }), encoding="utf-8")
        fill_params(self.root, 33)
        findings = fails(checks.check_scope(self.root, cfgo(self.root)))
        self.assertTrue(any("受保护" in f["msg"] for f in findings), findings)

    def test_scope_exempts_generated_artifacts(self):
        boot(self.root, git=True)
        commit_all(self.root)
        (self.root / ".agent" / "current-task.json").write_text(json.dumps({
            "task": "改算法", "inScope": ["apps/algo/src/**"],
        }), encoding="utf-8")
        (self.root / "apps" / "algo" / "src" / "new.py").write_text(HEADER, encoding="utf-8")
        (self.root / "docs" / "code-index.json").write_text("{}", encoding="utf-8")
        (self.root / "tests" / "evidence" / "x.json").write_text("{}", encoding="utf-8")
        (self.root / "reports" / "gate").mkdir(parents=True, exist_ok=True)
        (self.root / "reports" / "gate" / "r.json").write_text("{}", encoding="utf-8")
        self.assertEqual(fails(checks.check_scope(self.root, cfgo(self.root))), [])

    def test_scope_requires_task_when_configured(self):
        boot(self.root, git=True)
        commit_all(self.root)
        cfg = cfgo(self.root)
        cfg["policy"]["requireTask"] = True
        findings = fails(checks.check_scope(self.root, cfg))
        self.assertTrue(any("未声明任务范围" in f["msg"] for f in findings), findings)

    # ------------------------------------------------------------- 其它

    def test_cli_exit_codes_and_report(self):
        boot(self.root)
        cli = self.root / "scripts" / "gate.py"
        r = subprocess.run([sys.executable, str(cli), "all", str(self.root), "--record"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 1)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root)
        r = subprocess.run([sys.executable, str(cli), "all", str(self.root), "--record"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        reports = list((self.root / "reports" / "gate").glob("*.json"))
        self.assertGreaterEqual(len(reports), 2)
        payload = json.loads(reports[-1].read_text(encoding="utf-8"))
        for key in ("gate", "tier", "passed", "failed", "findings", "paramsHash"):
            self.assertIn(key, payload)

    def test_tier_s_needs_no_docs(self):
        boot(self.root, tier="S", parts="tool")
        fill_params(self.root)
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src" / "run.py").write_text(HEADER + "def run():\n    return 1\n", encoding="utf-8")
        r = run_py(self.root, "code-index.py", self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cfg = cfgo(self.root)
        self.assertEqual(fails(checks.check_params(self.root, cfg)), [])

    def test_tier_l_requires_flow_doc(self):
        boot(self.root, tier="L", parts="algo,backend")
        self.assertTrue((self.root / "docs" / "flows" / "deploy.md").is_file())
        (self.root / "docs" / "flows" / "deploy.md").unlink()
        self.assertTrue(fails(checks.check_flows(self.root, cfgo(self.root))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
