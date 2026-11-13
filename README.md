# project-guardrails

给 AI 编码助手用的一套**项目护栏**：管的是「谁有权改什么、改完拿什么证明、代码在哪一行」，不是「怎么写代码」。

v2 起多了三件事：**关键词定位**（一句话 → 文件:行）、**改动范围锁定**（越界即失败）、**证据指纹**（参数一改，旧证据全废）。

## 拦什么

| 症状 | 护栏做什么 |
|---|---|
| 改这里坏那里 | 部件隔离 + 变更影响表 + 契约变更触发全量回归 |
| AI 直接改数据库字段假装完成 | 派生字段只能重跑产生它的单元；没登记/没证据就失败 |
| AI 自己编数值（尺寸、阈值、权重） | `params.json` 只有人能写，缺了留 `__TBD__` 并阻断 |
| 说"测试通过"但拿不出证据 | 证据落盘，绑 `paramsHash` 与代码版本，参数一改全部失效 |
| 改了参数却没重算 | 证据里的 `paramsHash` 对不上，门禁直接拦 |
| 代码找不到在哪 | 每个源文件带五行关键词头 + 自动索引，三次跳转定位到行 |
| 顺手把无关文件也改了 | `current-task.json` 锁定 inScope，越界即失败 |

## 快速开始

```bash
# 1. 装到技能目录
git clone https://github.com/BZPJ2000/project-guardrails.git ~/.agents/skills/project-guardrails

# 2. 初始化项目（S=小脚本 / M=单端应用 / L=多端上线）
python ~/.agents/skills/project-guardrails/scripts/bootstrap.py --root . --tier M --parts algo,backend --git

# 3. 做基线提交（范围检查要靠它）
git add -A && git commit -m "chore: 初始化骨架"

# 4. 人填参数 → 写 current-task.json → 写代码 → 建索引 → 跑门禁
python scripts/code-index.py .
python scripts/gate.py all . --record
```

## 源文件头（门禁强制）

```python
"""
用途: 按优先级与依赖排序任务
关键词: 排序, 优先级, 拓扑, scheduleSeq, sortTaskPriority
输入: contracts/algo.json
输出: scheduleSeq (int[])，从 1 连续
文档: docs/parts/algo.md
"""
```

`code-index.py` 会把这些关键词和符号（函数/类名）编成一张表：

```markdown
| 关键词 / 符号 | 文件:行 | 职责 |
|---|---|---|
| `排序` | `apps/algo/src/sortTask.py:1` | 按优先级与依赖排序任务 |
| `sort_tasks` | `apps/algo/src/sortTask.py:42` | 按优先级与依赖排序任务 |
```

查代码是三层跳：`module-map`（哪个部件）→ `code-index`（哪个文件哪行）→ 文件头（不变量确认）。

## 门禁

```bash
python scripts/gate.py all . --record    # 按档位全跑，报告存 reports/gate/
python scripts/gate.py index .           # 关键词头 + 索引新鲜度 + 注释率
python scripts/gate.py scope .           # 改动是否越界 / 碰了受保护路径
python scripts/gate.py evidence .        # 条数/耗时/新旧/paramsHash
python scripts/gate.py params .          # 参数台账
python scripts/gate.py docs .            # 文档行数/小节/索引
python scripts/gate.py contracts .       # 契约与契约文档字段/版本一致
```

任一闸门失败退出码 1。门禁脚本会复制进项目 `scripts/`，可随项目打包迁移。

**证据合格线**（逐条检查）：

- `exitCode == 0`，通过率 100%
- 用例 ≥5（含边界 ≥1、非法输入 ≥1）
- 耗时 ≤ 单元 `budgetMs`
- 证据比源码新，且年龄 ≤720h
- `paramsHash` 等于当前 `params.json` 的 sha256
- 带 `command` 与 `env`

## 范围锁定

```json
// .agent/current-task.json
{
  "task": "把优先级权重改成从 params 读取",
  "inScope": ["apps/algo/src/**", "params/params.schema.json"],
  "outOfScope": ["apps/backend/**"]
}
```

门禁拿 `git status` 对比：越出 `inScope`、命中 `outOfScope`、碰了受保护路径（`params.json` / `evidence` / `data`），全部失败。想扩范围必须改声明并说明理由——自己给自己发许可不算。

## 分档

| 档 | 用在哪 | 必做 |
|---|---|---|
| S | 单脚本、小工具 | 目录 + params + 测试 + 证据 |
| M | 单端应用 | S + 短文档 + 契约 + 关键词索引 |
| L | 多端 / 多人 / 上线 | M + 流程文档 + 范围锁定 |

## 结构

```
project-guardrails/
├─ SKILL.md                  七条铁律 + 分档 + 工作流 + 路由
├─ references/               13 篇短文档，每篇一个决策
│  ├─ navigation.md          关键词定位体系（头注释 + 索引）
│  ├─ annotations.md         注释规范（文件头/函数/为什么）
│  ├─ scope-lock.md          任务范围锁定与受保护路径
│  ├─ anti-fake.md           SSOT、派生字段禁改、六个作假信号
│  ├─ contracts.md / params.md / testing-evidence.md
│  ├─ docs-system.md / layout.md / change-impact.md
│  └─ flows.md / bootstrap-session.md / discovery.md
├─ scripts/
│  ├─ bootstrap.py           脚手架
│  ├─ code-index.py          关键词 → 文件:行 索引
│  ├─ gate.py                门禁 CLI（8 个闸门）
│  ├─ checks*.py / common.py 各闸门实现
│  └─ skill-index.py         全局技能索引
├─ assets/templates/         13 个模板
├─ tests/test_gate.py        26 项自测，全部通过
└─ CHANGELOG.md
```

## 依赖

Python 3.9+，标准库，无第三方包。范围检查需要 git。

## 自测

```bash
python tests/test_gate.py    # 26 tests, OK
```

## License

MIT
