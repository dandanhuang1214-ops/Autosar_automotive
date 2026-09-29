# P25 可复现交付计划

状态 implementing（2026-09-29），当前主阶段。P24 已通过 run `36451604309` 七 job 验收；本计划不代表 P25 实现或交付验收已完成。

目标：从干净环境完成两个公开项目的安装、运行、配置变化、失败审查和证据交付，使 10 分钟演示中的每项结论都有可定位证据。

## 既有入口与缺口

- P13 已有 wheel 隔离安装/console trace；P14 已有仓库外安装后的 capsule 验证。继续复用，不能把仅 trace 成功等同于安装后完整项目可运行。
- P20–P24 已有两项目、对象图/影响、XML、独立 ECU 和审查评测。现有脚本常依赖 checkout 中的样例与脚本，需明确发行物、样例包、可选依赖和工作目录边界。
- 七 job CI 已包含 Windows/Ubuntu 与 Python 3.14；新增交付门应维持职责拓扑并提供独立 artifact，而非复制执行内核。

## 下一项与验收顺序

1. **安装后多项目竖切**：干净 venv 安装 wheel 和所需可选依赖，从 checkout 外调用 `workbench`，运行车窗与 ThermalControl，执行一种真实配置失败、影响比较、审查和引用复验。清除 PYTHONPATH/PYTHONHOME 并断言导入来自已安装包；保存 wheel、Python、依赖和输入版本/hash。
2. **可复制入口**：给出 Windows PowerShell 与 Linux 安装/执行手册、英文 README 和样例包准备入口；将有条件的 SocketCAN/OpenBSW 现场路径与默认 virtual 演示分开。
3. **10 分钟演示**：以“改动 → 影响对象/验收项 → 真实失败 → 审查引用 → 迁移复验”为顺序，固定命令、输入、输出与耗时观测。时间窗口是演示目标，实际测量前不宣称已达成。
4. **能力—证据对应**：分别整理工具链/配置自动化与 BSW 跨层定位的项目证据；不能将平台自动实现等同于个人源码讲解或协议实操已掌握。
5. **完整交付验收**：干净环境两项目与故障、安装后核心路径、最新实现七 job 和归档同时通过。真实外部使用/投递反馈单列，尚未取得就保留未满足门，不用代理自测代替反馈。

不新增协议栈、分布式服务或模型供应商；不自动发布包、向其他项目开 issue/PR 或联系他人。商业工具/物理 ECU 仍需各自真实环境和执行证据。

## 本轮实现状态

安装后双项目与配置故障/影响/审查/迁移完整流程已本地通过，自动流程耗时 40.799 秒（含本次依赖准备，不等同人工十分钟演示）。新入口 `scripts/check_installed_projects.py`、[Windows/Linux 指南](p25-installed-delivery-guide.md)和[英文入口](../../README.en.md)已提供；实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a` / [run `36586481411`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36586481411) 七 job 全部 success；Windows/Ubuntu 的安装后双项目验证及完整归档上传均 success。完整 P25 仍需人工演示、能力证据整理及真实外部反馈，不标记整阶段完成。

已整理[能力证据对应](p25-capability-evidence.md)和[演示脚本](p25-demo-runbook.md)，人工实测与真实外部反馈仍未取得。全量 307 tests：305 passed、2 环境跳过；归档依赖离线复跑 24.905 秒通过。本轮实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a` 已推送，远端 run `36586481411` 七 job 全部 success。

本轮验收与剩余门见[P25 验收记录](p25-acceptance.md)。下一项为真实操作者人工演示记录与实际外部反馈，不用自动流程耗时代替讲解或外部使用。
