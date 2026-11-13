---
name: project-guardrails
description: "多部件项目的防作假治理规程：开工先问清部件边界，一个部件一篇≤120行短文档并按定位只加载命中那篇；建立唯一真相源与派生字段禁改、参数台账强制人工填写、接口契约与文档自动比对、测试证据落盘并按条数/耗时/新旧判真、部署与测试流程固化为可更新流程文件。Use when starting a multi-part project (前端/后端/算法/服务端/数据), or when 改这里坏那里、AI 直接改数据库假装完成、AI 乱填数值参数、接口文档与代码对不上、没测试证据就说完成、需要目录与文档规范、要把部署/测试流程沉淀成可复用流程、担心 AI 编造结果. Covers 项目隔离、目录规范、短文档分层、契约校验、参数人工填、证据门禁、变更影响."
---

# Project Guardrails

管的是「谁有权改什么、改完拿什么证明」，不是「怎么写代码」。项目被拆成互相隔离的部件，每个部件一份短文档、一份契约、一份证据；AI 缺信息时停下来问人，而不是编一个数。

## 五条铁律

1. **先问后建**：部件清单、职责边界、通信方式、数值参数，四样没确认完，不建目录、不写业务代码。
2. **一个部件一篇文档，≤120 行**：超过就拆，一篇只讲一件事；入口只给索引，AI 按 module-map 只加载命中的那一篇。
3. **派生字段不可直改**：由计算产生的字段只能通过重跑产生它的单元来变；直接写数据库或写死结果一律视为造假。
4. **数值只能人填**：`params/params.json` 由人填写，AI 只读；缺参数就留 `__TBD__` 并阻断，不给"合理默认值"。
5. **没有证据 = 没做完**：证据必须落盘（条数、通过率、耗时、环境、命令），证据比源码旧即视为未验证。

## 分档

| 档 | 何时用 | 必做 | 可省 |
|---|---|---|---|
| S | 单脚本、小工具 | 目录 + params + 1 组测试 + 证据 | 契约、分件文档 |
| M | 单端应用（一个后端或一个算法） | S + 分件短文档 + 契约 + module-map | 流程文档 |
| L | 多端 / 多人 / 要上线 | M + 流程文档 + 变更影响清单 + 严格证据 | — |

档位写进 `guardrails.json` 的 `tier`，门禁按档位决定查哪些。判据：多端、多人、上线，占一条就是 L。

## 工作流

1. **定档**：问"这个项目几个部件、要不要上线"，按上表定 S/M/L。
2. **初始化**：`python scripts/bootstrap.py --root . --tier M --parts algo,backend --git`。建 git、目录骨架、`guardrails.json`、`AGENTS.md`、`docs/module-map.md`、空 part 文档、params 骨架、契约骨架。
3. **问清四件事**：部件清单与边界、部件间通信、需要人填的参数、上线环境。问话模板在 `references/bootstrap-session.md`。
4. **人填参数**：把 `params/params.example.json` 交给项目负责人填成 `params/params.json`，AI 不代填。
5. **写契约再写代码**：每个部件一份 `contracts/<part>.json`，标明哪些字段人填、哪些派生、派生由哪个单元产生。
6. **按单元实现**：一个单元 = 一个可独立运行、可独立验证的文件；入口薄、逻辑纯、IO 隔离。
7. **跑门禁**：`python scripts/gate.py all <root>`。任一闸门失败就停，不许"先合进去再说"。
8. **汇报**：只报 `changed / verified / evidence 路径 / 未验证风险` 四项。

## 路由

| 要决定的事 | 读这份 |
|---|---|
| 开新项目，不知道该先问什么 | `references/bootstrap-session.md` |
| 目录怎么放、文件怎么命名、数据怎么存 | `references/layout.md` |
| 文档写几份、多长、怎么让 AI 只读一篇 | `references/docs-system.md` |
| 接口/字段/错误码怎么定、文档怎么跟代码一致 | `references/contracts.md` |
| 怀疑 AI 在作假、怎么设计防线 | `references/anti-fake.md` |
| 参数谁来填、缺了怎么拦 | `references/params.md` |
| 测试怎么写、证据怎么算合格 | `references/testing-evidence.md` |
| 部署/测试流程怎么沉淀成可更新的流程 | `references/flows.md` |
| 改了这里怕坏那里 | `references/change-impact.md` |
| 开工前该先查什么、能不能借用现成 skill | `references/discovery.md` |

只加载当前决策需要的那一份。

## 失败即停

下列情形停在原地、把问题交回给人，不要"尽力而为"：

- 部件边界或通信方式未确认
- `params.json` 里还有 `__TBD__`
- 契约字段与契约文档字段对不上
- 单元没有证据，或证据比源码旧
- 用例条数不足、含失败、或超出耗时预算
- 部件文档超过 120 行（先拆再继续）

脚本互相独立，可单独跑：`gate.py docs|contracts|params|evidence|all`，加 `--json` 出机器可读报告。
