# Changelog

## v2.0 — 2026-11-14

**新增：关键词定位**

- 每个源文件必须带五行头注释（用途 / 关键词 / 输入 / 输出 / 文档），门禁按字面检查
- `scripts/code-index.py` 生成 `docs/code-index.md` + `.json`：关键词 → 文件:行
- 门禁 `index`：缺头、索引未收录新文件、索引比源码旧，全部失败
- 注释率下限（≥50 行文件 3%，可配）
- 新增 `references/navigation.md`、`references/annotations.md`

**新增：改动范围锁定**

- `.agent/current-task.json` 声明 `inScope` / `outOfScope`
- 门禁 `scope` 拿 `git status` 对比声明，越界即失败
- 受保护路径（`params/params.json`、`tests/evidence/**`、`data/**`）只读
- `policy.requireTask = true` 可强制每次改动都要先声明范围
- 新增 `references/scope-lock.md`

**证据链加强**

- 证据必须带 `paramsHash`（params.json 的 sha256），参数一改旧证据全部失效
- 证据必须带 `codeVersion`；可开启 `requireCurrentCommit` 强制等于当前提交
- `gate.py --record` 把每次门禁运行落盘到 `reports/gate/<时间>-<闸门>.json`

**门禁与分档**

- 新增闸门：`index`、`scope`；M 档含 `index`，L 档含 `index + scope`
- 模板新增 `current-task.json`；bootstrap 复制 7 个脚本进项目

**测试**

- 自测从 16 项增至 26 项，覆盖头注释、索引新鲜度、越界改动、受保护路径、证据指纹

## v1.0 — 2026-11-13

- 初始版本：部件隔离、≤120 行短文档、契约与文档比对、参数人工填、证据门禁、S/M/L 分档
