# P30 复杂解释与官方资料适用性评测 v1

状态：预推理冻结已本地验收（2026-10-19），待本实现提交的远端 CI 成功后，再且仅再运行一次固定 `qwen3.5:2b` cohort。当前没有模型结果，也没有完成的独立人工 assessment。

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

下一步是提交、推送并跟踪本冻结实现的远端 CI。远端成功前禁止目标模型调用；完成的独立人工 assessment 前，P30 的一般复杂解释、真实资料适用性和人工可用性仍为 pending。配置写入、SocketCAN、硬件和认证 operator 仍关闭。
