# Changelog

## v4.0 — 2026-11-16

**新增：任务制（问题「改前忘后 / 回退退太多」）**

- `scripts/task.py`：`start` 声明目标与 inScope，`status` 看改动面，`finish` 门禁+汇总+**一次提交**，`revert <id>` 只撤这一个任务
- 提交信息带 `task(<id>):`，回退按 id 找提交
- `.agent/tasks/<id>.json` 记录改了哪些文件/函数/增删行；`.log.jsonl` 记录任务时间线

**新增：改动上限（问题「AI 整块接管」）**

- 单任务文件 ≤15、符号 ≤20（可配）
- 整文件重写检测：删除 ≥60% **或** 新旧内容行重合 <60%，且涉及 ≥3 个符号
- 符号级指纹：Python 用 AST 精确，其他语言按符号行近似

**新增：交付门槛（三个制度）**

- `design` 闸门：L 档要求 `docs/design/` 四件套（模块/流程/数据/接口）
- `task` 闸门：变更说明四节（改了什么/为什么改/影响哪些模块/如何验证）缺一节即失败
- `release.py`：版本号 + CHANGELOG 段落 + **回滚方案必须先存在** + 门禁全绿，才允许打 tag

**闸门默认全开**

- `gate.py all` 跑九个闸门；档位只在闸门内部决定"适不适用"，不适用时给 SKIP 而不是静默跳过
- 新增 `task`、`design` 两个闸门

**修复**

- `finish` 前先清掉 `current-task.json` 再提交，避免回退时 modify/delete 冲突
- `current-task.json` 加入 `.gitignore`，临时状态不进版本库
- `Path.glob("dir/**")` 只返回目录，改为自行递归，源码索引不再漏文件
- 整文件重写判定从"删除行比例"改为"删除比例或行重合度"，避免 git diff 最大化匹配后重写被漏判

**测试**

- 自测 32 → 36 项，新增任务生命周期、回退、重写检测、设计门禁、发布门禁

## v3.0 — 2026-11-14

**新增：影响面分析**

- `scripts/impact.py`：拿当前 diff 算出必读文档、必查契约、必重跑单元，并标出未归属任何部件的改动

**新增：防绕过**

- `scripts/install-hooks.py`：把 params / contracts / index 装进 pre-commit（`--full` 可改为全量）
- 绕过必须显式 `git commit --no-verify`，不会"悄悄通过"

**新增：交付预检**

- `scripts/publish.py`：密钥（正则规则）、>50MB 文件、未提交改动、缺 `.gitignore` 全部拦下
- `--dry-run` 只审计不推送；审计失败时不上传任何内容
- `.publishignore` 处理误报

**工程**

- 门禁报告按秒级唯一命名，同一秒多次运行不再互相覆盖
- `.github/workflows/gate.yml`：CI 跑 32 项自测

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
