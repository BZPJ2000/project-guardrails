# {{PROJECT_NAME}}

档位：{{TIER}} ｜ 初始化：{{DATE}}

## 铁律

1. 动手前先读 `docs/module-map.md`，再读 `docs/code-index.md` 定位文件，只加载命中那一篇。
2. 每个源文件开头必须有「用途/关键词/输入/输出/文档」五行头注释，缺了门禁不过。
3. 派生字段只能重跑产生它的单元，不许直接改值。
4. 数值参数只来自 `params/params.json`；缺了报 `E_PARAM_MISSING`，不许给默认值。
5. 测试证据必须落盘并绑定 `paramsHash`；参数一改，旧证据全部失效。
6. 改动必须落在 `.agent/current-task.json` 的 `inScope` 内，越界即失败。
7. 汇报固定四项：changed / verified / evidence / risk。

## 部件

{{PART_LIST}}

## 门禁

```bash
python scripts/gate.py all . --record    # 全跑并落盘报告
python scripts/code-index.py .           # 改完源码重建索引
```

任一闸门失败就停下，不许绕过，不许"先合进去再说"。

## 当前阶段

初始化未完成前不写业务代码。完成判据：`params.json` 无 `__TBD__`、四组问题已答、
基线提交已做、门禁全绿。
