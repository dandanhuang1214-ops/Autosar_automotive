# P23 验收记录

更新：2026-09-27。当前主阶段 implementing；本轮独立执行底座 remote-accepted：实现 `320defd6b23d22800520b7434bd0ae739164e6ce` / [run `36323420799`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36323420799) 七 job 全部 success。项目统一接入未完成，不标记整阶段完成。

| 阶段门 | 实际证据 | 状态 |
|---|---|---|
| 固定干净构建及绑定 | `/tmp/workbench-p23-openbsw` 固定 dbd6e118；真实 configure、379-action Release build；源码/cache/ELF hash | 本地通过 |
| 独立 ECU 与 CF01 | 实际 ECU/client 两进程、24 字节一致、SF/FF/FC/CF、退出及清理记录 | 本地通过 |
| 无响应、错误 DID/ID | 未启动 ECU → timeout；CFFF → negative_response；响应 ID 0x0F1 → timeout | 本地通过 |
| 环境 blocked 与隔离 | 缺失构建离线 blocked；现场同通道锁冲突无进程启动；单测不同锁名 | 本地通过；不同通道 ECU 尚未验收 |
| 超时/异常/信号清理 | 客户端期限、早退/部分启动、实际 SIGTERM、强制 KILL 回归 | 本地通过（编排替身） |
| 快照与迁移 | 移除变体输入、移动目录后 5/5 现场报告复验；离线合成 1/1 | 本地通过 |
| 七 job CI | 两平台离线场景/上传 success，Linux 生命周期测试与 Windows blocked 回归通过 | remote-accepted |
| 统一项目快照/验收/审查 | 待接入版本化项目；不替换既有 0.1–0.4 | 待实现 |

本地证据：`output/p23-validation/build/`、`live-scenarios/`、`offline/`、`tests-final/`。构建与现场日志为本机证据，不提交 Git；CI 上传离线证据，明确不等同现场运行。

现场报告 SHA-256：

| 场景 | SHA-256 |
|---|---|
| normal | `1a7d78293108ce17ed43f53e6babc622b685b1be28ba6c08e62e3775e173a8b6` |
| no-response | `1b036ca8a852c5f5f7066f28cefdd44f620179864f86d8a380dcff4b27706ea4` |
| wrong-did | `64d6b2a797f310085ddb272888216c2e0e70a3074c030a92846d0fd1cb216716` |
| wrong-response-id | `839c3eaea9b7749cdae18f17fc07135a7830cd94b61654ef80c9aa48c76c9c90` |
| lock-busy | `ba068bb66462ad99a0f79869a545c402b06d57973e51cb3ab6ab6063f0644f09` |

ELF、构建 provenance 及每份报告的输入 inventory 保存独立 hash。哈希绑定不认证 ECU 身份。范围为 Linux POSIX/vcan，非物理 ECU/量产 BSW；商业工具往返仍 blocked，个人学习掌握另行验收。复跑入口见 [执行指南](p23-external-ecu-guide.md)。
