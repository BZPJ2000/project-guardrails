# 初始化会话：先问，再建

新项目的第一件事永远是 `git init`，第二件是问清四组问题。跳过任何一组，后面都会返工。

## 顺序（不可调换）

1. `git init` + `.gitignore` + 空仓库首次提交。
2. 问下面四组问题，得到人的明确回答。
3. 跑 `bootstrap.py` 生成骨架。
4. 人填 `params/params.json`。
5. 补 `module-map` 与各部件文档的「责任边界」「不负责」两栏。
6. `gate.py all` 通过后，才写第一行业务代码。

## 四组问题（直接复制去问）

**A. 部件与边界**

- 这个项目分哪几个部分？（前端 / 后端 / 算法 / 数据 / 采集 / 部署……）
- 每个部分**只**负责什么？明确**不负责**什么？
- 哪个部分是"权威"的？同一份数据谁产生、谁只读？

追问判据：如果一个部件说不清"不负责什么"，边界就没定完。

**B. 通信**

- 部件之间怎么传数据：文件 / HTTP / 消息队列 / 函数调用？选一个写死。
- 传输格式是什么？谁定义 schema？
- 失败怎么表达：错误码还是异常？调用方拿到错误后做什么？

**C. 数值参数**

- 这个项目里哪些数字是**业务决定**的、不能由实现者随手定？（尺寸、阈值、容量、超时、权重……）
- 每个数字的单位、合理范围、默认值？

这些一律进 `params/`，由人填。参考 `params.md`。

**D. 运行环境**

- 跑在哪：本机 / 云服务器 / 容器？端口？
- 上线要几步？谁执行？失败怎么回滚？
- 数据放哪？保留多久？

## 生成物清单

`bootstrap.py` 应产出且只产出这些：

```text
.gitignore  AGENTS.md  guardrails.json  README.md
docs/module-map.md  docs/parts/<part>.md  docs/contracts/<part>.md
contracts/<part>.json  params/params.schema.json  params/params.example.json
tests/units.json  tests/cases/  tests/evidence/
data/  scripts/  .agent/changes/
```

不建空架构层。没有真实内容的目录不要建。

## 完成判据

- 四组问题都有人给出的答案（不是 AI 猜的）
- `params.json` 无 `__TBD__`
- `gate.py all` 退出码 0
- 人确认过 module-map 的部件划分

四条全满足才算"初始化完成"；缺一条就还在初始化阶段，不许开始写功能。
