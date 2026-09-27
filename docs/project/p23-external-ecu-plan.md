# P23 独立 ECU 项目执行接入计划

更新：2026-09-27。状态 planned；P22 公开路径已远端冻结，商业往返 blocked 单列。本文规定下一实现入口，不是 P23 验收证据。

## 可复用入口与现场事实

- `src/automotive_workbench/uds_client.py` 的 `read_uds_did` 已支持单次只读 0x22、精确 ID filters、SF/FF/FC/CF、超时与报告；不在客户端内启动 responder。
- `examples/openbsw/read_cf01.json` 固定历史基线 `dbd6e118a9aaa2db36e4461ce76655e8f285598d`、请求 0x02A、响应 0x0F0、DID CF01 与 24 字节期望值。新执行必须将这些声明和实际构建绑定，不能只相信 target 文本。
- 本机 `/home/dev/work/openbsw` HEAD 与该基线相同；`CANFrameTest.cpp` 有既存修改，必须保留。Release ELF 存在；CMake cache 为 Ninja Multi-Config、Debug/Release、`/usr/bin/c++`。仅凭旧 ELF 与 cache 存在不能证明当前源码与二进制对应。
- 源码 `CanSystem.cpp` 配置 vcan0，`DoCanSystem.cpp` 配置 0x02A/0x0F0，`UdsSystem.cpp` 注册 CF01。本次权限外只读 netlink 查询确认 vcan0 不存在；先用既有 `scripts/linux/setup_vcan.sh --apply` 恢复，再运行现场门。

## 实现顺序

1. 固定干净 OpenBSW checkout 和 POSIX 构建，记录 commit、构建命令、编译器/生成器版本、配置和 ELF SHA-256；保留源码中寻址、通道和 DID 定义的路径与 hash。不要改写有用户修改的旧 checkout。
2. 增加版本化外部 ECU 执行声明及闭合报告：绑定构建证据、DID profile、channel、启动参数和有界启动/执行/清理时间。预检验证全部来源与 hash；非法输入在启动进程或开总线之前拒绝。外部进程仅通过显式参数数组启动，不使用 shell 字符串。
3. 编排器复用 SocketCAN 通道锁命名，在锁内预检、启动独立 ECU、调用既有客户端并清理自己创建的进程。启动退出、超时、客户端异常均保留日志和终止结果；不得杀死用户预先启动的进程。进程存活不等同诊断 ready，必须保留实际请求结果。
4. 经版本化项目入口接入输入快照、静态门控、诊断结果、验收 locator、审查/迁移复验；保持 project 0.1–0.4 及 `read-uds-did` 兼容。普通 virtual 项目不因新增外部执行配置而启动 ECU。
5. 完成故障场景、本地现场门和七 job 远端回归，按实现 commit/run/job 回填验收。CI 的进程替身与 virtual transport 只证明编排回归；真实 OpenBSW 现场证据单列。

## 必须交付的验收门

| 场景 | 必须保留的证据 |
|---|---|
| 固定构建 CF01 成功 | ELF/构建/profile hash、独立 PID、实际 SF/FF/FC/CF、24 字节匹配、退出与清理结果 |
| 无响应 | 不启动目标 ECU 的明确条件、真实请求与有界 timeout；不伪造响应 |
| 错误 DID | 显式变体、实际 NRC 或其他实际结果；不能预填期望结论 |
| 错误响应 ID | 显式变体、精确 filters 与 timeout，原始观测单列 |
| 环境 blocked | 缺失接口/二进制/依赖或锁冲突的准确原因，没有运行观测时不得写成功 |
| 生命周期 | 早退、超时、中断/异常、部分启动后的清理，证明无自建进程遗留 |
| 隔离与迁移 | 同通道互斥、不同通道声明与实际构建一致；移除原输入后可复验已保存证据 |
| 项目及远端 | 快照/报告/审查来源一致，旧项目兼容；固定实现七 job 全绿，现场结论不由 CI 替代 |

固定源码当前使用 vcan0，不能仅更改客户端 channel 就声称完成不同通道运行；支持不同通道须有对应构建或实际配置入口。构建来源绑定证明可追溯执行条件，不认证 ECU 身份。范围保持 Linux POSIX/SocketCAN/只读 CF01，不声称物理 ECU、商业 ECUC 或个人 BSW 熟练度。
