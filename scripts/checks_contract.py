"""Contract, evidence and flow gates."""
from __future__ import annotations

import time
from pathlib import Path

from common import (
    NUMERIC,
    TYPES,
    count_lines,
    doc_field_names,
    doc_version,
    finding,
    git_head,
    params_hash,
    paths_of,
    read_json,
    read_text,
    unit_ids,
)


def _check_contract_body(c, units):
    errs = []
    for key in ("contract", "version", "fields", "errorCodes"):
        if key not in c:
            errs.append(f"缺少 {key}")
    fields = c.get("fields")
    if not isinstance(fields, list):
        errs.append("fields 必须是数组")
        fields = []
    names = []
    for i, fld in enumerate(fields):
        if not isinstance(fld, dict):
            errs.append(f"fields[{i}] 不是对象")
            continue
        name = fld.get("name")
        if not name:
            errs.append(f"fields[{i}] 缺 name")
            continue
        if name in names:
            errs.append(f"字段重复: {name}")
        names.append(name)
        t = fld.get("type")
        if t not in TYPES:
            errs.append(f"{name}: type 非法 {t!r}")
        if not isinstance(fld.get("required"), bool):
            errs.append(f"{name}: required 必须是布尔")
        if t in NUMERIC:
            r = fld.get("range")
            if not (isinstance(r, list) and len(r) == 2 and r[0] <= r[1]):
                errs.append(f"{name}: 缺少合法 range")
            if not fld.get("unit"):
                errs.append(f"{name}: 缺少 unit")
        if fld.get("derived") is True:
            pb = fld.get("producedBy")
            if not pb:
                errs.append(f"{name}: derived 字段必须写 producedBy")
            elif pb not in units:
                errs.append(f"{name}: producedBy 未在 tests/units.json 登记 ({pb})")
        else:
            w = fld.get("writer")
            if w not in ("human", "system"):
                errs.append(f"{name}: writer 必须是 human 或 system")
            elif w == "human":
                src = str(fld.get("source") or "")
                if not src.startswith("params."):
                    errs.append(f"{name}: human 字段 source 必须是 params. 开头")
    codes = c.get("errorCodes")
    if not isinstance(codes, list) or not codes:
        errs.append("errorCodes 不能为空")
    return errs, names


def check_contracts(root, cfg):
    root = Path(root)
    out = []
    paths = paths_of(cfg)
    cdir = root / paths.get("contracts", "contracts")
    ddir = root / paths.get("contractsDoc", "docs/contracts")
    units = unit_ids(root, cfg)

    if not cdir.is_dir():
        return [finding("contracts", "contracts/", False, "缺少 contracts/ 目录")]
    files = sorted(cdir.glob("*.json"))
    if not files:
        return [finding("contracts", "contracts/", False, "没有任何契约文件")]

    for f in files:
        rel = str(f.relative_to(root))
        try:
            c = read_json(f)
        except Exception as e:  # noqa: BLE001
            out.append(finding("contracts", rel, False, f"解析失败: {e}"))
            continue
        if not isinstance(c, dict):
            out.append(finding("contracts", rel, False, "顶层必须是对象"))
            continue
        errs, names = _check_contract_body(c, units)
        out.append(finding("contracts", rel, not errs,
                           "; ".join(errs) if errs else f"{len(names)} 个字段 OK"))

        name = c.get("contract")
        if not isinstance(name, str) or not name:
            continue
        dd = ddir / f"{name}.md"
        drel = str(dd.relative_to(root))
        if not dd.is_file():
            out.append(finding("contracts", drel, False, "缺少契约文档"))
            continue
        text = read_text(dd)
        got = doc_field_names(text)
        if got is None:
            out.append(finding("contracts", drel, False, "缺少「## 字段」表格"))
        else:
            a, b = set(got), set(names)
            if a == b:
                out.append(finding("contracts", drel, True, f"{len(b)} 个字段与契约一致"))
            else:
                out.append(finding("contracts", drel, False,
                                   f"字段不一致 文档缺:{sorted(b - a)} 文档多:{sorted(a - b)}"))
        dv, cv = doc_version(text), str(c.get("version"))
        out.append(finding("contracts", drel, dv == cv, f"版本 文档={dv} 契约={cv}"))
    return out


def check_evidence(root, cfg):
    root = Path(root)
    paths = paths_of(cfg)
    ecfg = cfg.get("evidence") or {}
    min_cases = int(ecfg.get("minCases", 5))
    max_age = float(ecfg.get("maxAgeHours", 720))
    up = root / paths.get("units", "tests/units.json")
    ed = root / paths.get("evidence", "tests/evidence")

    if not up.is_file():
        return [finding("evidence", "tests/units.json", False, "缺少单元清单")]
    try:
        units = read_json(up).get("units") or []
    except Exception as e:  # noqa: BLE001
        return [finding("evidence", "tests/units.json", False, f"解析失败: {e}")]
    if not units:
        return [finding("evidence", "tests/units.json", False, "没有任何登记单元")]

    out = []
    now = time.time()
    for u in units:
        if not isinstance(u, dict) or not u.get("id"):
            out.append(finding("evidence", "tests/units.json", False, "存在缺少 id 的单元"))
            continue
        uid = u["id"]
        ev = ed / (uid.replace("/", "__") + ".json")
        if not ev.is_file():
            out.append(finding("evidence", uid, False, "没有证据文件"))
            continue
        try:
            e = read_json(ev)
        except Exception as ex:  # noqa: BLE001
            out.append(finding("evidence", uid, False, f"证据解析失败: {ex}"))
            continue

        errs = []
        if e.get("exitCode") != 0:
            errs.append(f"exitCode={e.get('exitCode')}")
        c = e.get("cases") or {}
        total, passed, failed = c.get("total", 0), c.get("passed", 0), c.get("failed", 0)
        if failed:
            errs.append(f"failed={failed}")
        need = max(min_cases, int(u.get("minCases", 0)))
        if total < need:
            errs.append(f"用例 {total} < 下限 {need}")
        if passed != total:
            errs.append(f"passed {passed} != total {total}")
        if c.get("boundary", 0) < 1:
            errs.append("缺少边界用例")
        if c.get("invalidInput", 0) < 1:
            errs.append("缺少非法输入用例")
        d = e.get("durationMs")
        b = u.get("budgetMs")
        if d is None:
            errs.append("缺少 durationMs")
        elif b is not None and d > b:
            errs.append(f"耗时 {d}ms > 预算 {b}ms")
        if not e.get("command"):
            errs.append("缺少 command")
        if not isinstance(e.get("env"), dict) or not e["env"]:
            errs.append("缺少 env")

        if ecfg.get("requireProvenance", False):
            cv = e.get("codeVersion")
            if not cv:
                errs.append("缺少 codeVersion（证据必须绑定代码版本）")
            ph = e.get("paramsHash")
            cur = params_hash(root, cfg)
            if not ph:
                errs.append("缺少 paramsHash")
            elif cur and ph != cur:
                errs.append("paramsHash 与当前 params.json 不一致（参数变了，需重跑）")
            if ecfg.get("requireCurrentCommit") and cv:
                head = git_head(root)
                if head and str(cv) != head:
                    errs.append(f"codeVersion {cv} != 当前提交 {head}（需重跑）")

        newest = 0.0
        for s in [u.get("entry")] + list(u.get("source") or []):
            if not s:
                continue
            p = root / s
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
        ev_m = ev.stat().st_mtime
        if ecfg.get("requireNewerThanSource", True) and newest and ev_m <= newest:
            errs.append("证据比源码旧（需重跑）")
        if max_age > 0 and (now - ev_m) / 3600.0 > max_age:
            errs.append(f"证据超过 {max_age:g}h")

        out.append(finding("evidence", uid, not errs,
                           "; ".join(errs) if errs else f"{total} 条全过 {d}ms"))
    return out


def check_flows(root, cfg):
    root = Path(root)
    max_doc = int(cfg.get("maxDocLines", 120))
    d = root / paths_of(cfg).get("flows", "docs/flows")
    if not d.is_dir():
        return [finding("flows", "docs/flows/", False, "L 档要求 docs/flows/")]
    files = sorted(d.glob("*.md"))
    if not files:
        return [finding("flows", "docs/flows/", False, "没有任何流程文档")]
    out = []
    for f in files:
        rel = str(f.relative_to(root))
        text = read_text(f)
        n = count_lines(f)
        errs = []
        if "## 最后验证" not in text:
            errs.append("缺少「## 最后验证」")
        if n > max_doc:
            errs.append(f"{n} 行，上限 {max_doc}")
        out.append(finding("flows", rel, not errs, "; ".join(errs) if errs else "OK"))
    return out
