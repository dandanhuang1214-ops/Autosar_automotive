# OpenBSW CF01 独立诊断客户端

`read_cf01.json` 固定 classic CAN 11-bit 请求 ID `0x02A`、响应 ID `0x0F0` 和 DID `0xCF01`。期望的 24 字节数据来自 profile 中声明的 OpenBSW referenceApp 基线；更换应用版本时应先核实 DID 定义，再更新 profile。

在 WSL/Linux 仓库根目录安装 `python -m pip install -e '.[diag]'`。先按 `scripts/linux/setup_vcan.sh` 的说明准备 `vcan0`，并在另一个终端启动已构建的 OpenBSW referenceApp：

```bash
/home/dev/work/openbsw/build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf
```

保持应用运行，在仓库根目录执行（输出目录必须为空或尚不存在）：

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli read-uds-did \
  examples/openbsw/read_cf01.json \
  --interface socketcan --channel vcan0 \
  --output output/openbsw-cf01
```

命令仅发送一次 `22 CF 01`，自动完成 ISO-TP Flow Control。正响应应为 `62 CF 01` 加 profile 中的期望数据；帧表包含请求 SF、响应 FF、请求 FC 和响应 CF。客户端不会启动 ECU responder，也不会切换诊断会话。

输出包括 `uds-did-report.json`、`uds-did-report.md`，以及进入请求流程时的 `uds-did.log`。报告记录 profile 和日志的 SHA-256。退出码 `0` 表示数据匹配，`2` 表示诊断失败，`3` 表示后端不可用；profile 或输出目录错误返回 `1`，命令行参数解析错误返回 `2`。典型失败原因包括 `negative_response`、`timeout`、`invalid_response`、`unexpected_response` 和 `data_mismatch`。

此入口使用精确 CAN ID filters，但不自动取得通道锁。实验期间保持 `vcan0` 上只有目标 ECU 和此诊断客户端使用这组 ID；报告中的 `isolation.channel_lock` 如实记录锁状态。`target` 是调用方声明，数据匹配不验证 ECU 身份。超时也不能单独定位到某个 BSW 模块。

自动回归通过独立的 virtual ISO-TP peer 覆盖多帧成功、数据不符、NRC、短响应、错误 DID、无响应和错误响应 CAN ID。该测试 peer 只存在于测试中；`--interface virtual` 仍要求调用方另行提供同进程的 virtual ECU。

2026-09-12 留存的 OpenBSW 实测结果位于 `output/upgrade-20260912/openbsw-live/`，观察到 `22CF01`、`62CF01` 和 SF/FF/FC/CF 完整链路。该目录是本机证据，不随 Git 分发。
