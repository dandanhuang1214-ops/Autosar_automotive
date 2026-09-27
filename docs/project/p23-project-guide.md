# P23：独立 ECU 纳入项目验收

项目/报告 0.5 已实现，本轮远端待验收。旧项目 0.1–0.4、手动 DID 客户端和独立执行入口保持兼容；固定构建与 Linux 运行环境准备见 [执行指南](p23-external-ecu-guide.md)。

## 一次项目运行包含什么

0.5 在 0.4 输入基础上新增 `inputs.execution`，引用构建绑定的外部执行声明。原始 execution/build/profile、关键构建来源和实际 runner 输入一并快照。先校验全部输入和 backend/channel；静态 canonical、mapping、ARXML 或可选 generation 门失败时，声明式通信和外部 ECU 均跳过。构建文件缺失属于环境 blocked，不伪造诊断结果。

静态门通过后，项目顺序执行两个独立阶段：

| 阶段 | 实际执行与证据范围 |
|---|---|
| `communication` | 按 DBC/intent/vectors 在所选通道运行本机声明式双端通信，保存路径绑定 |
| `external_ecu` | 使用固定 ELF 和独立进程读取 CF01，保存生命周期、诊断帧与清理记录 |

两阶段共享项目验收，但没有被证明的 DBC/SWC → OpenBSW 内部映射；报告和审查都保留这个边界。声明式通信失败不隐藏独立 ECU 诊断结果，两阶段结果都会进入项目总状态。外部执行器持其自身的通道锁，锁范围为该阶段，不声称整个项目事务持锁。

## 运行、审查、比较

先用构建脚本生成 `output/p23-build/build.json`，并恢复 vcan0。公开样例引用该位置；所有输出目录须为空或不存在。

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli run-project \
  examples/window_control/project-external.json \
  --interface socketcan --channel vcan0 --output output/p23-project
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli run-project-review \
  output/p23-project/bundle/project-report.json --output output/p23-project/review
PYTHONPATH=src .venv/bin/python -m automotive_workbench.cli compare-projects \
  output/p23-project/bundle/project-report.json \
  output/p23-project/bundle/project-report.json --output output/p23-project/compare
```

打开 `output/p23-project/bundle/index.html` 查看项目验收。`external-ecu.json` 提供稳定的 `/status`、`/reason`、`/source_commit`、`/diagnostic/actual_data_hex` 等验收 locator；详细进程/帧信息在 `external-ecu/`。未执行的诊断为 null，不能当作空响应或成功结果。

0.5 要求显式选择与构建声明一致的 classic SocketCAN/channel，默认 virtual 会在创建输出前拒绝；不会因运行旧项目而启动外部应用。当前实际构建限定 vcan0。另一个客户端通道须与实际构建一致，不能只改 CLI channel。

审查会先复验完整输入/运行来源、静态门、外部执行摘要、诊断绑定与验收值，再生成引用；修改阶段摘要并重算库存 hash 仍会被来源重算拒绝。它可以说明观察到的失败原因和 NRC，不据超时推断某个 BSW 模块故障，也不接受物理 ECU 成功等越界声明。

项目比较继续使用 comparison 0.2，新增固定构建内容、执行条件和诊断 profile 的比较依据。相同输入/定义可比较状态回归；切换 fault、launch_ecu、profile、构建或验收定义后为 `not-comparable`，不能把不同实验条件直接当成同一次配置回归。输入路径移动本身不改变比较依据。

## 重放和迁移

```bash
# 双平台 CI 使用：明确是离线 blocked/拒绝/静态失败证据
PYTHONPATH=src .venv/bin/python scripts/run_external_project_scenarios.py \
  --output output/p23-project-offline
# Linux 实际固定 OpenBSW：正常项目及真实诊断失败
PYTHONPATH=src .venv/bin/python scripts/run_external_project_scenarios.py \
  --build output/p23-build/build.json --output output/p23-project-live
```

现场脚本覆盖正常、静态失败、验收条件变化、未声明 ID 漂移、通道漂移、无响应、错误 DID 和错误响应 ID。移除生成的源输入并移动结果目录后，复验 manifest、原审查引用、重新审查与比较。迁移验证不启动 ECU、不访问原构建路径；执行二进制仍只记录 hash，不随证据包发布。

退出码保持：通过 0、项目失败 2、环境 blocked 3、非法配置 1。项目 schema 负责结构，loader 负责跨文件语义和可执行条件；引用、来源 hash 与比较依据属于不同检查，不能用一个成功结果代替全部检查。
