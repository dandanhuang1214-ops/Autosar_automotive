# P25 可复现交付验收

更新：2026-09-29。整阶段 implementing；本轮安装后双项目流程 **remote-accepted**。实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a` / [run `36586481411`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36586481411) 七 job 全部 success；Windows/Ubuntu 的安装后双项目验证及完整归档上传均 success。

| 验收门 | 实际记录 | 状态 |
|---|---|---|
| 干净 venv 安装后双项目 | 两项目 passed；安装来源与 prefix 校验；pip check；运行目录在 checkout 外 | 本地及双平台 CI 通过 |
| 真实配置故障与影响 | DBC 缩放变化，故障项目 failed/通信 skipped；thermal-status 受影响；项目比较 regressed | 本地及双平台 CI 通过 |
| 迁移后证据与审查 | 原目录不存在；三组项目库存和引用、配置影响、比较、工程答案独立复验 | 本地及双平台 CI 通过 |
| 离线依赖重用 | 同平台 wheelhouse、`--no-index` 安装；归档 wheel/输入/运行依赖/hash | 本地及双平台 CI 通过 |
| 安装/英文入口 | Windows/Linux 操作指南、英文 README、可移出的最小样例包 | 已提供，双平台实际执行通过 |
| CI 和完整归档 | 实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a`；run `36586481411` | remote-accepted |
| 能力与证据对应 | 工具链/配置自动化、BSW 对象影响及已有现场证据分别说明 | 已提供；不表示个人已掌握 |
| 十分钟人工演示 | 演示顺序与记录模板已提供，未实际录制或人工计时 | 待完成 |
| 真实外部反馈 | 没有外部使用/投递反馈，不用代理自测冒充 | 待取得 |

本地证据：`output/p25-installed-network/summary.json`（40.799 秒）；`output/p25-installed-offline/summary.json`（24.905 秒）；各归档含 85 个 portable 文件和完整命令记录。自动流程耗时不等于人工演示耗时。

全量 307 tests：305 passed、2 环境跳过。新增四个保护测试和既有 topology 测试通过；47 schema、61 schema-bound examples、25 syntax-only examples、Ruff、新脚本默认/Windows-target mypy、topology 与 whitespace 检查通过。P24 冻结的运行源码、评分器和 gold 未修改。

复跑入口见[交付指南](p25-installed-delivery-guide.md)，能力说明见[证据表](p25-capability-evidence.md)，未完成的人工验收见[演示记录模板](p25-demo-runbook.md)。本轮默认 virtual CAN，不新增现场 OpenBSW、物理 ECU、商业工具或身份认证声明。

实际远端记录：`output/p25-validation/remote-ci.json`。状态回填为后续纯文档 `[skip ci]` 提交，不作为另一次实现验收。下一项：按演示脚本完成操作者实际计时/讲解记录，并在取得真实外部使用或投递反馈后形成下一轮问题清单；未取得前保持 P25 implementing。
