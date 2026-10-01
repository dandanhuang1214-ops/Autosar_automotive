# P26 ECUC 体检首轮验收

更新：2026-10-01。P26 整阶段 implementing；本表仅覆盖项目感知只读体检，该门 remote-accepted。

| 验收门 | 证据与结果 |
|---|---|
| 项目选择与范围 | DPA/collection 选择活动模块；未选模块不误报、外部引用 unassessed |
| 公开失败场景 | 正常、未绑定、断引用、歧义四场景通过；仅使用合成工程 |
| 可移植复验 | 删除原输入后四组快照复验通过，报告/来源/库存篡改拒绝 |
| 本地回归 | 316 tests：314 passed、2 环境跳过；ECUC 定向 9/9 |
| 质量门 | 48 schemas、61 bound examples、25 syntax-only；Ruff、39-source mypy、topology、pip check 通过 |
| P24 兼容 | 原冻结记录不改，严格 0.1 输出保留；当前 0.2 历史回归 30 题及 12 负例/迁移通过，不声称新独立负例 |
| 双平台 CI | `c6320d5` / [run `36813404620`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36813404620) 七 job 全部 success；Windows/Ubuntu ECUC 场景和上传均 success |

本地证据：`output/p26-validation-20261001/`。首轮 `84b5469` / run `36742954252` Windows 因新增测试未指定 UTF-8 失败，Ubuntu/Python 3.14 成功，下游跳过；该 run 不作为验收依据。

下一项为根据真实 VALUE-REF 连接 Com → EcuC/PduR → CanIf → Can，明确方向、组信号、扩展与未知引用；尚未宣称该链实现。P25 人工演示/真实反馈、商业工具生成和物理 ECU 验证保持原有未验收边界。

验收实现完整 SHA：`c6320d503d3d704bdce5d64e294dc84811444e0c`。job/step 原始记录 `output/p26-validation-20261001/remote-ci.json`；各 job ID 见[进度账本](progress-log.md)。本表为后续纯文档回填，不把文档提交当作新实现验证。
