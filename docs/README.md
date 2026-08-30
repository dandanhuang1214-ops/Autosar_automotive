# Workbench 文档导航

## 项目管理

- [平台升级进度账本](project/progress-log.md)：每次升级必须更新的唯一状态源。
- [中长期路线](project/roadmap.md)：平台阶段、边界和里程碑。
- [Windows/WSL 双平面决策](project/windows-wsl-platform-decision.md)：开发环境职责划分。
- [Git 项目管理常用指令与用法](project/git-workflow-cheatsheet.md)：提交、分支、远端同步、冲突和回滚速查。

## 环境与学习

- [WSL/SocketCAN 分阶段记录](learning/wsl-socketcan-stage-b.md)
- [SocketCAN 操作说明](socketcan-wsl.md)
- [OpenBSW spike 说明](openbsw-spike.md)

## 技术调研

- [CAN 运行时、日志和回放](research/can-runtime-log-replay-research-2026-08-14.md)
- [SocketCAN R2 调研](research/socketcan-r2-research-2026-08-14.md)
- [OpenBSW POSIX spike 调研](research/openbsw-posix-spike-research-2026-08-16.md)
- [OpenBSW R3 readiness](research/openbsw-r3-readiness-2026-08-17.md)
- [OpenBSW R3 POSIX spike](research/openbsw-r3-posix-spike-2026-08-17.md)
- [UDS/ISO-TP R4 架构调研](research/uds-isotp-architecture-research-2026-08-18.md)
- [DTC operation-cycle/aging/snapshot R4k 调研](research/dtc-operation-cycle-aging-snapshot-research-2026-08-20.md)
- [DTC extended data/negative scenarios R4l 调研](research/dtc-extended-data-negative-scenarios-research-2026-08-20.md)
- [DTC reset/persistence R4m 调研](research/dtc-reset-persistence-research-2026-08-20.md)
- [DTC persistence integrity faults R4n 调研](research/dtc-persistence-integrity-fault-research-2026-08-20.md)
- [DTC redundant mirror/generation R4o 调研](research/dtc-redundant-mirror-generation-research-2026-08-20.md)

## 文档职责

- 本仓保存所有直接指导平台设计、开发、测试和运行环境的文档。
- `D:\work\improve` 继续保存职业路线、Sprint 学习记录、面试题、复盘和项目证据索引。
- 平台代码升级必须同步更新 `project/progress-log.md`；路线改变再更新 `project/roadmap.md`。
