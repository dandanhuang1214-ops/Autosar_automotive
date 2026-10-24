# P30 验收项原文绑定的证据对输入 0.6

状态：remote-accepted。实现 `6bc0a1c524c51e25beebf42398f9e043ecefb3a0` 的首次 [run `40119153119`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40119153119) 因 0.4 包装器动态关键字的 mypy 错误失败；修复提交 `9553d8b5d13ca78d56781a307b01266d168b6f09` / [run `40119433138`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40119433138) head 一致、七 job 全部 success。日期：2026-10-25。

## 用法

继续使用既有 0.3 plan。0.6 从已复验的项目报告按固定 check ID 选出完整 `status/reason` 对，同时取同一验收项的原始 `text`；ID、stage、pointer 必须唯一对应。报告的原始字节哈希与 selection 绑定，缺少、歧义或漂移的原文在调用模型前阻断。模型请求包含逐项验收原文与事实对，并明确验收描述本身不能证明运行观察、根因或物理 ECU 行为。

```bash
.venv/bin/python -m automotive_workbench.cli run-agent-evidence-pair-summary-v06 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  --model qwen3.5:2b --output output/pair-result-v06.json

.venv/bin/python -m automotive_workbench.cli verify-agent-evidence-pair-summary-result-v06 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  output/pair-result-v06.json

.venv/bin/python -m automotive_workbench.cli render-agent-evidence-pairs-v06 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  output/pair-result-v06.json --output output/pair-presentation-v06.json

.venv/bin/python -m automotive_workbench.cli verify-agent-evidence-pairs-v06 \
  path/to/project-report.json path/to/agent-evidence-pair-plan.json \
  output/pair-presentation-v06.json
```

0.6 结果和呈现均有独立 schema 与 CLI。旧 0.3/0.4/0.5 合约、冻结题和结果不改。0.6 的用户可见 `summary` 仍由确定性 pair 和固定证据边界生成；`model_summary` 单列为 `unassessed`，不能覆盖项目状态。服务阻断且选取完整时仍能展示事实，来源状态保持 `blocked`。输出路径须为空。

## 验证与边界

正例使用公开 ECUC integration 项目，核对模型请求、工具 projection、报告原文、离线 trace 和 0.6 确定性呈现；缺失原文在模型服务前阻断，替换报告拒绝离线重放。0.3/0.4/0.5 回归继续通过。内容是否减少无依据推断尚无真实模型结果；下一步在全新开发题中预冻结报告、plan、具体关系判据、模型身份与调用预算，先取得冻结提交自己的 CI，再执行恰一次目标推理与停服复验。通过内容开发门后才设计 held-out v2；独立人工适用性审阅仍待完成。

本地全量 530 tests 通过（2 项环境跳过），96 schemas / 79 bound / 25 syntax-only、Ruff、完整 scoped mypy、CI topology 和 diff check 通过。修复 run 的 job：Windows core `120947541485`、Ubuntu core `120947541714`、runtime-currency `120947541616`、Windows runtime-evidence `120949782169`、Ubuntu runtime-evidence `120949782269`、Windows controlled-rejections `120949782243`、Ubuntu controlled-rejections `120949782297`，均 success。另用公开 `timeout` 报告和合成客户端验证 4/4 原值绑定、源结果与呈现停服式离线复验通过；合成客户端不是目标模型质量证据。
