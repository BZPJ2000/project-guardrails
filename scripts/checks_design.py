"""Design gate: no design note, no large-scale coding (制度一)."""
from __future__ import annotations

from pathlib import Path

from common import count_lines, finding, read_text, section

DEFAULT_FILES = ["docs/design/modules.md", "docs/design/flows.md",
                 "docs/design/data.md", "docs/design/api.md"]


def check_design(root, cfg):
    root = Path(root)
    dcfg = section(cfg, "design")
    tier = str(cfg.get("tier", "M"))
    files = dcfg.get("files") or DEFAULT_FILES
    required = str(dcfg.get("required", "L"))

    exists = [f for f in files if (root / f).is_file()]
    if not exists and tier != required:
        return [finding("design", "docs/design/", True,
                        f"档位 {tier} 不要求设计说明书（{required} 档才强制）")]

    max_doc = int(cfg.get("maxDocLines", 120))
    out = []
    for f in files:
        p = root / f
        rel = str(f)
        if not p.is_file():
            out.append(finding("design", rel, False, "缺少设计说明书"))
            continue
        n = count_lines(p)
        text = read_text(p)
        placeholder = len(text.strip()) < 40
        errs = []
        if placeholder:
            errs.append("内容过短，疑似占位")
        if n > max_doc:
            errs.append(f"{n} 行，上限 {max_doc}")
        out.append(finding("design", rel, not errs,
                           "; ".join(errs) if errs else f"{n} 行"))
    return out
