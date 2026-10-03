# P29 配置与运行证据关联验收

更新：2026-10-03。P29 implementing；本轮 CAN 关联门 local-accepted，等待本实现远端 CI。独立 ECU 诊断关联仍是同阶段下一门，不将 CAN 端点误称为外部 ECU。

| 阶段门 | 本轮状态与证据 |
|---|---|
| 版本与兼容 | 项目/报告 0.8，ECUC 阶段 0.3，带上下文 CAN 观测 0.2；旧 0.1–0.7 保持 |
| 显式身份 | 保护策略、精确信号、PduR/CanIf 路径、向量、方向、CAN ID 与候选地址绑定；未知不执行 |
| 双工程 | 完整 Tx/Rx/应用/任务/模式工程与精简单 Tx；同一内核运行 |
| 静态门控与失败 | 静态拒绝、错误映射/地址不开总线；virtual timeout/wrong-ID 测试 harness；实际后端 blocked |
| 同次与便携证据 | 原始输入/候选/策略/执行上下文、工具版本；9 份运行、审查、回归比较、五类篡改拒绝与重复搬移 |
| 安装 | 仓库外 wheel + CAN 依赖通过，checkout import 排除；本地复用已有 wheelhouse，完整 9 场景/5 拒绝与复制后复验通过 |
| 本地回归 | 385 tests：383 passed、2 环境跳过；11 项新增运行关联测试；53 schema、71 bound/25 syntax-only、52-source mypy、Ruff、topology、compileall、pip check 通过 |
| Linux SocketCAN | vcan0 两工程通过；完整工程 Tx/Rx 2/2、单 Tx 1/1，通道锁已持有；最终代码离线复验通过，比较引用分别 50/50 与 22/22 |
| Windows/Ubuntu | 待固定实现的七 job、新场景/安装/上传结果 |
| 独立 ECU 诊断关联 | planned；下一任务冻结 P23 执行身份/配置策略映射与未支持范围，不沿用历史 CF01 结果 |

证据目录 `output/p29-validation/`，运行指南：[P29 同次 CAN 关联](p29-runtime-link-guide.md)。本轮不标记 P29 整阶段完成；P25 人工演示/反馈、厂商生成与物理 ECU 验收保持独立。

最终本地证据：`scenarios-release/summary.json`、`installed-release/summary.json`、`socketcan/summary.json`、`tests-release.log`，均位于 `output/p29-validation/`。源码流程搬出临时目录并删除原树后，项目与比较再次复验通过（50/50 引用）。
