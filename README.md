# project-guardrails

给 AI 编码助手用的一套**项目护栏**：管的是「谁有权改什么、改完拿什么证明、出问题退到哪一行」，不是「怎么写代码」。

v4 起多了三件事：**任务制**（一次一件事、一个任务一个提交、回退只退这一个）、**改动上限**（文件数/函数数/禁止整文件重写）、**交付门槛**（设计说明书 + 变更说明 + 回滚方案）。

## 拦什么

| 症状 | 护栏做什么 |
|---|---|
| AI 整块接手，一次改二十个文件 | `task.py` 声明范围；单任务 ≤15 文件 / ≤20 符号，整文件重写直接失败 |
| 改了前面忘后面 | 一次只做一个任务，变更说明四节不写不算完成 |
| 回退版本退太多 | 一个任务一个 commit，`task.py revert <id>` 只撤这一个 |
| 出问题不知道怎么查 | 每个源文件五行关键词头 + 关键词索引，三次跳转定位到行 |
| AI 直接改数据库假装完成 | 派生字段只能重跑产生它的单元；没登记/没证据就失败 |
| AI 自己编数值 | `params.json` 只有人能写，缺了留 `__TBD__` 并阻断 |
| 改了参数却没重算 | 证据绑 `paramsHash`，参数一改全部失效 |
| 没设计就开始大规模编码 | L 档要求 `docs/design/` 四件套，缺了连任务都开不了 |
| 没回滚方案就上线 | `release.py` 检查 rollback 文档与命令，缺了不许打 tag |

## 快速开始

```bash
# 1. 装到技能目录
git clone https://github.com/BZPJ2000/project-guardrails.git ~/.agents/skills/project-guardrails

# 2. 初始化（S=小脚本 / M=单端应用 / L=多端上线）
python ~/.agents/skills/project-guardrails/scripts/bootstrap.py --root . --tier M --parts algo,backend --git

# 3. 人填参数 → 基线提交
git add -A && git commit -m "chore: 初始化骨架"

# 4. 一个任务从头到尾
python scripts/task.py start "把优先级权重改成从 params 读" --files "apps/algo/src/**"
#   …改代码、补测试、重建索引…
python scripts/code-index.py .
python scripts/gate.py all . --record
#   …写 .agent/tasks/<id>.md 四节…
python scripts/task.py finish          # 门禁 + 汇总 + 一次提交
```

## 任务制

```bash
task.py start "<这一件事>" --files "<inScope>"
task.py status                 # 当前任务改了多少文件/多少符号
task.py finish                 # 全绿才提交，一次任务一个 commit
task.py revert <task-id>       # 只撤这一个任务
```

- 一个任务 = 一个 `current-task.json` + 一份 `.agent/tasks/<id>.md` + 一条日志 + **一个 commit**
- `finish` 的提交信息带 `task(<id>):`，`revert` 按它找提交
- 改动指纹精确到函数：Python 走 AST，Java/Rust/C++/Go/TS 按符号行近似（不承诺代码块级）

**改动上限**（默认，可改 `guardrails.json`）：

| 项 | 默认 |
|---|---|
| 单任务文件数 | 15 |
| 单任务符号数 | 20 |
| 整文件重写 | 禁止（删除 ≥60% 或新旧内容行重合 <60%，且涉及 ≥3 个符号） |

## 变更说明（四节）

`.agent/tasks/<id>.md`：

```markdown
## 改了什么
## 为什么改
## 影响哪些模块
## 如何验证
```

缺任一节，`finish` 与 `gate task` 都不过。第四节要写命令与证据路径，不能写"已测试"。

## 门禁

```bash
python scripts/gate.py all . --record   # 九个闸门 + 报告落 reports/gate/
python scripts/gate.py task .           # 任务范围 / 改动上限 / 变更说明 / 日志
python scripts/gate.py design .         # 设计说明书四件套（L 档）
python scripts/gate.py scope .          # 越界与受保护路径
python scripts/gate.py index .          # 五行头 + 索引新鲜度 + 注释率
python scripts/gate.py evidence .       # 条数/耗时/新旧/paramsHash
python scripts/gate.py docs|contracts|params|flows .
```

闸门默认全开；档位只在闸门内部决定某条要求适不适用，不适用时给 **SKIP**（可见），不静默跳过。

## 发布

```bash
python scripts/release.py --version 1.2.0          # dry-run
python scripts/release.py --version 1.2.0 --apply  # 打 tag
```

发版前强制检查：工作区干净、`CHANGELOG` 有该版本、`docs/flows/rollback.md` 里有可执行回滚命令、门禁全绿。

## 分档

| 档 | 用在哪 | 差异 |
|---|---|---|
| S | 单脚本、小工具 | 契约/分部件文档/设计说明书 SKIP，任务制照旧 |
| M | 单端应用 | 全套文档 + 契约 + 索引 + 任务制 |
| L | 多端 / 多人 / 上线 | + 流程文档 + 设计说明书 + 回滚方案 |

## 结构

```
project-guardrails/
├─ SKILL.md                  八条铁律 + 分档 + 工作流 + 路由
├─ references/               14 篇短文档，每篇一个决策
│  ├─ task-loop.md           任务循环与回退颗粒度
│  ├─ scope-lock.md          改动范围与受保护路径
│  ├─ navigation.md          关键词定位体系
│  ├─ annotations.md         注释规范
│  ├─ anti-fake.md / contracts.md / params.md / testing-evidence.md
│  ├─ docs-system.md / layout.md / change-impact.md
│  └─ flows.md / bootstrap-session.md / discovery.md
├─ scripts/                  15 个
│  ├─ task.py                任务：start / status / finish / revert
│  ├─ gate.py                门禁 CLI（9 个闸门）
│  ├─ release.py             版本 + 回滚前置校验
│  ├─ code-index.py          关键词 → 文件:行
│  ├─ impact.py              改动影响面
│  ├─ publish.py             推送预检
│  ├─ install-hooks.py       pre-commit
│  ├─ bootstrap.py           脚手架
│  └─ checks*.py / common.py / tasklib.py / skill-index.py
├─ assets/templates/         17 个模板（含设计说明书四件套、回滚流程）
├─ tests/test_gate.py        36 项自测，全部通过
├─ .github/workflows/gate.yml
└─ CHANGELOG.md
```

## 依赖

Python 3.9+，标准库，无第三方包。范围/任务/回退功能需要 git。

## 自测

```bash
python tests/test_gate.py    # 36 tests, OK
```

## License

MIT
