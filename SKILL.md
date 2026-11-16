---
name: project-guardrails
description: "多部件项目的防作假治理规程：一次任务只做一件事，用 task.py 声明范围、汇总改动、绑定证据、一个任务一个提交，回退只退这一个；控制单次改动的文件数与函数数并禁止整文件重写；开工先问清部件边界，一个部件一篇≤120行短文档并按定位只加载命中那篇；源文件五行头注释 + 关键词→文件:行 索引；参数台账强制人工填写；契约与文档自动比对；证据绑 paramsHash 与代码版本。Use when starting a multi-part project (前端/后端/算法/服务端/数据), or when 改这里坏那里、AI 整块接手改代码、回退版本退太多、AI 直接改数据库假装完成、AI 乱填数值参数、改了参数却没重算、接口文档与代码对不上、没证据就说完成、代码找不到在哪、需要设计说明书与回滚方案. Covers 任务粒度、改动范围、提交颗粒度、短文档分层、关键词定位、契约校验、参数人工填、证据门禁、发布回滚."
---

# Project Guardrails

管三件事：**谁有权改什么、改完拿什么证明、出问题退到哪。**

## 八条铁律

1. **先问后建**：部件清单、职责边界、通信方式、数值参数，四样没确认完，不建目录、不写业务代码。
2. **一次只做一件事**：`task.py start` 声明目标与 `inScope`，越界即失败；一个任务一个 commit。
3. **改动有上限**：单任务文件 ≤15、符号 ≤20，禁止整文件重写；超了就拆任务。
4. **一个部件一篇文档，≤120 行**：超过就拆；按 module-map 只加载命中那一篇。
5. **派生字段不可直改**：只能重跑产生它的单元；直接写库视为造假。
6. **数值只能人填**：`params.json` 由人写，AI 只读；缺了留 `__TBD__` 阻断。
7. **没有证据 = 没做完**：证据绑 `paramsHash` 与代码版本；参数一改旧证据全失效。
8. **发版先有回滚**：没有 `docs/flows/rollback.md` 和版本号，不允许打 tag。

## 分档

| 档 | 何时用 | 说明 |
|---|---|---|
| S | 单脚本、小工具 | 闸门全跑，但契约/分部件文档/设计说明书按档位 SKIP |
| M | 单端应用 | 分部件文档 + 契约 + 关键词索引 + 任务制 |
| L | 多端 / 多人 / 上线 | M + 流程文档 + 设计说明书四件套 + 范围锁定强制 |

**闸门默认全开**：`gate.py all` 跑九个闸门；档位只决定某条要求适不适用，不适用时显式 SKIP，不静默跳过。

## 工作流

1. **定档**：问"几个部件、要不要上线"。
2. **初始化**：`bootstrap.py --root . --tier M --parts algo,backend --git`。
3. **问清四件事**：部件边界、通信、人填参数、上线环境（模板见 `bootstrap-session.md`）。
4. **人填参数** → 补契约 → **基线提交**（`git add -A && git commit`）。
5. **开任务**：`task.py start "<这一件事>" --files "<inScope>"`。
6. **按单元实现**：文件写五行头；入口薄、逻辑纯、IO 隔离。
7. **重建索引** → **跑门禁**（`--record` 落报告）。
8. **写变更说明** `.agent/tasks/<id>.md` 四节。
9. **结束**：`task.py finish`（门禁 + 汇总 + 一次提交）。
10. **发版**：`release.py --version X.Y.Z --apply`，先过回滚方案检查。

## 路由

| 要决定的事 | 读这份 |
|---|---|
| 开新项目，先问什么 | `references/bootstrap-session.md` |
| **一次任务怎么开、怎么收、怎么退** | `references/task-loop.md` |
| **这次能改哪些文件** | `references/scope-lock.md` |
| **代码在哪、关键词怎么打** | `references/navigation.md` |
| **注释写到什么程度** | `references/annotations.md` |
| 目录怎么放、文件怎么命名 | `references/layout.md` |
| 文档写几份、多长 | `references/docs-system.md` |
| 接口/字段/错误码、文档一致性 | `references/contracts.md` |
| 怀疑 AI 在作假 | `references/anti-fake.md` |
| 参数谁填、缺了怎么拦 | `references/params.md` |
| 测试怎么写、证据怎么合格 | `references/testing-evidence.md` |
| 部署/回滚/发版流程 | `references/flows.md` |
| 改了这里怕坏那里 | `references/change-impact.md` |
| 开工前能否借用现成 skill | `references/discovery.md` |

只加载当前决策需要的那一份。

## 门禁

```bash
python scripts/gate.py all . --record   # 九个闸门 + 报告
python scripts/gate.py task .           # 任务范围/改动上限/变更说明
python scripts/gate.py design .         # 设计说明书四件套（L 档）
python scripts/gate.py scope .          # 越界与受保护路径
python scripts/gate.py index .          # 五行头 + 索引新鲜度
python scripts/gate.py evidence .       # 条数/耗时/新旧/paramsHash
python scripts/gate.py docs|contracts|params|flows .
```

## 失败即停

- 部件边界或通信方式未确认，`params.json` 还有 `__TBD__`
- 没有 `current-task.json` 就动代码，改动越出 `inScope`，碰了受保护路径
- 单任务文件 >15 / 符号 >20 / 整文件重写
- 变更说明缺任一节，任务日志缺失
- 契约与契约文档不一致，文档超过 120 行
- 证据缺失、比源码旧、`paramsHash` 不匹配
- 缺设计说明书（L 档）或缺回滚方案就要发版

任何一条命中：停在原地，把失败项交回给人，不要"尽力而为"。
