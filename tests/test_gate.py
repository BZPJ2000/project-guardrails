#!/usr/bin/env python3
"""Self-tests for project-guardrails gates.

Every test builds a throwaway project, so the gates are proven to block,
not assumed to. Run:

    python tests/test_gate.py
"""
from __future__ import annotations

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
import gate  # noqa: E402


def boot(root, tier="M", parts="algo"):
    cmd = [sys.executable, str(SKILL / "scripts" / "bootstrap.py"),
           "--root", str(root), "--tier", tier, "--parts", parts]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def fails(findings):
    return [f for f in findings if not f["ok"]]


def fill_params(root, value=10):
    (root / "params" / "params.json").write_text(
        json.dumps({"sampleSize": value}), encoding="utf-8")


def add_unit(root, unit_id="algo/sortTask", prepared=True):
    entry = root / "apps" / "algo" / "src" / "sortTask.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("def sort(tasks):\n    return sorted(tasks)\n", encoding="utf-8")
    data = {"units": [{"id": unit_id, "entry": "apps/algo/src/sortTask.py",
                       "source": [], "budgetMs": 200, "minCases": 5}]}
    (root / "tests" / "units.json").write_text(json.dumps(data), encoding="utf-8")
    return entry


def add_evidence(root, unit_id="algo/sortTask", **over):
    ev = {"unit": unit_id, "runId": "t-1", "startedAt": "2026-11-13T23:00:00+08:00",
          "durationMs": 42, "command": "python tests/runUnit.py " + unit_id,
          "env": {"language": "python", "version": "3.12", "os": "test"},
          "exitCode": 0,
          "cases": {"total": 7, "passed": 7, "failed": 0, "boundary": 2, "invalidInput": 2}}
    ev.update(over)
    p = root / "tests" / "evidence" / (unit_id.replace("/", "__") + ".json")
    p.write_text(json.dumps(ev), encoding="utf-8")
    return p


class T(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

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
        self.assertTrue(fails(checks.check_params(self.root, checks.load_config(self.root)[0])))

    def test_out_of_range_param_is_blocked(self):
        boot(self.root)
        fill_params(self.root, 99999)
        self.assertTrue(fails(checks.check_params(self.root, checks.load_config(self.root)[0])))

    def test_unknown_param_key_is_blocked(self):
        boot(self.root)
        (self.root / "params" / "params.json").write_text(
            json.dumps({"sampleSize": 10, "ghost": 1}), encoding="utf-8")
        self.assertTrue(fails(checks.check_params(self.root, checks.load_config(self.root)[0])))

    def test_full_green_project_passes(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root)
        findings = checks.run_gate(self.root, "all")
        self.assertEqual(fails(findings), [], [f for f in fails(findings)])

    def test_stale_evidence_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        entry = add_unit(self.root)
        add_evidence(self.root)
        future = os.path.getmtime(entry) + 600
        os.utime(entry, (future, future))
        findings = fails(checks.check_evidence(self.root, checks.load_config(self.root)[0]))
        self.assertTrue(any("比源码旧" in f["msg"] for f in findings), findings)

    def test_thin_evidence_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        ev = add_evidence(self.root)
        data = json.loads(ev.read_text(encoding="utf-8"))
        data["cases"] = {"total": 2, "passed": 2, "failed": 0, "boundary": 0, "invalidInput": 0}
        ev.write_text(json.dumps(data), encoding="utf-8")
        findings = fails(checks.check_evidence(self.root, checks.load_config(self.root)[0]))
        msgs = " ".join(f["msg"] for f in findings)
        self.assertIn("下限", msgs)
        self.assertIn("边界", msgs)
        self.assertIn("非法输入", msgs)

    def test_slow_unit_is_blocked(self):
        boot(self.root)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root, durationMs=9999)
        findings = fails(checks.check_evidence(self.root, checks.load_config(self.root)[0]))
        self.assertTrue(any("预算" in f["msg"] for f in findings), findings)

    def test_contract_doc_drift_is_blocked(self):
        boot(self.root)
        doc = self.root / "docs" / "contracts" / "algo.md"
        text = doc.read_text(encoding="utf-8").replace("| inputId | string | 是 |", "| ghost | string | 是 |")
        doc.write_text(text, encoding="utf-8")
        cfg = checks.load_config(self.root)[0]
        findings = fails(checks.check_contracts(self.root, cfg))
        self.assertTrue(any("字段不一致" in f["msg"] for f in findings), findings)

    def test_version_drift_is_blocked(self):
        boot(self.root)
        c = self.root / "contracts" / "algo.json"
        data = json.loads(c.read_text(encoding="utf-8"))
        data["version"] = "2.0.0"
        c.write_text(json.dumps(data), encoding="utf-8")
        cfg = checks.load_config(self.root)[0]
        findings = fails(checks.check_contracts(self.root, cfg))
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
        cfg = checks.load_config(self.root)[0]
        findings = fails(checks.check_contracts(self.root, cfg))
        self.assertTrue(any("producedBy" in f["msg"] for f in findings), findings)

    def test_overlong_doc_is_blocked(self):
        boot(self.root)
        p = self.root / "docs" / "parts" / "algo.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n填充\n" * 130, encoding="utf-8")
        cfg = checks.load_config(self.root)[0]
        findings = fails(checks.check_docs(self.root, cfg))
        self.assertTrue(any("上限" in f["msg"] for f in findings), findings)

    def test_missing_section_is_blocked(self):
        boot(self.root)
        p = self.root / "docs" / "parts" / "algo.md"
        p.write_text(p.read_text(encoding="utf-8").replace("## 变更影响", "## 其它"), encoding="utf-8")
        cfg = checks.load_config(self.root)[0]
        findings = fails(checks.check_docs(self.root, cfg))
        self.assertTrue(any("缺少小节" in f["msg"] for f in findings), findings)

    def test_cli_exit_codes(self):
        boot(self.root)
        cli = self.root / "scripts" / "gate.py"
        r = subprocess.run([sys.executable, str(cli), "all", str(self.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 1)
        fill_params(self.root)
        add_unit(self.root)
        add_evidence(self.root)
        r = subprocess.run([sys.executable, str(cli), "all", str(self.root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_tier_s_needs_no_docs(self):
        boot(self.root, tier="S", parts="tool")
        fill_params(self.root)
        add_unit(self.root, "tool/run")
        add_evidence(self.root, "tool/run")
        cfg = checks.load_config(self.root)[0]
        self.assertEqual(fails(checks.check_params(self.root, cfg)), [])
        self.assertEqual(fails(checks.check_evidence(self.root, cfg)), [])

    def test_tier_l_requires_flow_doc(self):
        boot(self.root, tier="L", parts="algo,backend")
        self.assertTrue((self.root / "docs" / "flows" / "deploy.md").is_file())
        cfg = checks.load_config(self.root)[0]
        (self.root / "docs" / "flows" / "deploy.md").unlink()
        self.assertTrue(fails(checks.check_flows(self.root, cfg)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
