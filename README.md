# Automotive Software Engineering Workbench

平台路线、升级状态、环境记录和技术调研统一从 [`docs/README.md`](docs/README.md) 进入。每次功能或环境升级都必须同步更新 [`docs/project/progress-log.md`](docs/project/progress-log.md)。

这是统一汽车软件工程平台的轻量骨架。当前版本围绕统一契约、静态映射、确定性运行实验和可审计证据四条主线展开，以下为已落地能力：

1. 定义跨工具稳定的 `Artifact`、`Finding`、`Trace`、`TestResult` 数据契约；
2. 将 Generate-Arxml 的 `issues.json` 转换为统一 Finding；
3. 查询公开样例中 `DBC Signal → SWC → COM → I-PDU → PduR → CanIf` 的研究映射。
4. 用 cantools 读取 DBC，并确定性校验 DBC 与 BSW intent 中的帧和信号属性。
5. 对接 Generate-Arxml canonical contract，校验名称映射、缩放、偏移、单位和物理范围。
6. 一次运行基线和五个故障注入场景，生成 JSON 与 Markdown 工程证据报告。
7. 使用 python-can virtual 运行双节点报文收发、解码、超时和故障检测实验。
8. 运行周期通信、周期/抖动观测、丢帧超时和恢复状态转换实验。
9. 录制 can-utils 日志、使用 DBC 离线解码并向 virtual/SocketCAN 后端回放。
10. 探测 CAN backend 能力，并在 virtual/SocketCAN 上复用同一实验契约。
11. 使用 UDS intent 在 python-can virtual 上运行 positive/NRC/timeout/malformed payload 诊断场景，并在诊断 lab 中归档 backend probe/blocked 证据。
12. 使用精确 CAN ID filters 和按 channel 命名的进程锁隔离共享 SocketCAN 实验，并在报告中记录 isolation/contamination 证据。
13. 使用 DTC intent 运行 absent/pending/confirmed/healing/healed/clear 确定性生命周期，并通过 UDS `0x19/0x14` 读取和清除 DTC。
14. 显式运行 diagnostic operation cycle，仅在 tested-pass cycle end 累加 aging，并归档/读取/删除 confirmed-trigger DTC snapshot。
15. 读取 occurrence/aging extended data，并验证未知 DTC、未知 record、非法 cycle 顺序和 malformed snapshot 负面场景。
16. 区分 DTC 运行态与进程内持久镜像，并通过 UDS hard reset 验证 flush 后恢复、未 flush 丢失和 clear 后不复活。
17. 对 DTC 持久镜像注入 flush failure 和 checksum corruption，验证 last-good 保留、完整性拒绝和空状态安全回退。
18. 使用双副本 generation 与独立 checksum 验证新副本选择、loss-of-redundancy 报告和损坏新副本后的旧副本回退。
19. 使用 staged/committed 标记验证中断写入的 last-good 回退、幂等冗余修复和中断 repair 后的源副本保留。
20. 对显式本地 JSON artifact 运行 retrieval-only 工程审查，验证 JSON Pointer citation、required-check coverage 和证据不足拒答。
21. 对显式 JSON/Markdown artifact 执行跨来源 assertion 与 14 案例、30 checks 的 gold evaluation，覆盖 core、DBC-derived contract、CAN/BSW、UDS 和 DTC。
22. 通过白名单 producer 生成并审查 CAN/UDS/DTC runtime report，运行独立 held-out negative evaluation，并把实际报告 SHA-256 注入审查请求。
23. 配对两次独立 CAN/UDS/DTC 运行，只比较显式稳定字段；对白名单字段注入 drift 并验证冲突，同时拒绝比较 run ID、时间、耗时和 channel 等动态字段。
24. 导入已存在且 SHA-256 固定的 CAN/UDS/DTC CI/外部 runner 报告执行 cohort evaluation，无需 evaluator 现场重跑 producer，并归档哈希绑定的 run/job/commit provenance。
25. 对外部报告 SHA、provenance、调用方 expectation 和 cohort policy 预检失败生成最小机器可读 rejection artifact，同时保持 CLI 非零退出且不物化 review request。
26. 在 Windows/Ubuntu CI 中分别上传正常固定报告 cohort 与可控 SHA-256 拒绝证据，并校验拒绝命令确实失败、最小证据闭合且无 request/result 旁路物化。
27. 从本地 ECU 视角显式校验 DBC sender/receiver 与 BSW intent 的 Tx/Rx 方向，并输出 `DBC Signal → SWC → COM → I-PDU → PduR → CanIf` 逐链路证据。
28. 在同一次编排中运行静态映射与双向 virtual CAN 场景，以 message/signal identity、方向和 frame ID 将两层证据绑定为闭合通信链报告。
29. 为本地证据目录生成可移植 manifest，登记相对路径、类型、schema、producer、SHA-256，以及报告显式声明的 bundle 内部和外部依赖。
30. 使用已有 manifest 事后验证 bundle 与外部依赖，确定性报告 missing、unexpected、tampered 和 dependency failure，并在 CI 演练可控篡改拒绝。
31. 用一条命令串联通信链运行、bundle 索引、完整性验证与 receipt，保留 `passed/failed/blocked` 业务状态并单独记录 integrity 状态。
32. 将 P7 交付导出为自包含 evidence capsule，仅复制 manifest 声明的外部依赖，移出原工作区后仍可离线验证。
33. 对整个 capsule 执行事后库存与依赖图验证，检出顶层 receipt/verification/Markdown、bundle、external dependency 的 missing、unexpected、tampered 和 unsafe file。
34. 用 Draft 2020-12 schema 校验自描述样例，在 Python 3.14 上复跑全量测试，并归档解释器、平台和关键依赖的 resolved inventory。

当前不生成ECUC、不替代供应商BSW generator，也不需要Docker、GPU、Qdrant或LLM。

## 运行

核心追踪无需第三方依赖；DBC 功能安装可选 CAN 依赖：

运行完整测试、schema、Ruff 和 mypy 门禁时安装 `python -m pip install -e ".[diag,dev]"`。

```powershell
python -m pip install -e ".[can]"
$env:PYTHONPATH='src'
python -m automotive_workbench.cli trace examples/window_control/bsw_intent.json WindowPosition
python -m automotive_workbench.cli inspect examples/generate_arxml/issues.sample.json
python -m automotive_workbench.cli inspect examples/window_control/window_control.dbc
python -m automotive_workbench.cli validate-map examples/window_control/window_control.dbc examples/window_control/bsw_intent.json
python -m automotive_workbench.cli validate-contract examples/window_control/window_control.dbc examples/window_control/canonical_contract.json examples/window_control/bsw_intent.json
python -m automotive_workbench.cli run-suite examples/window_control/window_control.dbc examples/window_control/canonical_contract.json examples/window_control/bsw_intent.json --output output/latest
python -m automotive_workbench.cli run-can-lab examples/window_control/window_control.dbc --output output/latest
python -m automotive_workbench.cli run-can-supervision examples/window_control/window_control.dbc --output output/latest
python -m automotive_workbench.cli run-communication-chain examples/window_control/window_control.dbc examples/window_control/bsw_intent.json --output output/communication-chain
python -m automotive_workbench.cli run-communication-delivery examples/window_control/window_control.dbc examples/window_control/bsw_intent.json --base . --output output/communication-delivery
python -m automotive_workbench.cli export-evidence-capsule output/communication-delivery --base . --output output/evidence-capsule
python -m automotive_workbench.cli verify-evidence output/evidence-capsule/bundle output/evidence-capsule/manifest.json --base output/evidence-capsule --output output/evidence-capsule-recheck
python -m automotive_workbench.cli verify-evidence-capsule output/evidence-capsule --output output/evidence-capsule-verification
python -m automotive_workbench.cli run-communication-chain examples/window_control/window_control.dbc examples/window_control/bsw_intent.json --interface socketcan --channel vcan0 --output output/socketcan-communication-chain
python -m automotive_workbench.cli index-evidence output/communication-chain --producer "workbench run-communication-chain" --base . --manifest output/evidence-manifests/communication-chain.json
python -m automotive_workbench.cli verify-evidence output/communication-chain output/evidence-manifests/communication-chain.json --base . --output output/evidence-verification
python -m automotive_workbench.cli capture-log --interface socketcan --channel vcan0 --count 10 --output output/capture
python -m automotive_workbench.cli decode-log output/capture/capture.log examples/window_control/window_control.dbc --output output/decode
python -m automotive_workbench.cli replay-log output/capture/capture.log --interface socketcan --channel vcan0 --output output/replay
python -m automotive_workbench.cli run-log-lab examples/window_control/window_control.dbc --output output/log-lab
python -m automotive_workbench.cli probe-can-backend --interface socketcan --channel vcan0 --output output/socketcan-probe
python -m automotive_workbench.cli run-backend-lab examples/window_control/window_control.dbc --interface socketcan --channel vcan0 --output output/socketcan-lab
python -m automotive_workbench.cli inspect examples/window_control/uds_intent.json
python -m automotive_workbench.cli inspect examples/window_control/dtc_intent.json
python -m automotive_workbench.cli run-dtc-lifecycle examples/window_control/dtc_intent.json --output output/dtc-lifecycle
python -m automotive_workbench.cli run-dtc-aging-lab examples/window_control/dtc_intent.json --output output/dtc-aging
python -m automotive_workbench.cli run-dtc-reset-lab examples/window_control/dtc_intent.json --output output/dtc-reset
python -m automotive_workbench.cli run-dtc-persistence-fault-lab examples/window_control/dtc_intent.json --output output/dtc-persistence-fault
python -m automotive_workbench.cli run-dtc-redundancy-lab examples/window_control/dtc_intent.json --output output/dtc-redundancy
python -m automotive_workbench.cli run-dtc-redundancy-repair-lab examples/window_control/dtc_intent.json --output output/dtc-redundancy-repair
python -m automotive_workbench.cli run-review examples/review/review_request.json --output output/review
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/evaluation.json --output output/review-evaluation
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/runtime-evaluation.json --output output/review-runtime-evaluation
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/held-out-negative.json --output output/review-held-out-negative
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/cross-run-evaluation.json --output output/review-cross-run
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/cohort-evaluation.json --output output/review-cohort
python -m automotive_workbench.cli run-review-eval examples/review/evaluation/external-cohort-evaluation.json --output output/review-external-cohort
python -m automotive_workbench.cli probe-uds-backend --interface socketcan --channel vcan0 --output output/socketcan-uds-probe
python -m automotive_workbench.cli run-uds-lab examples/window_control/uds_intent.json --output output/uds-lab
python -m automotive_workbench.cli run-uds-lab examples/window_control/uds_intent.json --interface socketcan --channel vcan0 --output output/socketcan-uds-lab
python -m unittest discover -s tests -v
```

WSL2/SocketCAN host preparation is documented in `docs/socketcan-wsl.md`. Linux scripts default to a read-only probe or dry-run; only `setup_vcan.sh --apply` performs explicit sudo operations.

检查 Generate-Arxml 报告：

```powershell
$env:PYTHONPATH='src'
python -m automotive_workbench.cli inspect D:\path\to\issues.json
```

## 当前边界

- `examples/window_control/bsw_intent.json` 是公开学习样例和vendor-neutral意图，不是量产ECUC。
- `bsw-intent-0.2` 的 `local_ecu` 和 `direction` 是显式研究契约；校验方向来自 DBC sender/receiver，不通过 PduR/CanIf 对象名中的 `Tx`/`Rx` 后缀推断配置语义。
- `run-communication-chain` 以同一个 `BusConfig` 在 virtual 或 SocketCAN 上执行双向通信，并固定 DBC、intent、runtime report 的 SHA-256。SocketCAN 不可用时输出 `blocked` 证据和退出码 3，不把宿主缺失误报为通信失败；它仍不证明目标 ECU、RTE、控制器、电气总线或量产 ECUC 行为。
- `index-evidence` 只读取指定目录与报告显式声明的本地依赖；manifest 必须写在 bundle 外，不跟随符号链接，不下载或复制来源，也不承担 P5b 的事后篡改验证职责。
- `verify-evidence` 对合法 manifest 产生闭合 verification result；bundle 状态变化返回 `status=failed` 和退出码 2，manifest 结构错误返回 CLI error。它验证本地字节完整性，不认证 producer 身份或供应链来源。
- `run-communication-delivery` 在一个空目录中串联已冻结的通信链、manifest 和 verifier，receipt 固定 manifest/verification SHA-256；为避免旧 artifact 混入新证据，非空输出目录会被拒绝。
- `export-evidence-capsule` 先重验 P7 交付及所有依赖，再按 manifest 白名单复制 bundle 和 external files，最后以 capsule 根目录为 portable base 离线复验。它不打包整个仓库，也不提供签名或身份证明。
- `verify-evidence-capsule` 从闭合 capsule report 重建全量文件库存，验证固定哈希、可重建 Markdown 和 P5 依赖图；合法胶囊变化会生成 `status=failed` 证据并返回退出码 2。
- `examples/window_control/uds_intent.json` 是公开学习样例和vendor-neutral诊断意图，不是量产DCM/DEM或OEM诊断规范。
- `examples/window_control/dtc_intent.json` 中的 debounce、operation-cycle、aging、snapshot、extended data、进程内持久镜像、generation、commit marker 和 status byte 仅用于可重复研究实验，不是量产 DEM displacement、NvM、OBD 或 OEM 策略。
- `run-review` 只读取 request 显式列出的本地 JSON/Markdown；跨 artifact 冲突只比较显式 assertion locator，词法匹配和 coverage 不是语义理解、LLM 结论或安全证明。
- `run-review-eval` 使用仓库内 gold locator 和结构化期望，不使用 LLM judge；development、runtime、held-out、cross-run 和 cohort split 都是确定性回归证据，不代表自由问答或量产评审准确率。drift injection 仅允许修改 runner 白名单字段；`review-request-0.5` 在 artifact-bound applicability 基础上显式区分 baseline/candidate，并逐 candidate 输出 `stable/drifted/not-comparable` catalog。evaluator 0.8 进一步汇总全局与 CAN/UDS/DTC 各域状态计数；evaluator 0.9 的 `external_reports` 与 `producer` 互斥，要求每份本地报告提供精确 SHA-256，并在装配请求前验证 JSON 与 artifact-bound applicability profile。evaluator 1.0-1.2 逐步增加报告内 provenance、调用方 expectation 和 cohort repository/job policy；1.3 为这些外部报告预检失败生成不含请求或报告内容的 `review-evaluation-rejection.json`。固定哈希和本地声明匹配不构成 CI 身份认证、远端证明或供应链签名。
- `run-uds-lab --interface socketcan` 会先探测 CAN backend；缺少接口或权限时返回 `blocked`，不把环境不可用误报为诊断业务失败。
- SWC、COM、PduR和CanIf对象名是该公开样例的设计名称，不代表OEM或供应商命名规则。
- 最终正确性仍需规范、供应商BSWMD/generator、运行测试及商业工具验证。

## 后续adapter

```text
adapters/
  generate_arxml   已有v0
  dbc/cantools     已有v0：读取和DBC↔intent校验
  openbsw          第5周spike
  uds              第9周后
  evidence_review  第16周后
  vendor_vector    仅公开样例和合法环境
```

## CI/CD边界

当前GitHub Actions在Windows和Ubuntu 22.04/Python 3.11上运行完整工程链，并用Ubuntu 22.04/Python 3.14执行 runtime-currency 全量回归、Draft 2020-12 schema 实例校验、最小 Ruff 门禁和 evidence 模块范围内的 mypy 门禁；每个环境归档 resolved dependency inventory。现在只有CI，没有CD；等出现可发布CLI包、容器或文档站后再设计发布流程。
