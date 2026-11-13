"""Docs, params and navigation gates, plus the gate registry.

Contract/evidence/flow checks live in checks_contract.py; navigation checks in
checks_nav.py; scope checks in checks_scope.py. All are re-exported here so
callers import one module.
"""
from __future__ import annotations

from pathlib import Path

from common import (
    NUMERIC,
    PLACEHOLDER,
    count_lines,
    finding,
    load_config,
    paths_of,
    read_json,
    read_text,
)
from checks_contract import check_contracts, check_evidence, check_flows  # noqa: F401
from checks_nav import check_index  # noqa: F401
from checks_scope import check_scope  # noqa: F401

PART_HEADINGS = ["## 用途", "## 责任边界", "## 变更影响", "## 最后更新"]


def check_docs(root, cfg):
    root = Path(root)
    out = []
    paths = paths_of(cfg)
    max_doc = int(cfg.get("maxDocLines", 120))
    max_agents = int(cfg.get("maxAgentsLines", 80))
    parts = cfg.get("parts") or []

    agents = root / "AGENTS.md"
    if not agents.is_file():
        out.append(finding("docs", "AGENTS.md", False, "缺少入口文件"))
    else:
        n = count_lines(agents)
        out.append(finding("docs", "AGENTS.md", n <= max_agents,
                           f"{n} 行，上限 {max_agents}"))

    docs = root / paths.get("docs", "docs")
    if not docs.is_dir():
        out.append(finding("docs", "docs/", False, "缺少 docs/ 目录"))
        return out

    for p in sorted(docs.rglob("*.md")):
        n = count_lines(p)
        out.append(finding("docs", str(p.relative_to(root)), n <= max_doc,
                           f"{n} 行，上限 {max_doc}"))

    parts_dir = root / paths.get("parts", "docs/parts")
    for part in parts:
        pp = parts_dir / f"{part}.md"
        rel = str(pp.relative_to(root))
        if not pp.is_file():
            out.append(finding("docs", rel, False, "缺少部件文档"))
            continue
        text = read_text(pp)
        missing = [h for h in PART_HEADINGS if h not in text]
        out.append(finding("docs", rel, not missing,
                           ("缺少小节: " + ", ".join(missing)) if missing else "小节齐全"))

    mm = docs / "module-map.md"
    if not mm.is_file():
        out.append(finding("docs", "docs/module-map.md", False, "缺少索引文件"))
    else:
        text = read_text(mm)
        missing = [p for p in parts if p not in text]
        out.append(finding("docs", "docs/module-map.md", not missing,
                           ("未登记部件: " + ", ".join(missing)) if missing else "部件已登记"))
    return out


def _type_ok(value, t):
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "bool":
        return isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t in ("array", "object"):
        return isinstance(value, list if t == "array" else dict)
    return True


def check_params(root, cfg):
    root = Path(root)
    paths = paths_of(cfg)
    sp = root / paths.get("paramsSchema", "params/params.schema.json")
    vp = root / paths.get("paramsValues", "params/params.json")
    if not sp.is_file():
        return [finding("params", "params/params.schema.json", False, "缺少 schema")]
    try:
        schema = read_json(sp)
    except Exception as e:  # noqa: BLE001
        return [finding("params", "params/params.schema.json", False, f"解析失败: {e}")]
    spec = schema.get("params")
    if not isinstance(spec, dict) or not spec:
        return [finding("params", "params/params.schema.json", False, "schema.params 为空")]

    if not vp.is_file():
        qs = [f"{k}: {v.get('question', '')}" for k, v in spec.items() if isinstance(v, dict)]
        return [finding("params", "params/params.json", False,
                        "缺少 params.json（需人工填写）: " + " / ".join(qs))]
    try:
        vals = read_json(vp)
    except Exception as e:  # noqa: BLE001
        return [finding("params", "params/params.json", False, f"解析失败: {e}")]
    if not isinstance(vals, dict):
        return [finding("params", "params/params.json", False, "顶层必须是对象")]

    out = []
    for k, s in spec.items():
        if not isinstance(s, dict):
            out.append(finding("params", f"params.{k}", False, "schema 条目必须是对象"))
            continue
        q = s.get("question", "")
        if k not in vals:
            out.append(finding("params", f"params.{k}", False, f"缺失，需人工填写：{q}"))
            continue
        v = vals[k]
        if v is None or v == "" or v == PLACEHOLDER:
            out.append(finding("params", f"params.{k}", False, f"仍为占位值 {v!r}"))
            continue
        t = s.get("type")
        if not _type_ok(v, t):
            out.append(finding("params", f"params.{k}", False,
                               f"类型应为 {t}，实际 {type(v).__name__}"))
            continue
        r = s.get("range")
        if t in NUMERIC and isinstance(r, list) and len(r) == 2:
            if not (r[0] <= v <= r[1]):
                out.append(finding("params", f"params.{k}", False,
                                   f"值 {v} 超出范围 [{r[0]}, {r[1]}]（单位 {s.get('unit')}）"))
                continue
        out.append(finding("params", f"params.{k}", True, f"= {v} {s.get('unit', '')}".strip()))

    for k in vals:
        if k not in spec:
            out.append(finding("params", f"params.{k}", False, "schema 未声明的参数（白名单外）"))
    return out


TIER_GATES = {
    "S": ["params", "evidence"],
    "M": ["docs", "contracts", "params", "evidence", "index"],
    "L": ["docs", "contracts", "params", "evidence", "index", "scope", "flows"],
}

RUNNERS = {
    "docs": check_docs,
    "contracts": check_contracts,
    "params": check_params,
    "evidence": check_evidence,
    "index": check_index,
    "scope": check_scope,
    "flows": check_flows,
}


def run_gate(root, gate):
    cfg, err = load_config(root)
    if err:
        return [err]
    if gate == "all":
        names = TIER_GATES.get(str(cfg.get("tier", "M")), TIER_GATES["M"])
        findings = []
        for n in names:
            findings.extend(RUNNERS[n](root, cfg))
        return findings
    if gate not in RUNNERS:
        return [finding("gate", gate, False, "未知闸门")]
    return RUNNERS[gate](root, cfg)
