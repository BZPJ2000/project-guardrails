# 测试与证据：合格线是数字

"跑通了"不是证据，"3 类共 7 条用例全过、耗时 42ms、证据在某个路径"才是。证据是唯一让"完成"可核查的东西。

## 单元清单

`tests/units.json` 登记每个单元，门禁只认这里登记过的单元：

```json
{
  "units": [
    {
      "id": "algo/sortTaskPriority",
      "entry": "apps/algo/src/sortTaskPriority.py",
      "source": ["apps/algo/src/priorityRules.py"],
      "budgetMs": 200,
      "minCases": 5
    }
  ]
}
```

- `source` 列出该单元依赖的所有源文件，用于判断证据是否过期。
- `budgetMs` 是单次运行的耗时上限，超了就是失败。

## 用例必须覆盖三类

| 类型 | 数量下限 | 内容 |
|---|---|---|
| 正常 | ≥2 | 典型输入，校验主路径 |
| 边界 | ≥1 | 最小/最大规模、恰好等于范围端点 |
| 非法输入 | ≥1 | 缺字段、类型错、超范围，**必须被拒绝**且有错误码 |

非法输入用例的期望是"返回错误"，不是"返回空值"。若实现吞掉错误返回空结果，该用例判失败。

## 证据文件

每个单元一份，落在 `tests/evidence/<unitId 把 / 换成 __>.json`：

```json
{
  "unit": "algo/sortTaskPriority",
  "runId": "20261113T2310-a1b2",
  "startedAt": "2026-11-13T23:10:04+08:00",
  "durationMs": 42,
  "command": "python tests/runUnit.py algo/sortTaskPriority",
  "env": { "language": "python", "version": "3.12.4", "os": "Windows-11" },
  "exitCode": 0,
  "cases": { "total": 7, "passed": 7, "failed": 0, "boundary": 2, "invalidInput": 2 }
}
```

## 合格线（门禁逐条检查）

| 检查 | 阈值 | 不满足的后果 |
|---|---|---|
| `exitCode` | 必须为 0 | 失败 |
| `cases.failed` | 必须为 0 | 失败 |
| `cases.total` | ≥ `max(minCases, 5)` | 失败 |
| `cases.boundary` | ≥ 1 | 失败 |
| `cases.invalidInput` | ≥ 1 | 失败 |
| `durationMs` | ≤ `budgetMs` | 失败 |
| 证据 mtime | 必须晚于该单元所有源文件的 mtime | 失败（视为未验证） |
| 证据年龄 | ≤ `maxAgeHours`（默认 720） | 失败 |
| `env` + `command` | 必须存在 | 失败（无法复现的证据不算证据） |

任一条不过，该单元状态为"未验证"，任何汇报里不许出现"完成"。

## 写测试的顺序

1. 先写用例（输入 / 期望 / 期望错误码），此时必然红。
2. 写实现，跑到全绿。
3. 跑证据生成脚本，落盘。
4. 跑 `gate.py evidence`。

## 采样与性能

- 计时的单元一次运行至少采样 3 次，`durationMs` 取中位数，并在证据里附 `samples`。
- 只报单次数值（尤其"最快一次"）视为无效证据。

## 不许做的事

- 为了让测试变绿改断言、放宽范围 —— 改的是契约，不是测试。
- 用 mock 替代真实产物却宣称链路可用；mock 只在单元级使用，集成级必须真跑。
- 手动改证据文件里的数字。证据由脚本生成，人只读。
