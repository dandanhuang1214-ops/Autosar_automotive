# Automotive Software Engineering Workbench

平台路线、升级状态、环境记录和技术调研统一从 [`docs/README.md`](docs/README.md) 进入。每次功能或环境升级都必须同步更新 [`docs/project/progress-log.md`](docs/project/progress-log.md)。

这是统一汽车软件工程平台的轻量骨架。当前版本只做四件事：

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

当前不生成ECUC、不替代供应商BSW generator，也不需要Docker、GPU、Qdrant或LLM。

## 运行

核心追踪无需第三方依赖；DBC 功能安装可选 CAN 依赖：

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
- `examples/window_control/uds_intent.json` 是公开学习样例和vendor-neutral诊断意图，不是量产DCM/DEM或OEM诊断规范。
- `examples/window_control/dtc_intent.json` 中的 debounce、operation-cycle、aging、snapshot 和 status byte 仅用于可重复研究实验，不是量产 DEM displacement、NVRAM、OBD 或 OEM 策略。
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

当前GitHub Actions在Windows和Ubuntu 22.04上运行单元测试、CLI smoke test和JSON语法检查。现在只有CI，没有CD；等出现可发布CLI包、容器或文档站后再设计发布流程。
