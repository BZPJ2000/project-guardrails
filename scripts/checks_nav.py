"""Navigation gate: every source file carries a keyword header, and the
generated code index is fresh and complete."""
from __future__ import annotations

from pathlib import Path

from common import (
    HEADER_KEYS,
    comment_ratio,
    finding,
    parse_header,
    read_json,
    read_text,
    rel_posix,
    section,
    source_files,
)


def check_index(root, cfg):
    root = Path(root)
    icfg = section(cfg, "index")
    files = source_files(root, cfg)
    if not files:
        return [finding("index", "sources", True, "尚无源文件（初始化阶段），跳过")]

    out = []
    min_ratio = float(icfg.get("minCommentRatio", 0.03))
    min_lines = int(icfg.get("minCommentRatioLines", 50))
    worst = None

    for rel in files:
        text = read_text(root / rel)
        header = parse_header(text)
        missing = [k for k in HEADER_KEYS if not header.get(k)]
        ratio, n = comment_ratio(text)
        errs = []
        if missing:
            errs.append("缺关键词头: " + ", ".join(missing))
        if n >= min_lines and ratio < min_ratio:
            errs.append(f"注释率 {ratio:.1%} < {min_ratio:.0%}")
            if worst is None or ratio < worst[1]:
                worst = (rel, ratio)
        out.append(finding("index", rel, not errs,
                           "; ".join(errs) if errs else f"头齐全，注释率 {ratio:.0%}（{n} 行）"))

    jpath = root / icfg.get("json", "docs/code-index.json")
    if not jpath.is_file():
        out.append(finding("index", "docs/code-index.json", False,
                           "缺少代码索引，先跑 python scripts/code-index.py ."))
        return out
    try:
        idx = read_json(jpath)
    except Exception as e:  # noqa: BLE001
        out.append(finding("index", "docs/code-index.json", False, f"解析失败: {e}"))
        return out

    indexed = {f.get("path") for f in idx.get("files", []) if isinstance(f, dict)}
    missing = [f for f in files if f not in indexed]
    out.append(finding("index", "docs/code-index.json", not missing,
                       "未收录: " + ", ".join(missing[:5]) if missing else f"收录 {len(indexed)} 个源文件"))

    newest_src = max((root / f).stat().st_mtime for f in files)
    src_of_index = (jpath.stat().st_mtime, idx.get("sourceMtimeMax", 0))
    if max(src_of_index) < newest_src:
        out.append(finding("index", "docs/code-index.json", False,
                           "索引比源码旧，跑 python scripts/code-index.py . 重建"))
    else:
        out.append(finding("index", "docs/code-index.json", True, "索引是最新的"))
    return out
