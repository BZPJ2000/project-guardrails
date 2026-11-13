---
name: project-guardrails
description: "多部件项目的防作假治理规程：开工先问清部件边界，一个部件一篇≤120行短文档并按定位只加载命中那篇；源文件必须带「用途/关键词/输入/输出/文档」头注释并自动生成关键词→文件:行 的代码索引；用 current-task.json 锁定改动范围、受保护路径只读；参数台账强制人工填写、接口契约与文档自动比对、测试证据落盘并绑定 paramsHash 与代码版本。Use when starting a multi-part project (前端/后端/算法/服务端/数据), or when 改这里坏那里、AI 直接改数据库假装完成、AI 乱填数值参数、改了参数却没重算、接口文档与代码对不上、没证据就说完成、代码找不到在哪、需要目录与文档规范、担心 AI 编造结果. Covers 项目隔离、目录规范、短文档分层、关键词定位、注释规范、范围锁定、契约校验、参数人工填、证据门禁."
---

# Project Guardrails

管的是「谁有权改什么、改完拿什么证明、代码在哪一行」，不是「怎么写代码」。

## 七条铁律

1. **先问后建**：部件清单、职责边界、通信方式、数值参数，四样没确认完，不建目录、不写业务代码。
2. **一个部件一篇文档，≤120 行**：超过就拆；入口只给索引，按 module-map 只加载命中的那一篇。
3. **派生字段不可直改**：由计算产生的字段只能重跑产生它的单元；直接写数据库或写死结果视为造假。
4. **数值只能人填**：`params/params.json` 由人填写，AI 只读；缺参数留 `__TBD__` 并阻断。
5. **没有证据 = 没做完**：证据要落盘、绑 `paramsHash` 和代码版本；参数一改旧证据全失效。
6. **每个源文件带关键词头**：五行头 + 自动生成的 `docs/code-index.md`，让"排序在哪"三次跳转能定位到行。
7. **改动必须落在 inScope 内**：`.agent/current-task.json` 声明范围，越界即失败；受保护路径只读。

## 分档

| 档 | 何时用 | 必做 | 可省 |
|---|---|---|---|
| S | 单脚本、小工具 | 目录 + params + 测试 + 证据 | 契约、分件文档、索引、范围锁定 |
| M | 单端应用 | S + 分件短文档 + 契约 + 关键词索引 | 流程文档、范围强制 |
| L | 多端 / 多人 / 上线 | M + 流程文档 + 范围锁定 + 严格证据 | — |

## 工作流

1. **定档**：问"几个部件、要不要上线"。多端、多人、上线占一条就是 L。
2. **初始化**：`python scripts/bootstrap.py --root . --tier M --parts algo,backend --git`。
3. **问清四件事**：部件边界、通信方式、人填参数、上线环境（模板见 `bootstrap-session.md`）。
4. **人填参数**：`params.example.json` → `params.json`，AI 不代填。
5. **写契约再写代码**：每个部件一份 `contracts/<part>.json`。
6. **基线提交**：`git add -A && git commit -m "chore: 初始化骨架"`。没提交就没有范围基线。
7. **声明范围**：写 `.agent/current-task.json`（`inScope` / `outOfScope`）。
8. **按单元实现**：文件开头写五行头；入口薄、逻辑纯、IO 隔离。
9. **重建索引**：`python scripts/code-index.py .`。
10. **跑门禁**：`python scripts/gate.py all . --record`，报告落 `reports/gate/`。
11. **汇报**：只报 `changed / verified / evidence / risk`。

## 路由

| 要决定的事 | 读这份 |
|---|---|
| 开新项目，先问什么 | `references/bootstrap-session.md` |
| 目录怎么放、文件怎么命名 | `references/layout.md` |
| 文档写几份、多长、怎么只读一篇 | `references/docs-system.md` |
| **代码在哪、关键词怎么打、索引怎么用** | `references/navigation.md` |
| **注释写到什么程度** | `references/annotations.md` |
| **这次能改哪些文件** | `references/scope-lock.md` |
| 接口/字段/错误码、文档如何跟代码一致 | `references/contracts.md` |
| 怀疑 AI 在作假 | `references/anti-fake.md` |
| 参数谁填、缺了怎么拦 | `references/params.md` |
| 测试怎么写、证据怎么算合格 | `references/testing-evidence.md` |
| 部署/测试流程怎么沉淀 | `references/flows.md` |
| 改了这里怕坏那里 | `references/change-impact.md` |
| 开工前先查什么、能否借用现成 skill | `references/discovery.md` |

只加载当前决策需要的那一份。

## 门禁

```bash
python scripts/gate.py all . --record     # 按档位全跑，报告存 reports/gate/
python scripts/gate.py index .            # 关键词头 + 索引新鲜度
python scripts/gate.py scope .            # 改动是否越界 / 碰了受保护路径
python scripts/gate.py evidence .         # 证据条数/耗时/新旧/paramsHash
python scripts/gate.py docs|contracts|params|flows .
```

## 失败即停

- 部件边界或通信方式未确认
- `params.json` 还有 `__TBD__`
- 契约字段与契约文档对不上
- 单元没有证据、证据比源码旧、或 `paramsHash` 不匹配
- 用例条数不足、含失败、或超出耗时预算
- 源文件缺五行头、注释率低于 3%、索引比源码旧
- 改动越出 `inScope`，或碰了受保护路径
- 部件文档超过 120 行

任何一条命中：停在原地，把失败项交回给人，不要"尽力而为"。
