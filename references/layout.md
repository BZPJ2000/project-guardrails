# 目录与命名

目标：别人（和人带的 AI）打开仓库，看一眼目录就知道每个东西在哪。

## 顶层骨架

```text
<project>/
├─ AGENTS.md              入口：铁律 + 索引 + 当前档位与阶段（≤80 行）
├─ guardrails.json        门禁配置（档位、部件清单、路径）
├─ docs/                  文档中心
│  ├─ module-map.md       唯一索引，AI 先读它
│  ├─ parts/<part>.md     每个部件一篇（≤120 行）
│  ├─ contracts/<name>.md 接口字段表
│  └─ flows/<flow>.md     部署/测试/发版流程
├─ apps/<part>/           每个部件一个顶层目录（S 档可省，直接放 src/）
│  └─ src/  tests/  scripts/
├─ contracts/<part>.json  机器可读契约
├─ params/                只有人写这里
├─ data/YYYY-MM-DD/<runId>/  运行产物
├─ tests/cases/  tests/evidence/  tests/units.json
├─ scripts/               start / verify-all / deploy / gate
└─ .agent/changes/        变更影响记录
```

## 命名规则

| 对象 | 规则 | 例 |
|---|---|---|
| 目录 | 全小写，单词或连字符，英文全拼 | `params/` `task-sorting/` |
| 代码文件 | 英文全拼驼峰（语言惯例优先） | `sortTaskPriority.py` `TaskSorter.java` |
| 数据文件 | 小写 + 下划线 + 日期 | `schedule_2026-11-13.json` |
| 文档 | 小写连字符 | `task-sorting.md` |

禁止：拼音缩写、`utils2`、`final`、`new`、`tmp`、`test1`、中文文件名、空格。

**框架或语言强制约定优先**：Maven/Gradle、Cargo、CMake、Django 的目录布局不要为规范而对抗工具。

## 约束

- 路径深度 ≤3 层（部件内 `src/<模块>/<文件>` 到顶）。再深说明该拆部件。
- 同一目录文件数 ≤12。超了按职责拆子目录。
- 一个部件内部固定四件事：`src/`（源码）、`tests/`（该部件的测试）、`scripts/`（该部件的启动/校验脚本）、可选 `data/`。

## 数据目录

```text
data/2026-11-13/20261113T2310-run-a1b2/
  input.json   params.snapshot.json   output.json   run.log
```

硬规则：

- 产物**必须**先按日期分目录，再按一次运行分目录；平铺在 `data/` 或 `results/` 下的产物视为不合格。
- 每次运行复制一份当时的 `params.json` 快照进去，否则结果不可复现。
- 产物只增不改；要修正就重跑一次、产生新目录。

## 各语言落地要点

- **Python**：`src/<package>/` 一个包，单元一个文件；入口 `main.py` 只做参数解析与调度。
- **Java**：跟 Maven/Gradle 标准布局，包名按部件分段；入口类只做组装。
- **Rust**：Cargo workspace，一个 crate 一个部件；模块文件与职责同名。
- **C++**：`include/` 放公共头、`src/` 放实现、`cmake/` 放构建；一个编译单元一个职责。

## 单元粒度

一个单元 = 一个文件，满足三条：有明确输入输出、能单独运行、能单独验证。

- 入口/编排脚本 ≤80 行，只解析参数、串流程、转错误码。
- 核心逻辑 200–400 行，纯函数为主，不碰时间/随机/网络/数据库。
- IO 适配器尽量薄，一个外部系统一个文件。
- 超过 400 行且无法一句话说明职责 → 拆。

拆分不是目的，可验证性才是：拆完必须每个单元都配得上测试，否则只是把复杂度挪了个位置。
