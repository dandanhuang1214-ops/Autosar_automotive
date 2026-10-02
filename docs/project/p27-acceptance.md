# P27 声明式 ECUC 配置变更验收

更新：2026-10-02。remote-accepted；本阶段声明式静态配置接受能力通过本实现验收，不沿用 P26 结论。下一主阶段 P28 planned。

| 阶段门 | 当前证据 |
|---|---|
| 版本与兼容 | 新 workbench-project/project-acceptance 0.6，旧 0.1–0.5 保留；比较新增 0.3 |
| 声明式运行 | 基线/候选输入、五类检查、四状态接受条件、冻结来源、项目报告和通用 manifest |
| 两种结构 | 完整集成 Tx/Rx/ASW/BSW/BswM；精简单 Tx/五模块，无需改内核 |
| 故障与边界 | 任务缺口、通信退化、未知字段、缺应用、重复身份、历史日志分别检查 |
| 审查与比较 | 精确断言、受影响对象、固定基线/策略比较，原输入移除与再次搬移复验 |
| 防篡改 | 项目/阶段/HTML/来源/库存单测；CLI 结论/来源/策略/库存四类拒绝 |
| 本地完整检查 | 359 tests：357 passed、2 环境跳过；15 项专项；52 schema/63 bound/25 syntax-only、49-source mypy、Ruff、topology、pip check 通过；隔离 wheel 八场景/8 复验/8 审查/4 拒绝/比较和二次搬移通过 |
| Windows/Ubuntu | 实现 `55e208fffe6d51c233ff30d3604bafd992dfb080` / [run `36901660485`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36901660485) 七 job 全部 success；双平台新场景/安装/上传三步骤均 success |

证据目录 `output/p27-validation/`。开发中第一次场景和安装检查因审查断言不接受数组而失败，已改为逐条标量引用；最终复跑结论单独记录，不隐藏初次失败。

只验收声明的静态条件；未知/缺少输入不自动通过。商业工具生成、可调度性、物理 ECU、P25 人工演示与外部反馈仍未验收。完成本阶段后下一主阶段为 [P28 对象级配置变更验收策略](p28-object-acceptance-plan.md)，保持一个主阶段。

远端原始记录 `output/p27-validation/remote-ci.json`；job ID 见进度账本，双平台产物为 `ecuc-projects-Windows` / `ecuc-projects-Linux`。本验收回填为随后纯文档 `[skip ci]` 提交，不计作新的实现运行。
