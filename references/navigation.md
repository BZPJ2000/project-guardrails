# 关键词定位：从一句话到一行代码

目标：AI 想知道「排序逻辑在哪」，三次跳转内落到具体文件和行，不需要通读仓库。

## 三层跳转

```text
1. docs/module-map.md       部件级   哪个部件负责这件事
2. docs/code-index.md       文件级   关键词 → 文件:行
3. 文件头注释                职责级   用途 / 不变量 / 输入输出
```

第 1 层用「职责」列匹配问题里的名词；第 2 层按关键词表拿路径；第 3 层读文件头确认是不是这里。找不到就停下问人，不要靠猜打开一串文件。

## 文件头（门禁强制）

每个源文件的前 40 行内必须有这五行，键名不能改：

```python
"""
用途: 按优先级与依赖排序任务，产出连续序号
关键词: 排序, 优先级, 拓扑, scheduleSeq, sortTaskPriority
输入: contracts/algo.json
输出: scheduleSeq (int[]), 从 1 连续
文档: docs/parts/algo.md
"""
```

其他语言用同样的键，换注释符号即可：

```java
// 用途: ...
// 关键词: ...
```

```rust
// 用途: ...
```

```cpp
/* 用途: ...
   关键词: ... */
```

**关键词怎么写**：3 个以上，中文业务词和英文符号名都要有。别人会用「优先级怎么算」来搜，也会用 `scheduleSeq` 来搜，两种都要命中。

## 生成与更新索引

```bash
python scripts/code-index.py .
```

产物两份：

- `docs/code-index.md` —— 人读：`| 关键词/符号 | 文件:行 | 职责 |`
- `docs/code-index.json` —— 机器读：含每个文件的注释率、符号表、源文件最大 mtime

索引不许手改。源码一改就重建，门禁会检查索引是否比源码旧。

## 临时 grep（索引没覆盖时）

```powershell
# 按文件头关键词找
Select-String -Path apps\*\src\*.py -Pattern '关键词.*排序'
# 按符号找
Select-String -Path apps\*\src\*.* -Pattern 'def sortTaskPriority|fn sort_task'
```

先 grep 文件头，再 grep 符号名。不要用 `Select-String -Pattern '.'` 之类的方式扫全库。

## 门禁规则

`gate.py index` 检查四件事，任一不满足即失败：

1. 每个源文件都有五行头，且都不为空
2. `docs/code-index.json` 存在
3. 索引收录了全部源文件（新增文件没重建索引 → 失败）
4. 索引不比源码旧

## 为什么不用「大而全的架构文档」

那种文档一长就没人读，AI 也读不全。索引是按需查的：查什么、打开哪一行，都写在表里。
