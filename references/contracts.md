# 契约与接口文档

契约是**唯一的字段真相**。文档是契约的人读版，代码是契约的实现。三者不一致时，以契约为准，改另外两个。

## 契约文件

位置 `contracts/<part>.json`，格式：

```json
{
  "contract": "algo-tasks",
  "version": "1.0.0",
  "owner": "algo",
  "fields": [
    { "name": "taskId", "type": "string", "required": true, "writer": "human",
      "source": "params.tasks[].id" },
    { "name": "priority", "type": "int", "required": true, "range": [1, 5],
      "unit": "级", "writer": "human", "source": "params.tasks[].priority" },
    { "name": "scheduleSeq", "type": "int", "required": true, "derived": true,
      "producedBy": "algo/sortTaskPriority" }
  ],
  "errorCodes": ["E_EMPTY_INPUT", "E_PRIORITY_OUT_OF_RANGE", "E_CONTRACT_VIOLATION"]
}
```

字段属性含义：

| 属性 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 扁平字段名，与文档表格第一列一致 |
| `type` | 是 | `string` `int` `float` `bool` `array` `object` |
| `required` | 是 | 缺失即报错，不给默认值 |
| `range` | 数值型必填 | `[min, max]`，超范围**拒绝**，不截断 |
| `unit` | 数值型必填 | 单位，防止量纲错 |
| `writer` | 是 | `human`（来自 params）或 `system`（由单元产生） |
| `source` | human 字段必填 | 必须是 `params.` 开头 |
| `derived` | 派生字段必填 | `true` 表示只能重算，不能直改 |
| `producedBy` | derived 必填 | 产生它的单元 id，必须存在于 `tests/units.json` |

## 三条硬约束

1. **白名单**：契约里没有的字段一律拒绝。`additionalProperties: false` 是默认行为，不做"宽容解析"。
2. **派生字段不可直改**：`derived: true` 的字段只能由 `producedBy` 指定的单元重新计算。任何"直接 UPDATE 数据库 / 直接改 JSON 里的值"的实现都算造假。
3. **错误必须显性**：每种拒绝都要有错误码，且出现在 `errorCodes` 里。禁止静默跳过、禁止返回空对象假装成功。

## 文档同步（自动比对）

`docs/contracts/<contract>.md` 必须包含：

```markdown
## 版本
1.0.0

## 字段
| 字段 | 类型 | 必填 | 范围/单位 | 写入方 | 说明 |
|---|---|---|---|---|---|
| taskId | string | 是 | — | 人 | 任务唯一标识 |
| scheduleSeq | int | 是 | — | 算法（重算） | 排序结果，禁止直改 |
```

门禁 `gate.py contracts` 检查：

- 文档「## 字段」表第一列的字段集合 == 契约 `fields[].name` 集合
- 文档「## 版本」里的字符串 == 契约 `version`
- 每个 `derived` 字段的 `producedBy` 在 units 清单里存在
- 每个 `writer: human` 字段的 `source` 以 `params.` 开头

## 版本与兼容

- 加字段（可选）：minor。删/改字段语义、改范围：major。
- major 变更期间双写：旧字段保留一个版本，契约里标 `deprecated: true`。
- 契约文件与文档必须同一次提交更新，否则门禁失败。

## 实现侧要求

- 读取输入后**先校验再计算**：结构 → 范围 → 语义不变量。
- 输出**先自检再返回**：字段齐全、范围和单位正确、不变量成立。
- 任一校验失败 → 返回错误码，附失败字段名与期望范围。不要返回部分结果。
