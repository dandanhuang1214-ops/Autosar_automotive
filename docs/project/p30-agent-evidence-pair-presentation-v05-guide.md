# P30 证据对确定性呈现 0.5

状态：remote-accepted。实现 `fe9777cf14974ed386cc6cdce7913f22491c92a3` / [run `40055697502`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40055697502) head 一致、七 job 全部 success。日期：2026-10-24。

## 用户路径

0.4 的真实结果保留原状。0.5 只在本地读取可复验的项目报告、0.3 plan 和 0.4 result，不调用 Ollama，不修改原报告或结果。先完整复验 0.4 的 trace、report binding 与模型交换，再从已验证的 selection 按 plan 顺序呈现每项原始 `status/reason`、事实 ID 和 JSON Pointer。用户可见 `summary` 只由这些事实和既有控制面证据边界生成；模型原文单列为 `model_summary`，状态固定 `unassessed`。

```bash
.venv/bin/python -m automotive_workbench.cli render-agent-evidence-pairs-v05 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  path/to/agent-evidence-pair-summary-result-v04.json \
  --output output/agent-evidence-pair-presentation-v05.json

.venv/bin/python -m automotive_workbench.cli verify-agent-evidence-pairs-v05 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  output/agent-evidence-pair-presentation-v05.json
```

输出路径必须不存在，旧 0.3/0.4 文件、schema、命令和冻结 cohort 均不改。`presentation_status=presented` 只说明报告中全部指定 pair 可复验；`source_protocol_status` 另行保留 0.4 的 `passed/refused/blocked`。因此服务阻断但已完整选择事实时，可以显示确定性事实表，同时继续显示 `source_protocol_status=blocked` 与 `model_summary_status=unavailable`。缺失或歧义 pair 时不发布摘要，`presentation_status=unavailable`。这不是模型解释通过，也不改变项目工程状态。

## 本地真实证据

对原 development v2 的完整结果 `f8a00c87…82722` 离线重放，0.5 result `2195dcd4f740ac65d9311966a325d6bab05619c3fc4c17f2ea87e9dcc7ab6acb` / SHA-256 `c33e4fa2d4e4ef813648efa19cae6e524d42b2006a29e8279f533b53fe19ad0f`：5/5 pair 逐项呈现 `APPLICATION`、`TASK-BINDINGS`、`MODE-RULES`、`TASK_REF`、`TASK_PRESENT` 的精确原值；`source_protocol_status=passed`、`model_summary_status=unassessed`，停服 verifier passed。旧模型文本遗漏 reason 的失败结论不变。

对原 development v1 的环境阻断结果 `4e83a8b9…c730` 只读重放，0.5 result `2ade309c…27fdf04` / SHA-256 `22f41cfa505907d541cdd132bf6058f48b64d506955aff7f9af4167c84227ba7`：4/4 报告 pair 可呈现，但 `source_protocol_status=blocked`、`model_summary_status=unavailable`，停服 verifier passed。不能把事实表当作一次成功的模型推理。

当前输出保存在 `output/p30-pair-summary-v05-development-v2.json` 和 `output/p30-pair-summary-v05-blocked-v1.json`，属于本机忽略的离线证据；输入报告、plan、0.4 result 的身份仍由外层完整保存并由 verifier 重算。0.5 schema、正例/缺项/篡改/错报告代入测试和 CLI 已本地通过。实现 run `40055697502` 的七个实际 job 全部 success：core-contracts Windows `120758077152`、Ubuntu `120758077241`；runtime-currency `120758077263`；runtime-evidence Windows `120759513619`、Ubuntu `120759513667`；controlled-rejections Windows `120759513672`、Ubuntu `120759513722`。后续纯文档状态提交不替代该实现 run。

## 下一门

这一步解决**指定事实逐项可见**，未解决一般因果解释或官方资料的适用性。下一门预推理冻结全新开发题，检查模型文本是否提供有证据支持、可保留的附加解释；只有开发题通过，才冻结新 held-out。独立人工审阅继续待完成。配置写入、SocketCAN、硬件和认证 operator 权限不扩大。
