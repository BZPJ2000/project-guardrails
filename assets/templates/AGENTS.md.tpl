# {{PROJECT_NAME}}

档位：{{TIER}} ｜ 初始化：{{DATE}}

## 铁律

1. 动手前先读 `docs/module-map.md`，只加载命中的那一篇部件文档。
2. 派生字段只能重跑产生它的单元，不许直接改值。
3. 数值参数只来自 `params/params.json`；缺了报 `E_PARAM_MISSING`，不许给默认值。
4. 测试证据必须落盘；证据比源码旧即视为未验证。
5. 汇报固定四项：changed / verified / evidence / risk。

## 部件

{{PART_LIST}}

## 门禁

```bash
python scripts/gate.py all .
```

任一闸门失败就停下，不许绕过，不许"先合进去再说"。

## 当前阶段

初始化未完成前不写业务代码。完成判据：`params.json` 无 `__TBD__`、四组问题已答、门禁全绿。
