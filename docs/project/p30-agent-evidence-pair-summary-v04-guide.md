# P30 控制面证据对摘要 0.4

状态：remote-accepted。实现提交 `bf2447fb4895668c1b5699492160bfb9f464fd73` / [run `39942378767`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39942378767)，head 一致、七个实际 job 全部 success。日期：2026-10-23。

## 动机与兼容性

0.3 held-out v1 的 18/18 个状态/原因均精确匹配冻结参考，但 physical-ECU 证据边界硬门为 0/3。因此 0.4 不再要求模型自行重复固定的边界句：控制面在面向用户的最终摘要中确定性附加它。

0.4 不改既有 0.3 plan、request、response、trace、result schema 或 verifier。新结果包含完整 `base_result`（原 0.3 结果）、原文 `model_summary` 与最终 `summary`；`summary` 被精确规定为原文、空行、固定声明。固定文本标注“由控制面附加”，说明摘要仅反映被引用项目报告，不证明物理 ECU 行为、配置写入或实车执行，也不支持超出各检查已记录原因的根因判断。

```bash
python -m automotive_workbench.cli run-agent-evidence-pair-summary-v04 \
  path/to/project-report.json output/agent-evidence-pair-plan.json \
  --model qwen3.5:2b \
  --output output/agent-evidence-pair-summary-result-v04.json

python -m automotive_workbench.cli verify-agent-evidence-pair-summary-result-v04 \
  path/to/project-report.json \
  output/agent-evidence-pair-plan.json \
  output/agent-evidence-pair-summary-result-v04.json
```

Verifier 先将 `base_result` 交给完整 0.3 verifier，以原始报告重建 facts 并核对模型 exchange、预算、身份和 trace；随后检查 0.4 envelope 的 status/ID 对应关系，并精确重建最终摘要。拒绝或阻断时不发布摘要；固定声明仍作为 protocol metadata 留在结果中。`semantic_assessment` 始终为 `unassessed`：确定性边界文案不能证明模型对 status/reason 的语义理解正确。

## 本地验证与限制

针对性协议与 schema 测试通过；全量 525 个既有用例通过（2 项环境跳过），新增 refusal regression 随后单独通过，所以当前 526 个用例均已执行/覆盖，但最后一次全量运行尚未包含新增用例。93 schemas、79 schema-bound examples、25 syntax-only examples、Ruff、Agent evidence scoped mypy、CI topology、compileall、diff check 均通过。全量测试先在默认沙箱因缺少 venv setuptools 及禁止 loopback bind 出现 3 个环境错误；补齐构建工具并在授权 loopback 权限下完整重跑后 525 tests 全绿。

0.4 实现提交 `d66e54c` 已推送，但对应 run `39931330099` 的 Windows 核心测试因新 schema 中中文常量被旧测试以 cp1252 默认编码读取而失败（12 个 subtests 共享同一 `UnicodeDecodeError`）；runtime-currency 与 Ubuntu core-contracts success，downstream jobs skipped，故仍未 remote-accepted。已将 schema 字符串替换为等价 JSON `\u` 转义，并通过 PairSummary + 通信图回归 18/18、93 schemas、Ruff、scoped mypy、CI topology 与 diff check；该修复尚未提交/推送。没有运行真实模型。修复提交取得 head 一致且七 job 全绿后，才冻结全新 development-only 报告、问题、Codex transcription reference、边界检查 criteria、模型 digest 与预算并运行 Qwen 一次，停服后离线复验。新开发题达标后再冻结新 held-out cohort。旧 held-out v1 保持 `failed_for_the_requested_task`，不改写或重跑；独立人工 assessment 仍 pending。

状态回填（2026-10-23）：上一段“尚未提交/推送、未获远端 CI”记录的是首次 CI 失败后的临时状态，已被修复并 superseded。提交 `bf2447fb4895668c1b5699492160bfb9f464fd73` 将 schema 固定文案改为语义等价的 ASCII JSON Unicode escapes；[run `39942378767`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39942378767) head 一致，七个实际 job 全部 success：Windows core `120376688704`、Ubuntu core `120376688891`、runtime-currency `120376688960`、controlled-rejections Ubuntu `120380021668` / Windows `120380021688`、runtime-evidence Windows `120380021773` / Ubuntu `120380022000`。因此 0.4 已 remote-accepted。此后已本地推理前冻结[development v1](../research/p30-agent-evidence-pair-summary-v04-development-v1.json)，freeze SHA-256 `2d9332e322689d77e0c67d0716902d83ac7b6b199f61f5d69683c51186f539f7`：全新 report SHA `cb17e447…8b77453`、4-pair plan `40967689…9224b8`、Codex transcription reference/边界 criteria、qwen3.5:2b digest 与 1 call/4096 token budget；report、plan 均离线验证通过，result 路径不存在，尚未调用 Qwen。下一步先推送冻结包并取得该冻结提交自身 CI success，再重验 Ollama/model digest、恰运行一次并停服后离线验证。旧 held-out v1 保持真实 `failed_for_the_requested_task`，不改写或重跑，独立人工 assessment 仍 pending。

该实现不增加写配置、商业工具、SocketCAN、硬件、approval、claim 或 execution 权限。
