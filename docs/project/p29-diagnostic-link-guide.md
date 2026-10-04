# P29 配置验收与独立诊断依赖

项目 0.9 在精确对象保护策略通过后，要求一次独立、只读的诊断执行。它复用 P23 的固定构建、独立 ECU/客户端进程、通道锁、超时与清理。项目 0.1–0.8 保持兼容；0.8 的 CAN 关联流程仍独立可用。

## 声明和判定

`diagnostic` 声明 `id`、`execution` 路径、已有 `policy_ids`、`relation` 与 `identity`。身份包含 source_commit、channel、request_id、response_id、did、expected_data_hex，必须与 P23 构建绑定一致；每个诊断依赖必须出现在 requirements 的 `/checks/diagnostic.<id>/status`，期望只能是 passed。

- `acceptance-dependency` 表示接受当前配置时还必须取得指定诊断证据。这不是配置到代码生成关系。
- `configuration-semantic` 当前没有 Dcm/CanTp 或生成来源支持，返回 unassessed，不启动进程。
- 静态条件未通过：诊断 blocked，保留 static_acceptance_rejected；静态失败仍使项目 failed。
- 声明身份无法对应：unassessed；执行后端/channel 不匹配：blocked；均不启动 ECU。
- 静态及身份通过后交给 P23 执行；实际 missing files、环境、超时、负响应和成功各自保留原因。

## 离线公开示例

```bash
python -m automotive_workbench.cli run-project examples/ecuc_diagnostic/integration.project.json --interface socketcan --channel p29-absent --output output/diagnostic-offline
python -m automotive_workbench.cli verify-ecuc-project output/diagnostic-offline/bundle/project-report.json
python -m automotive_workbench.cli run-project-review output/diagnostic-offline/bundle/project-report.json --output output/diagnostic-review
```

第一条预期退出 3：合成清单故意没有可执行文件。后两条验证和解释保存结果，不打开总线。transmitter.project.json 提供结构更简单的第二工程，复用同一内核。

完整离线案例、输入删除、二次搬移、审查、比较与篡改拒绝：

```bash
python scripts/run_ecuc_diagnostic_scenarios.py --output output/diagnostic-scenarios
python scripts/check_installed_ecuc.py --diagnostic-links --output output/diagnostic-installed
```

隔离安装路径使用无额外依赖的 wheel 验证离线 blocked/rejection；它不作为现场诊断的依赖安装或执行证据。

## Linux 独立进程现场路径

需要固定提交 `dbd6e118a9aaa2db36e4461ce76655e8f285598d` 的干净 OpenBSW checkout、CMake/Ninja/C++、Workbench diag 依赖及 vcan0。原始开发目录可以有用户修改，应在独立副本中构建。

```bash
python scripts/build_openbsw_execution.py --source /path/to/clean-openbsw --output output/diagnostic-build
bash scripts/linux/setup_vcan.sh --apply
python scripts/run_ecuc_diagnostic_scenarios.py --build output/diagnostic-build/build.json --output output/diagnostic-live
```

现场脚本把新构建身份显式填入两份合成项目，执行正常、静态拒绝、身份缺口、未支持语义、后端不匹配、无响应、错误 DID/响应 ID 和同配置重复运行。后续审查/搬移仍离线执行。错误寻址是 P23 明确记录的 fault variant，不是暗改正常构建身份。

独立执行器与诊断客户端分别记录同次上下文；新客户端报告为 uds-did-read-0.2，旧 0.1 保持。诊断上下文绑定项目声明、基线、候选、策略、执行输入及本次 run_id。比较基础还包含诊断声明、构建/profile/执行设置与后端；条件变化会判为不可比较，不强行声称运行回归。移除原输入不会阻碍复验，但重新执行仍需要原始或重新构建的可执行文件。

当前现场仅为本机 vcan0 上的独立 OpenBSW POSIX 进程。合成 ECUC 没有生成这个二进制；记录哈希也不是签名、远程身份认证或防止全部证据被整体伪造的机制。未取得物理 ECU、商业生成、可调度性或个人独立操作证据。

操作者练习见[配置与独立诊断证据](../learning/p29-diagnostic-dependency.md)。
