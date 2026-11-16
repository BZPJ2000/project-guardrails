# {{PROJECT_NAME}}

档位：{{TIER}} ｜ 初始化：{{DATE}}

## 铁律

1. 动手前先读 `docs/module-map.md` 与 `docs/code-index.md`，只加载命中那一篇。
2. **一次只做一件事**：先 `task.py start` 声明 inScope；越界即失败。
3. 每个源文件开头必须有「用途/关键词/输入/输出/文档」五行头。
4. 派生字段只能重跑产生它的单元，不许直接改值。
5. 数值参数只来自 `params/params.json`，缺了报错，不许给默认值。
6. 证据必须落盘并绑 `paramsHash`；参数一改，旧证据全部失效。
7. 结束前写 `.agent/tasks/<id>.md` 四节（改了什么/为什么改/影响哪些模块/如何验证），
   然后 `task.py finish` —— 一个任务一个 commit，回退就 revert 这一个。

## 部件

{{PART_LIST}}

## 门禁

```bash
python scripts/task.py start "<这一件事>" --files "<inScope>"
python scripts/code-index.py .
python scripts/gate.py all . --record
python scripts/task.py finish
python scripts/release.py --version X.Y.Z --apply   # 要发版时
```

任一闸门失败就停下，不许绕过，不许"先合进去再说"。

## 当前阶段

初始化未完成前不写业务代码。完成判据：`params.json` 无 `__TBD__`、四组问题已答、
基线提交已做、门禁全绿。
