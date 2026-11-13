# project-guardrails

给 AI 编码助手用的一套**项目护栏**：管的是「谁有权改什么、改完拿什么证明」，不是「怎么写代码」。

目标很具体——拦住四件反复发生的事：

| 症状 | 护栏做什么 |
|---|---|
| 改这里坏那里 | 部件隔离 + 每部件「变更影响」表 + 契约变更触发全量回归 |
| AI 直接改数据库字段假装完成 | 契约字段标 `derived`，只能重跑产生它的单元；没登记/没证据就失败 |
| AI 自己编数值（尺寸、阈值、权重） | `params/params.json` 只有人能写，缺了留 `__TBD__` 并阻断 |
| 说"测试通过"但拿不出证据 | 证据必须落盘，按条数、通过率、耗时、比源码新 判定 |

## 快速开始

```bash
# 1. 放到你的技能目录（DSH / Claude Code 等会用 ~/.agents/skills/）
git clone https://github.com/BZPJ2000/project-guardrails.git ~/.agents/skills/project-guardrails

# 2. 初始化一个项目（S=小脚本 / M=单端应用 / L=多端上线）
python project-guardrails/scripts/bootstrap.py --root . --tier M --parts algo,backend --git

# 3. 改完东西跑门禁
python scripts/gate.py all .
```

`bootstrap` 生成骨架后**不会**让你直接写业务代码：先答四组问题（部件边界、部件间通信、需要人填的参数、上线环境），把 `params.json` 填掉，门禁全绿，才开始写。

## 门禁

```bash
python scripts/gate.py all .            # 按档位跑全部
python scripts/gate.py params .         # 只查参数台账
python scripts/gate.py docs .           # 只查文档行数/小节/索引
python scripts/gate.py contracts .      # 只查契约与契约文档字段/版本是否一致
python scripts/gate.py evidence .       # 只查测试证据
```

任一闸门失败退出码为 1，并打印失败原因。门禁脚本会被复制进项目 `scripts/`，可随项目打包迁移，不依赖本仓库。

证据合格线（逐条检查，不满足即失败）：

- `exitCode == 0`
- 用例数 ≥ 5（含边界 ≥1、非法输入 ≥1）
- 通过率 100%
- 耗时 ≤ 该单元的 `budgetMs`
- 证据文件必须比它覆盖的源码新
- 必须带 `command` 和 `env`（否则不可复现）

## 分档

| 档 | 用在哪 | 必做 | 可省 |
|---|---|---|---|
| S | 单脚本、小工具 | 目录 + params + 一组测试 + 证据 | 契约、分件文档 |
| M | 单端应用（一个后端或一个算法） | S + 分件短文档 + 契约 + module-map | 流程文档 |
| L | 多端 / 多人 / 要上线 | M + 流程文档 + 变更影响清单 + 严格证据 | — |

小工具不该被流程压死，大项目不该只靠自觉——所以分档。

## 结构

```
project-guardrails/
├─ SKILL.md                  入口：五条铁律 + 分档 + 工作流 + 路由表
├─ references/               10 篇短文档，每篇一个决策，按需加载
│  ├─ bootstrap-session.md   开新项目先问哪四组问题
│  ├─ layout.md              目录/命名/数据按日分 + 四种语言落地要点
│  ├─ docs-system.md         ≤120 行、固定小节、module-map 路由
│  ├─ contracts.md           契约格式 + 文档自动比对
│  ├─ anti-fake.md           SSOT 表、派生字段禁改、三层校验、六个作假信号
│  ├─ params.md              参数台账，人填 AI 只读
│  ├─ testing-evidence.md    证据格式与硬阈值
│  ├─ flows.md               部署/测试/发版固化成可更新流程
│  ├─ change-impact.md       改 X 必查 Y / 必重跑 Z
│  └─ discovery.md           先查 → 再借 → 才造
├─ scripts/                  common / checks / checks_contract / gate / bootstrap
├─ assets/templates/         12 个脚手架模板
├─ tests/test_gate.py        16 项自测，全部通过
└─ agents/openai.yaml        技能元信息
```

## 设计取舍

- **文档宁短勿长**：一篇超过 120 行就必须拆。不是因为写不动，是因为 AI 读到中段就散了，人也一样。
- **一个部件一篇**：定位到哪坏，就只打开那一篇，不把整套文档塞进上下文。
- **契约是唯一字段真相**：文档是它的人读版，代码是它的实现，三者不一致以契约为准。
- **未知即停**：缺信息只有两个合法动作——问人，或在参数台账留 `__TBD__` 并阻断。没有"先填个合理默认值"。

## 依赖

Python 3.9+，标准库，无第三方包。

## 自测

```bash
python tests/test_gate.py    # 16 tests, OK
```

## License

MIT
