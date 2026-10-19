# P30 复杂解释与官方资料适用性评测 v1

状态：冻结实现已远端验收，固定 `qwen3.5:2b` cohort 已且仅已运行一次（2026-10-19）。机器结果为 0/4 failed，停服离线复验通过；独立人工 assessment 仍待完成。

## 冻结内容

[v1 spec](../research/p30-agent-explanation-review-v1-spec.json) 在任何目标模型调用前写定 4 题，[manifest](../research/p30-agent-explanation-review-v1-manifest.json) 的 ID 为 `c99acf880ff7085ffb0f5821e8b0867415d91506df3a4aa8efb422ed13b95286`。它绑定：

- 从未进入既有 P30 模型 cohort 的 `ambiguous` 项目报告及完整 bundle digest；
- `impact` 的 `blocked / snapshots_not_comparable` 和 `policy.TASK_REF` 的 `blocked / ambiguous_target` 四个结构化 gold 事实；
- 项目事实单独路由、官方资料单独路由、因果边界与只读排查顺序两个混合路由；
- `qwen3.5:2b` 完整 digest、工具顺序、引用要求、每题成本上限与全局预算；
- 知识策略 `b2a213da…90fdb7b8` 与两份文档的内容 digest。

结构化评分只检查工具选择、有效参数、目标事实/资料命中、observation 引用和成本。它不把模型 prose 、因果判断、资料适用性或人工可用性自动认定为通过。

## 官方资料与边界

冻结语料只包含两段维护者撰写的简短摘要，原文定位、版本、取得时间和摘要内容全部进入 hash：

- Vector DaVinci Configurator Classic User Manual 6.4 的 [BSW Package identity 不一致与 read-only 行为](https://help.vector.com/davinci-configurator-classic/en/latest/user-manual/bsw-update/update-bsw-package-behind-the-scenes.html)；
- 同版本的 [`dvcfg-b project validate` 范围](https://help.vector.com/davinci-configurator-classic/en/latest/user-manual/references/cli/dvcfg-b/project-validate.html)。

[corpus](../../examples/knowledge/p30-vector-official-corpus.json) 的 ID 为 `87471de4…ab46e85`。本地服务对每个查询都返回这个仅有两段的完整语料，因此本门测的是模型是否选择已审核资料并尊重边界，不是检索排名质量。

策略中的 reviewer `automotive-workbench-source-curation` 表示维护者对来源允许列表和摘要的冻结；它不是对模型答案的独立审阅。这些资料不能证明本机已安装 Vector 软件、license/SIP 合法可用、命令已运行或某个真实 ECU 项目适用。项目报告中的 Workbench `ambiguous_target` 和 `snapshots_not_comparable` 也不得改写为 DaVinci BSW package mismatch。

## 可重现操作

冻结命令的核心参数为：

```bash
python -m automotive_workbench.cli freeze-readonly-agent-eval \
  docs/research/p30-agent-explanation-review-v1-spec.json \
  --root . --implementation-root . \
  --output docs/research/p30-agent-explanation-review-v1-manifest.json \
  --model qwen3.5:2b \
  --model-digest 324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df \
  --knowledge-policy examples/knowledge/p30-vector-official-policy.json \
  --max-steps 4 --max-model-calls 4 --max-tool-calls 3 \
  --max-total-tokens 6000 --max-output-tokens-per-call 256 \
  --context-window 8192 --max-seconds 120 --max-observation-chars 20000
```

只有冻结提交的远端 CI 与 head 一致且七个 job 成功后，才可执行：

```bash
PYTHONPATH=src python scripts/run_readonly_agent_evaluation.py \
  docs/research/p30-agent-explanation-review-v1-manifest.json \
  --root . --implementation-root . \
  --manifest-id c99acf880ff7085ffb0f5821e8b0867415d91506df3a4aa8efb422ed13b95286 \
  --knowledge-corpus examples/knowledge/p30-vector-official-corpus.json \
  --output output/p30-agent-explanation-review-v1

python -m automotive_workbench.cli verify-readonly-agent-eval \
  docs/research/p30-agent-explanation-review-v1-manifest.json \
  output/p30-agent-explanation-review-v1
```

无论自动分数如何，都从该唯一结果生成 pending 人工审阅包：

```bash
python -m automotive_workbench.cli prepare-agent-human-review \
  docs/research/p30-agent-explanation-review-v1-manifest.json \
  output/p30-agent-explanation-review-v1 \
  --implementation-root . \
  --output output/p30-agent-explanation-human-review-v1
```

不在看到结果后修改本 cohort 或重跑。模型运行后先停止 Ollama，再完成离线重评分、review pack 验签和进度回填。

## 当前验收证据与下一步

本地全量 510 tests 通过（2 项环境跳过）；新增的官方语料加载、内容篡改拒绝、回环 HTTP 检索链和冻结 manifest 身份回归通过。85 schemas / 79 schema-bound examples / 25 syntax-only examples、Ruff、相关 mypy、compileall、pip check 和 CI topology 通过。隔离无依赖 wheel 外加载语料通过，确认 `automotive_workbench` 来自临时 site-packages；wheel SHA-256 为 `06ea0a37151bcbdbb3f5e4b860ab242de4eeff0ddcf2928fd10e9cdea17e2872`。

冻结实现提交为 `c904bd913703890e33d46c709d3efeb0b8ff533b`，[run `39192046821`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39192046821) 与该 head 完全一致且 completed/success。七个实际 job 均为 success：runtime-currency `117866780441`；core-contracts Windows `117866780327`、Ubuntu `117866780586`；controlled-rejections Ubuntu `117868942709`、Windows `117868942802`；runtime-evidence Ubuntu `117868942704`、Windows `117868942722`。因此评测实现 remote-accepted；后续状态文档不替代该 run。

远端通过后复用既有 Ollama 0.31.1，并在调用前核对 `qwen3.5:2b` digest 完全一致。固定四题只运行一次，得到 failed result `dd91e3e751cefd6fec475a30785d316779ea6a217b68c6993ca23040b5874c36`：0/4 题通过；status/tool selection/parameters/citation/cost 分别为 2/4、2/4、2/4、0/4、4/4。两道混合题都选择了项目事实和资料工具，4/4 gold 事实进入结果且检索到文档 101/102；但最终引用均不完整。一道项目题错误选择概览验证工具，一道资料题产生非法 finish action；因果题取得两个 observation 后未形成有效完成响应。四题合计 9 次模型调用、5 次工具调用、8609 tokens；逐题成本门均通过。

Ollama 停止后，离线 verifier 返回 `status=passed` / `evaluation_status=failed` 和相同 result ID。这只证明 artifact 与评分可重放，不改变模型失败结论。由该唯一结果生成的 review pack `761361aa9e8d1b63db6adc5766d2e2cf2fc0d094930fddec0bc756be753fab8c` 已离线验签，4 个 item 的状态为 `pending_human_review`；两题有未认证回答，两题无可审正文。

下一步由独立审阅者填写 `output/p30-agent-explanation-human-review-v1/review-template.json`，再使用既有 finalize/verify 流程固化 assessment。本 cohort 不修改、不重跑；在独立 assessment 完成前，P30 的一般复杂解释、真实资料适用性和人工可用性仍为 pending。后续开发只能在新版本和新 cohort 中处理本次暴露的工具选择、finish action 与 observation 引用问题。配置写入、SocketCAN、硬件和认证 operator 仍关闭。
