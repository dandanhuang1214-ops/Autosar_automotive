# P30 Codex-reference / Qwen 证据解释对比 v1

状态：**pre-inference frozen / local-accepted**（2026-10-20）。四道题、Codex 参考答案、评审要点、项目/资料摘要、目标模型 identity 和预算已经冻结；`qwen3.5:2b` 尚未在本 cohort 上调用。

## 对比边界

本门落实用户提出的“先由 Codex 回答，再让 Qwen 生成并对比”，但不把 Codex 冒充独立人工 gold：

- [spec](../research/p30-agent-evidence-comparison-v1-spec.json) 中的四个 reference answer 在目标模型推理前形成；它们明确标注为 agent-authored reference。
- [manifest](../research/p30-agent-evidence-comparison-v1-manifest.json) 将 reference、criteria、每题确定性 evidence plan、项目报告/bundle 摘要、资料 policy/corpus、模型 digest、预算和实现摘要一起哈希绑定。
- runner 只把 goal 与控制面取得的 observation 发给模型，绝不把 reference answer 或 criteria 放入模型消息。
- 自动门只评分 `status`、固定工具序列、完整引用、单次模型调用、identity 与成本。它把 Qwen 目标文本和冻结 reference 并列保存，但 `semantic_status` 固定为 `pending_comparative_review`。
- 后续 Codex 对照可按预先写定的 criteria 逐项说明差异；它仍不是独立人工可用性结论，不能关闭 P30 的独立人工门。

## 冻结题组

四题复用公开 `ambiguous` 报告和已审核 Vector 摘要，以便把回答完整性与旧版工具路由失败分开：

1. 项目-only 交接：两个 blocked 检查的 status/reason、可证与不可证边界。
2. 资料-only 说明：`dvcfg-b project validate` 的检查范围、输入、退出条件和无运行证据时的表述。
3. 混合因果：能否把 Workbench blocked 归因于 BSW Package identity mismatch，以及最小缺失证据。
4. 混合工单：按依赖顺序区分 `ambiguous_target`、`snapshots_not_comparable` 与条件性的 package mismatch/validate 路径。

manifest ID 为 `67d556349f3d60bd751081c70ef181993888b0247796b4790d8109a7e3f82cab`，实现摘要为 `cf95fe36956c0149f014bac7c49c64680c46cbc03c45a7fd00bae8d2acfd9671`。模型固定为 `qwen3.5:2b` / digest `324d162b…20df`；每题最多 2 个固定 read tool、1 次模型调用、6000 total tokens、512 output tokens 和 120 秒。

## 操作顺序

冻结与离线核对：

```bash
python -m automotive_workbench.cli freeze-agent-evidence-comparison \
  docs/research/p30-agent-evidence-comparison-v1-spec.json \
  --root . --implementation-root . \
  --model qwen3.5:2b \
  --model-digest 324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df \
  --knowledge-policy examples/knowledge/p30-vector-official-policy.json \
  --knowledge-corpus examples/knowledge/p30-vector-official-corpus.json \
  --output docs/research/p30-agent-evidence-comparison-v1-manifest.json

python -m automotive_workbench.cli verify-agent-evidence-comparison-manifest \
  docs/research/p30-agent-evidence-comparison-v1-manifest.json
```

只有冻结实现提交自己的远端七 job 全部 success 后，才能运行目标模型一次：

```bash
PYTHONPATH=src python scripts/run_agent_evidence_comparison.py \
  docs/research/p30-agent-evidence-comparison-v1-manifest.json \
  --root . --implementation-root . \
  --manifest-id 67d556349f3d60bd751081c70ef181993888b0247796b4790d8109a7e3f82cab \
  --output output/p30-agent-evidence-comparison-v1

python -m automotive_workbench.cli verify-agent-evidence-comparison \
  docs/research/p30-agent-evidence-comparison-v1-manifest.json \
  output/p30-agent-evidence-comparison-v1
```

目标运行目录必须不存在。运行中逐题写入 result 和 partial 进度；完整结果写 `comparison.json`。看到结果后不修改或重跑本 cohort。

## 本地验收

- 完整回归 518 tests 通过，2 项按环境跳过；4 项新测试覆盖预推理 reference、目标/参考隔离、停服离线复验、manifest/reference 篡改、模型 identity、输出保护、已签入 manifest 的实现摘要与 schema。
- 89 schemas / 79 schema-bound examples / 25 syntax-only examples、Ruff、scoped mypy、CI topology、compileall、pip 与 diff check 通过。
- 隔离无依赖 wheel 从 checkout 外导入并复验冻结 manifest；wheel SHA-256 `737f726bb04f2fa624786a0579a660a48b261f76d44293981bda018e13863673`。

下一步是提交冻结实现并完成其远端七 job。远端通过前不运行 Qwen；旧复杂解释 v1 的 0/4、Codex 非盲诊断和 pending 独立人工门都保持原样。配置写入、SocketCAN、硬件和认证 operator 继续关闭。
