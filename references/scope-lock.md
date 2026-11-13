# 任务范围锁定：改之前先声明改哪里

"顺手改一下"是连带崩坏的主要来源。所以每次动工之前，先写一份范围声明，门禁按它检查实际改动。

## 声明文件

`.agent/current-task.json`：

```json
{
  "task": "把优先级权重改成从 params 读取",
  "inScope": ["apps/algo/src/**", "params/params.schema.json"],
  "outOfScope": ["apps/backend/**"],
  "startedAt": "2026-11-14T00:10:00+08:00"
}
```

- `inScope` 必填，空等于没有边界，门禁直接失败。
- `outOfScope` 用来挡"看着不像但确实不能碰"的地方。
- 通配符支持 `*`（单层）、`**`（跨目录）、`?`。

## 门禁怎么判

`gate.py scope` 取 `git status --porcelain` 的全部改动（含未跟踪文件），逐个比对，顺序是：

1. 命中 `policy.exempt` → 通过（工作流自己生成的东西）
2. 命中 `policy.protected` → 失败（受保护路径只读）
3. 命中 `outOfScope` → 失败
4. 不在 `inScope` → 失败
5. 都不命中 → 通过

### 豁免：工作流产物不算越界

代码索引、测试证据、门禁报告、范围声明本身，都是工具跑出来的，不该逼你写进 `inScope`：

```json
"exempt": ["docs/code-index.md", "docs/code-index.json",
           "tests/evidence/**", "reports/**", ".agent/**", "data/**"]
```

豁免只针对**生成物**。`tests/units.json` 是手写清单，不在豁免里——加单元就要在 `inScope` 里声明；`params/params.json` 更不在，它是人写的。

### 受保护：人写的、AI 不能碰

```json
"protected": ["params/params.json", "**/.env", "**/*.key", "**/*.pem"]
```

证据文件不再靠路径保护，靠指纹（`paramsHash` + 条数 + 耗时）自证——改数字会让它跟当前参数对不上。

## 前置条件：先做基线提交

scope 是拿"当前改动"对比"上次提交"。所以 bootstrap 之后**先提交一次完整骨架**，再开始改东西：

```bash
git add -A && git commit -m "chore: 初始化骨架"
```

没有提交时，所有文件都算"新增"，范围检查没有意义。

## 越界了怎么办

**不许**悄悄把 `inScope` 改大。正确顺序：

1. 停下，把越界文件列出来
2. 问人：这个文件要不要一起改？
3. 要 → 由人确认后扩 `inScope`，并在 `.agent/changes/` 里记一句为什么扩
4. 不要 → 回退那个文件

自己扩范围等于自己给自己发许可，这条防线就废了。

## 可选：强制模式

`guardrails.json` 里 `policy.requireTask = true` 之后，没有 `current-task.json` 时门禁直接失败。适合多人协作或跑自动任务时打开。

## 和变更影响清单的分工

- `current-task.json`：这次**能碰哪些文件**（物理边界）
- 部件文档的「变更影响」：碰了之后**必须检查什么**（逻辑边界）

两个都要过。物理上没越界、逻辑上漏了检查，一样会坏。
