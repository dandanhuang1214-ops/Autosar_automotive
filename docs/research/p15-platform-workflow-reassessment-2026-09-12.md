# P15 平台目标复核与项目工作流升级

日期：2026-09-12。依据：仓库实现、P0–P14 进度、路线与用户本次明确纠正。学习进度不作为平台里程碑选择依据。

## 判断

“统一工程体验、分离工具内核、通过 artifact 连接 Windows 工程面和 Linux 执行面”的目标仍合理。现有 CAN/UDS/DTC、映射校验、review 和 evidence 能力可以复用，个人维护也不需要立即承担完整 AUTOSAR BSW 或商业工具链的成本。

需要调整的是升级排序。P10 的质量缺口已补齐，P12–P14 又完成 CI 拆分及安装后消费验证；继续只增加证据封装层，难以改善工程人员从输入到结论的操作。9 月 10 日审计提出的短期质量优先策略已经兑现，应回到平台工作流。最新 README 的 37 项能力包含未提交 CF01 功能，不能据此声称统一平台已经交付。

| 原目标 | 实际状态 | 本次判断 |
|---|---|---|
| DBC、canonical、BSW intent 静态关系 | 已有 adapter 和公开样例 | 保留并整合 |
| CAN/UDS/DTC 可重复运行 | virtual、SocketCAN 与大量故障实验已实现 | 能力足够支撑当前工作流，暂缓协议扩张 |
| 统一体验 | CLI 命令分散；P7 只串通信交付，未包含 canonical 和声明验收项 | 当前主要缺口 |
| 工程证据与审查 | P5–P14、R5 基础较完整 | 作为工作流底座复用 |
| 真实工程输入桥接 | Generate-Arxml issue/canonical adapter 已有，自动导出和真实往返尚不足 | 下一阶段应以明确导出产物驱动 |
| AI 辅助定位 | 当前是词法检索、断言与引用 | 不能称为通用语义诊断；后续使用真实失败报告评测 |
| 六个月路线 | 历史周计划与已完成阶段混排 | 改用能力验收门，不把日历或学习周次当工程完成条件 |

## 调研与方案选择

1. ASAM XIL 的核心方向是解耦测试逻辑与实际/虚拟测试系统，并提供抽象映射。Workbench 已有 BusConfig 与分层 adapter，可以沿用这种分离原则；本次不实现也不声称符合 XIL 标准。[ASAM XIL 官方说明](https://www.asam.net/standards/detail/xil/)
2. Eclipse openDuT 当前的执行模型涉及 peer、Docker/Podman 测试容器和 WebDAV 结果上传。单机 Windows/WSL 尚无多 DUT 调度需求；现在引入会增加运维面，不能直接解决项目验收入口问题。[openDuT Test Execution](https://opendut.eclipse.dev/book/user-manual/test-execution.html)
3. StrictDoc 支持以文本管理需求、关联需求和源码，并导出 HTML、ReqIF 等。需求 ID、显式关系与可阅读报告值得借鉴；当前只有公开车窗的几项验收条件，先保留轻量 JSON。出现实际 ReqIF/需求库交换需要时再做 adapter。[StrictDoc User Guide](https://strictdoc.readthedocs.io/en/stable/stable/docs/strictdoc_01_user_guide.html)
4. OpenBSW 官方诊断能力与寻址受构建选项控制。新增某个 DID 客户端是独立 ECU 接入的一步，但无法代表跨工具平台整合，既有 CF01 profile 也不能直接假定适用于所有上游构建。[OpenBSW Diagnostics](https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/features/diagnostics.html)

以上是资料事实；下面的取舍是结合本项目状态作出的工程判断。

| 方案 | 当前收益 | 代价/前置条件 | 决定 |
|---|---|---|---|
| 项目文件 + 统一执行 + 验收矩阵 | 一条命令完成配置到结论，直接用于日常修改和演示 | 复用已有运行内核，新增薄编排层 | 本次实施 |
| OpenBSW/商业工具深度接入 | 提高真实集成证据 | 需固定构建、输入与工具可用性 | 下一实际输入任务再做 |
| 引入通用 LLM 助手 | 改善自然语言解释 | 需要真实失败集、模型依赖和质量评测 | 先建立项目级失败证据 |
| openDuT 或完整需求管理平台 | 远程执行、需求协作与交换 | 多机、容器或需求库运维 | 暂缓，保留 adapter 方向 |

适合当前用户的方式是“先形成一条可使用的工程工作流，再沿实际输入扩展”。保持单机可复现、无需额外服务；用已有专业组件，不另造 CAN/UDS 内核。

## 本次实施

新增 `workbench-project-0.1` 与 `run-project`：

```text
project.json：输入路径 + 验收 ID/文本/证据位置/期望值
  → 固化本次输入副本
  → canonical/DBC 校验 + DBC/BSW intent 校验
  → 静态通过后运行既有 communication chain
  → 逐条验收并绑定报告 SHA-256 / JSON Pointer
  → HTML + JSON 项目报告
  → 复用既有 manifest / verifier
```

- 输入路径相对于项目文件，运行使用本次输入快照，后续修改原件不会污染报告。
- 只开放 canonical、mapping、communication 三个已有阶段；项目文件不能执行 shell 或任意 Python。
- 保留底层完整 findings；任一阶段失败会使项目失败，不能通过挑选少量通过的验收项掩盖错误。
- 静态失败时通信阶段 skipped，对应验收项 blocked；后端不可用时项目 blocked；缺失 pointer 为 failed。
- 验收项是调用方明确声明的可观测条件，不将 5/5 外推为完整车窗功能、完整需求覆盖或量产合格。
- 不自动取得 SocketCAN 通道锁，virtual 为默认路径；共享通道仍需使用既有隔离纪律。
- HTML 是直接打开的静态文件，正文转义，不引入 Web 服务、数据库或前端构建链。
- 原 CF01 与 cantools 升级保留为先前未提交工作，不把它们计为 P15 的平台目标。

## 验收与回退

公开样例须跑通 5 项声明验收；负例须覆盖 scale 配置错误停止运行、后端不可用、证据不存在、布尔/数字混淆、非法项目和非空输出保护；迁移整个输出目录并移除原输入后仍可复验，篡改快照须被检出。

CI 在既有 runtime-evidence 中增加项目入口及整个结果目录上传；负例由核心回归负责，保持四类 job、七个实际 job 的结构。远端结果必须另行记录，不用本地成功替代 Windows/Python 3.14 验收。

回退可以停止使用 `run-project`，继续调用原有命令。新增编排不修改现有输入和旧报告契约；运行结果写入新目录。

## 接下来两步

- P16：用一个明确 Generate-Arxml 导出产物替换公开 fixture，建立版本、配置变化到项目验收失败的真实案例；以可重放产物开始，不先整合两个仓库或引入商业工具依赖。
- P17：在实际项目正常/失败报告上增加面向工程问题的审查入口，复用既有引用与拒答机制，再决定是否增加 LLM 解释。每一阶段都要求可运行命令、失败案例与可阅读报告。

功能进度与实测结果以 `docs/project/progress-log.md` 的 P15 记录为准。
