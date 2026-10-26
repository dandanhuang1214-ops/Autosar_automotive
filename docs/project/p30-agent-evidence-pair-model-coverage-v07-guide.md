# P30 模型原文字面覆盖门 0.7

状态：remote-accepted。实现 `0cb238b253b79240b73453887c8a62d454ce0967` / [run `40252739257`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40252739257) head 一致、七 job 全部 success。0.7 只读消费已复验的 0.6 呈现，旧 0.3–0.6 结果与模型请求保持不变。

```bash
workbench assess-agent-evidence-pair-model-v07 REPORT PLAN PRESENTATION --output COVERAGE
workbench verify-agent-evidence-pair-model-v07 REPORT PLAN PRESENTATION COVERAGE
```

每个检查要求模型原文中恰有一整行 `CHECK_ID: status="原值"; reason="原值"`。0 行或重复行均为 `incomplete`；无模型原文为 `unavailable`；全部匹配才是 `complete`。覆盖结果绑定 0.6 呈现的字节哈希、ID 和顺序，保存每项规范行及出现次数，可在模型服务停止后复验；篡改计数或呈现内容会拒绝。模型原文始终是 `semantic_assessment=unassessed`，即使字面覆盖 complete，也还需要独立审阅关系、来源适用性和无依据断言。

真实 `wrong-mapping` development v2 的旧模型原文经 0.7 得到 `incomplete`、0/4 条规范行；这是严格格式门的结果，不把其中出现的个别事实抹去，也不修改旧题的[逐项审阅](../research/p30-agent-evidence-pair-projection-v06-development-v2-review.json)。确定性用户摘要仍完整显示 4/4 原值。下一步在新开发题中明确要求模型输出规范行并冻结内容判据，取得冻结提交自身 CI 后只运行一次；旧题不重跑。通过开发门后才进入 held-out v2 与独立人工适用性审阅。

本地全量 531 tests 通过（2 项环境跳过）；97 schemas / 79 bound / 25 syntax-only、Ruff、scoped mypy、CI topology、diff check 通过。远端成功 job：runtime-currency `121347955846`、core Windows `121347956135` / Ubuntu `121347956076`、runtime-evidence Windows `121350594005` / Ubuntu `121350593979`、controlled-rejections Windows `121350594034` / Ubuntu `121350594002`。此 run 验收覆盖门实现，不评价模型解释的语义质量。
