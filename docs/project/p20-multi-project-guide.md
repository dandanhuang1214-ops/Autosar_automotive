# P20：声明式多项目验收

同一 `run-project` 引擎支持公开车窗与 ThermalControl；新项目不修改 Python 内核。输入是 DBC、canonical contract、BSW intent、运行向量和项目 JSON。输出是可迁移的输入快照、阶段与验收报告、manifest、工程审查和基线比较。

## 从两个公开项目开始

安装项目及 CAN 依赖后运行：

```bash
python -m pip install -e ".[can]"
workbench run-project examples/window_control/project-declared.json --output output/window-project
workbench run-project examples/thermal_control/project.json --output output/thermal-project
workbench run-project-review output/thermal-project/bundle/project-report.json --output output/thermal-review
workbench compare-projects output/thermal-project/bundle/project-report.json output/thermal-project/bundle/project-report.json --output output/thermal-comparison
workbench verify-project-comparison output/thermal-comparison/project-comparison.json
```

默认 virtual 使用唯一通道；显式 `--channel` 可选固定通道。旧 `examples/window_control/project.json` 及 project 0.1/0.2 保持兼容。每个输出目录必须为空或不存在。

## 编写新项目

以 `examples/thermal_control/project.json` 为模板，使用 `workbench-project-0.3`：

- `inputs` 固定包含 `dbc`、`contract`、`intent`、`vectors` 四个文件路径，均相对于项目 JSON。
- `comparison_key` 是同一验收任务的稳定标识，例如 `thermal_control-communication-v1`。改变任务定义时应更换该标识。
- `requirements` 每项声明唯一 `id`、说明 `text`、`stage`、JSON Pointer 和标量 `expected`。通信结果使用向量 ID，例如 `/vectors/thermal-status/status`，避免依赖数组位置。
- 可选 `generation` 复用 project 0.2 的固定 Generate-Arxml 来源声明和门控；未声明时不能使用 generation 验收阶段。升级到 0.3 时同步修改通信验收 locator：原 `/runtime_status` 对应新绑定报告的 `/status`，或直接引用 `/vectors/<id>/status`；不能只替换版本号。

运行前从快照编译全部向量，确认映射路径有向量覆盖；非法向量、重复映射身份、不支持的 CAN 布局在开总线及写运行输出之前拒绝。静态 canonical/mapping/generation 失败会生成失败报告并跳过通信。运行使用已保存的快照，不重新读取原项目文件。

支持与拒绝的 CAN/DBC 特性、量化规则及 timeout 边界见 [通信声明说明](p20-communication-declarations.md)。平台仅验证 intent 明确映射的路径；例如旧车窗 intent 只映射 WindowPosition 和 RequestedDirection，其他编码信号不会被误称为已有完整 BSW 映射。

## 报告、审查与比较

`project-acceptance-0.3` 包含输入/运行来源哈希、可迁移的来源清单及 `comparison_basis`。通信阶段通过消息、信号、方向、frame ID 和原始整数观测绑定路径；运行失败会产生 `DECLARED-PATH-FAILED`，没有向量证据的路径为 `DECLARED-PATH-MISSING`。JSON 仍保留所有向量结果及原始运行报告。

审查读取 0.3 来源时先复核来源库存/哈希及快照中的验收定义，拒绝缺失或被修改的来源。正常/失败报告均可 answered：这是有证据可回答，不等于项目通过。报告所记事实与来源完整性不提供生产者身份认证。

涉及新项目的比较输出 `project-comparison-0.2`。只有报告版本、阶段集合、验收 ID 集合、comparison_key、本地 ECU、完整向量定义及验收条件全部一致时才比较结果；值类型差异也保守视为定义变化。来源缺失或篡改同样不可比较。旧版报告继续使用 comparison 0.1 的既有语义。

比较分类为 stable/regressed/improved/changed/not-comparable；比较不同业务项目或改变 expected 后，不会用相同 requirement ID 强行判定回归。输入修改但任务定义相同（例如 canonical 分辨率改错）可产生真实回归。这里比较的是验收结果；完整配置变更影响属于下一阶段 P21。

## 一次重放完整阶段证据

```bash
python -m pip install -e ".[can,dev]"
python scripts/run_multi_project_scenarios.py --output output/p20-release
```

打开 `output/p20-release/portable/index.html`。六个案例为车窗、ThermalControl、静态配置失败、合法输入下的运行超时、验收条件变化、不可用后端；五个比较为稳定、静态回归、运行回归、定义变化不可比较、不同项目不可比较。运行故障通过真实 virtual 端点上的发送抑制注入，`transport-injection.json` 明确记录方式。

脚本把整组原目录移动到 portable，确认原路径消失，再复验每个 manifest、review citation、项目来源和比较。迁移时保留整组目录结构；项目单包的复验命令为：

```bash
workbench verify-evidence output/p20-release/portable/projects/thermal/bundle output/p20-release/portable/projects/thermal/manifest.json --base output/p20-release/portable/projects/thermal --output output/thermal-reverification
```

CI 在 Windows/Ubuntu 的 runtime-evidence job 执行并上传 `multi-project-release`。Linux 现场入口另行执行：

```bash
bash scripts/linux/run_socketcan_projects.sh vcan0 output/p20-socketcan .venv/bin/python
```

该入口持有与既有实验一致的通道锁，依次执行两项目、审查、稳定比较及独立比较复验。接口必须已存在；失败/blocked 不代表阶段通过，项目目录保存具体状态。运行依旧是同进程两个 SocketCAN 端点，不证明物理 ECU、独立 ECU 生命周期或量产 BSW。
