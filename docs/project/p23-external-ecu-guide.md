# P23 独立 ECU 执行底座

当前 P23 implementing。本轮交付固定构建、独立进程执行与现场故障证据；统一 `run-project` 快照/验收/审查接入仍待实现。P22 公开路径冻结保持，商业工具往返仍 blocked。

## 从干净构建到诊断报告

需要 Linux、CMake、Ninja、C/C++ 编译器及 Workbench 的 `diag` 依赖。使用独立干净 checkout，不改动已有 OpenBSW 工作树。构建脚本只接受已审计基线 `dbd6e118a9aaa2db36e4461ce76655e8f285598d`，检查构建前后工作树状态，运行真实 configure 和 clean-first Release build；固定源的通道/寻址/CF01 值来自该提交，暂不支持其他版本或通道的自动推导。

```bash
git clone https://github.com/eclipse-openbsw/openbsw.git /tmp/p23-openbsw
git -C /tmp/p23-openbsw checkout --detach dbd6e118a9aaa2db36e4461ce76655e8f285598d
.venv/bin/python scripts/build_openbsw_execution.py \
  --source /tmp/p23-openbsw --output output/p23-build
bash scripts/linux/setup_vcan.sh --apply
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli run-external-ecu \
  examples/openbsw/execution.json --output output/p23-run
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli verify-external-ecu \
  output/p23-run/external-ecu-report.json
```

输出目录须不存在或为空；构建和场景脚本要求不存在。构建输出保存命令日志、工具版本、commit、ELF/CMake cache/三份关键源码 hash，以及 `build.json`、`profile.json`、`execution.json`。执行声明与构建记录分别有版本化 closed schema；除了结构检查，loader 还检查唯一角色、文件 hash、时限和客户端/构建的 channel、请求/响应 ID、DID、期望数据一致性。schema 不能替代这些跨文件检查。

执行器先校验输入，再取得与既有 Linux 脚本一致的 SocketCAN 通道锁，探测依赖/接口并启动 ECU。客户端使用另一个 Python 进程，仍只调用既有 `read-uds-did`。启动延迟是有界等待，不代表 ECU ready；只有实际 CF01 返回值才能证明本次请求成功。客户端总等待预算为 profile timeout 加 5 秒；ECU 和客户端分别进入本次创建的进程组，TERM 后必要时 KILL，报告记录 PID、退出码及父进程 reap 结果，不清理用户预先启动的 ECU。

报告包含输入与构建来源快照、后端 probe、原始 ECU/client 日志、诊断报告和 CAN log。构建 ELF 只保存 hash，不复制进执行证据包。`lock=held` 表示执行期间持锁，调用结束后释放。共享锁只约束遵守同一锁约定的工具；总线上的其他程序仍可能产生帧，数据匹配不认证 ECU 身份。

`verify-external-ecu` 只读取迁移后的快照，检查文件库存/hash、构建来源/配置绑定和成功诊断/清理条件，不访问原构建路径、不执行 ELF、不重发请求；它证明保存的字节和声明一致，不认证来源或重新证明现场结果。输出根只存此执行的文件；新增/删除/篡改库存文件会拒绝验证。

退出码：成功 0、诊断/执行失败 2、环境或通道锁 blocked 3、配置/来源不合法 1。Windows 保留输入检查和 blocked 报告，外部执行仅支持 Linux SocketCAN。旧 `read-uds-did`、project 0.1–0.4 与 virtual runner 不变。

## 故障及迁移验收

```bash
PYTHONPATH=src .venv/bin/python scripts/run_external_ecu_scenarios.py \
  --build output/p23-build/build.json --output output/p23-live
# 不需要 ECU、CAN 或 Linux 的 CI 离线路径：
PYTHONPATH=src .venv/bin/python scripts/run_external_ecu_scenarios.py \
  --output output/p23-offline
```

真实路径依次执行正常读取、`launch_ecu=false` 的无响应、显式 `fault=wrong-did`、`fault=wrong-response-id` 和锁冲突；故障仅修改客户端，不声称 OpenBSW 有缺陷。未声明 fault 的 ID/DID 漂移在开总线前拒绝。无响应场景要求现场没有其他 ECU 使用同组 ID，否则脚本应失败，不把外部响应隐去。

场景删除自己生成的变体输入并移动结果目录后，对全部报告离线复验。CI 默认只运行合成缺失构建的 blocked、未声明漂移拒绝和迁移，证据标注 `synthetic-offline-rejection-only`；它不能代替真实构建和现场 ECU。

12 组专项回归覆盖来源/声明非法与无副作用、schema、快照篡改、缺失二进制、锁隔离、进程早退、客户端启动失败、客户端总期限、实际 SIGTERM、中断和 KILL 升级等。测试中的进程替身、mock probe 与既有 virtual ISO-TP peer 均不计作 OpenBSW 现场证据。

## 后续阶段门

下一步将已验证执行底座接入版本化项目：定义执行输入与验收 locator，绑定项目快照、运行报告与审查引用，保留静态门控及旧项目兼容；随后完成整阶段交付。当前固定构建只支持 vcan0，不把另一个锁名的互斥测试当成不同通道的 ECU 运行。项目集成、其他通道构建及整阶段远端冻结均不能由本轮运行底座验收替代。
