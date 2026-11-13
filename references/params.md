# 参数台账：数值只能由人填

数值参数是业务决定，不是实现细节。AI 填一个"看起来合理"的车长或阈值，等于替人做了产品决策，且这个错误会静默传播到所有结果里。

## 三份文件

| 文件 | 谁写 | 作用 |
|---|---|---|
| `params/params.schema.json` | AI 起草、人确认 | 声明有哪些参数、类型、范围、单位、必填 |
| `params/params.example.json` | AI 生成 | 全部填 `__TBD__` 的模板，供人对照 |
| `params/params.json` | **只有人** | 真实取值，AI 只读 |

## schema 格式

```json
{
  "params": {
    "taskCount":  { "type": "int",   "range": [1, 1000], "unit": "个", "required": true,
                    "question": "一次最多处理多少个任务？" },
    "timeoutMs":  { "type": "int",   "range": [100, 600000], "unit": "ms", "required": true,
                    "question": "单个任务允许的最长处理时间？" },
    "weightAge":  { "type": "float", "range": [0, 10], "unit": "权重", "required": true,
                    "question": "任务年龄在优先级里的权重，0 表示不考虑？" }
  }
}
```

`question` 字段是给人看的提问原话，必填 —— 让人一眼知道该填什么，而不是猜。

## 哨兵值

`__TBD__` 表示"人还没填"。门禁遇到它直接失败，并打印**还差哪几个参数、每个参数对应的问题原话**。

其他禁止的占位：`null`、`""`、`0`（除非 0 是合法业务值并写进 range）、`TODO`、`待定`。

## AI 的行为边界

- 只能读 `params.json`，不能写。
- 可以在 `params.example.json` 里生成骨架和问题清单。
- 人填完之前，可以写不依赖该参数的代码；一旦运行路径依赖它，必须报 `E_PARAM_MISSING`，不许给默认值。
- 需要新增参数时：先加 schema + example，然后**停下来问人**，不要顺手填上再继续。

## 校验规则（门禁执行）

1. `params.json` 存在且是合法 JSON。
2. 所有 `required: true` 的键都存在，且不等于 `__TBD__`。
3. 每个值的类型与 schema 一致。
4. 数值在 `range` 内。**超范围拒绝，不截断、不夹紧。**
5. `params.json` 里不得出现 schema 未声明的键（白名单）。

## 变更留痕

参数改动追加到 `params/CHANGELOG.md`：

```markdown
| 日期 | 参数 | 旧值 | 新值 | 改动原因 | 谁改的 |
|---|---|---|---|---|---|
| 2026-11-13 | timeoutMs | 5000 | 8000 | 大数据量下超时 | 张三 |
```

参数变了，之前跑出的结果就不再可复现 —— 所以每次运行的产物目录里要放一份 `params.snapshot.json`。

## 常见错误

- **让 AI"先随便填一个跑通"**：这条错误会进入产物，且没人记得它存在。禁止。
- **把参数写死在代码里**：等于绕过台账。发现一个就要挪进 schema。
- **参数有默认值**：默认值也是决策。要么在 schema 里写清并让人确认，要么就不要默认值。
