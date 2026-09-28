# P23 验收记录

更新：2026-09-28。实现 `3e4c29aba190f74cf0e17641af649892a37f415a` / [run `36331506323`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36331506323) 七 job 全部 success，Windows/Ubuntu 项目场景与上传均 success。P23 固定 POSIX/vcan0 范围 remote-accepted；现场证据沿用已记录的真实构建与诊断，不把远端离线验收当现场运行。

| 阶段门 | 实际证据 | 状态 |
|---|---|---|
| 固定干净构建及绑定 | `/tmp/workbench-p23-openbsw` 固定 dbd6e118；真实 configure、379-action Release build；源码/cache/ELF hash | 本地通过 |
| 独立 ECU 与 CF01 | 实际 ECU/client 两进程、24 字节一致、SF/FF/FC/CF、退出及清理记录 | 本地通过 |
| 无响应、错误 DID/ID | 未启动 ECU → timeout；CFFF → negative_response；响应 ID 0x0F1 → timeout | 本地通过 |
| 环境 blocked 与隔离 | 缺失构建离线 blocked；现场同通道锁冲突无进程启动；单测不同锁名 | 固定 vcan0 通过；不匹配通道在预检拒绝，其他通道构建不在已验证范围 |
| 超时/异常/信号清理 | 客户端期限、早退/部分启动、实际 SIGTERM、强制 KILL 回归 | 本地通过（编排替身） |
| 快照与迁移 | 移除变体输入、移动目录后 5/5 现场报告复验；离线合成 1/1 | 本地通过 |
| 七 job CI | 两平台离线场景/上传 success，Linux 生命周期测试与 Windows blocked 回归通过 | remote-accepted |
| 统一项目快照/验收/审查 | project/report 0.5；快照/静态门控/诊断/审查比较及迁移已通过；旧 0.1–0.4 兼容 | remote-accepted（3e4c29a / 36331506323） |

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

## 项目 0.5 整条路径（已远端冻结）

- 本地场景：正常项目 passed；canonical 静态失败使 communication/external_ecu 均 skipped；验收条件变化、无响应、错误 DID/响应 ID 为 failed；未声明 ID 漂移与通道漂移在创建输出前拒绝。
- 六份报告删除生成源输入、移动目录后，manifest、原引用、重审和比较均通过。正常自比较 stable、静态回归 regressed；改变执行条件或验收定义为 not-comparable，物理 ECU 越界声明拒答。
- `output/p23-project-validation/live/` 保存本机真实八案例，`offline-final/` 保存离线五案例及三份迁移报告；CI 两平台只运行离线 blocked/静态失败/拒绝/迁移，不能当作实际 OpenBSW 执行。
- 固定通道隔离由上一轮实际同通道锁冲突与本轮错误通道拒绝共同覆盖；启动/期限/中断/清理继续使用已验收执行内核。项目两个运行阶段各有证据范围，外部阶段持锁，不声称整个项目事务持锁。

| 现场项目报告 | SHA-256 |
|---|---|
| baseline | `67e9a0253facd579469f4f11815a2c0943e7fa3e4963e3c370d9e8391d1242dc` |
| changed-definition | `10b1aa7c5685a6adfb82b3dbcabee09bacad3b9d8f5e3af641888c2d324d3bea` |
| no-response | `a3df5a79d2770c5472b057eff6ad561d998478cfd4c64efa3bc7e1535d0c24ac` |
| static-failure | `362fbddbdb529502198b502264a469a8092f46f152f782f8dbe9bfec4af8c782` |
| wrong-did | `f43c730cddb81a0c13ba5757e8150e8d561ad1c1b7449f2f8037d54d2b48ac91` |
| wrong-response-id | `21b27cec9897bf0e4729412fa13a61723f9f3f0346a74022fa3458590b3dd417` |
