# P30 Codex-reference / Qwen 证据解释对比 v1

状态：**remote-accepted / fixed result failed**（2026-10-20）。四道题、Codex 参考答案、评审要点、项目/资料摘要、目标模型 identity 和预算在推理前冻结；冻结实现远端七 job 全部成功后，`qwen3.5:2b` 只运行一次，结构结果为 0/4 failed，且已停服离线复验。

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

目标运行目录必须不存在。运行中逐题写入 result 和 partial 进度；完整结果写 `comparison.json`。本 cohort 已产生唯一结果，不修改、不重跑。

## 本地验收

- 完整回归 518 tests 通过，2 项按环境跳过；4 项新测试覆盖预推理 reference、目标/参考隔离、停服离线复验、manifest/reference 篡改、模型 identity、输出保护、已签入 manifest 的实现摘要与 schema。
- 89 schemas / 79 schema-bound examples / 25 syntax-only examples、Ruff、scoped mypy、CI topology、compileall、pip 与 diff check 通过。
- 隔离无依赖 wheel 从 checkout 外导入并复验冻结 manifest；wheel SHA-256 `737f726bb04f2fa624786a0579a660a48b261f76d44293981bda018e13863673`。

## 远端验收与唯一实跑

冻结实现提交 `452a55d4f0cf80c8b96e276a2d6b4bc9d1d60350` 的 [run `39366567431`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39366567431) completed/success，head 一致。七个实际 job 均 success：runtime-currency `118444660067`；core-contracts Windows `118444660262`、Ubuntu `118444660295`；runtime-evidence Ubuntu `118446893667`、Windows `118446893785`；controlled-rejections Ubuntu `118446893731`、Windows `118446893774`。评测实现 remote-accepted；后续文档状态提交不替代该 run。

远端通过后才启动既有 Ollama 容器并核对服务 `0.31.1`、模型 `qwen3.5:2b` 与完整 digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df`。仓库只读、仅 `output/` 可写的固定 cohort 只运行一次；结果 ID `8990c7ce1e9b98c43e10d38d93017ff3613895e17e3cf0cdd492032bf76037ee`，结构结果 **0/4 failed**：4 次模型调用、6 次固定只读工具调用、3160 tokens。工具计划全部正确，但四题均未形成通过结构和完整引用的最终答案：两题返回错误对象形状，一题返回非法 JSON，一题没有有效响应。

停止 Ollama 后，离线 verifier 返回 `status=passed` / `comparison_status=failed` 与同一 result ID。这证明工件、身份、计划和评分可重放，不把模型失败改写成通过。

## Codex 对照结论

Codex 按冻结 criteria 对保留的原始 Qwen 文本作非盲诊断：12 条标准中 4 条满足、2 条部分满足、6 条不满足。Qwen 能复述两项 blocked reason 和 `project validate` 的主要范围，但遗漏受限后续步骤与安装/许可边界；因果题又把 `snapshots_not_comparable` 过度解释为数据完整性或快照生成问题，并没有列齐 package identity/version/path/dialog 与实际 validate 命令证据；工单题无响应。诊断文件 SHA-256 为 `c7f3a1362ae3e5ff8867a3515ebc6785e9ddf4b88a57ba58e1e307d507a6e7c7`，它位于本地忽略的 `output/p30-agent-evidence-comparison-v1-codex-review.json`。

这个 Codex 对照是 user-authorized、non-blind、not an independent human，不是独立人工 gold。主结论仍是：控制面已修复工具路由和证据取得，但当前 qwen3.5:2b 未能产生可发布的复杂解释。下一门只在新的协议版本和新 cohort 上研究更小的摘要接口或更强文本模型，同时等待独立审阅者完成原 review pack；旧复杂解释 v1 和本 cohort 都不修改、不重跑。配置写入、SocketCAN、硬件和认证 operator 继续关闭。
