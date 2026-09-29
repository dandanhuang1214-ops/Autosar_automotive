# P25 安装后双项目交付

本轮验证 wheel 的实际工程流程：车窗与 ThermalControl 正常运行、DBC 缩放故障、静态门控、配置影响、项目回归、工程审查及迁移复验。使用公开合成输入和进程内 virtual CAN，不要求 CAN 硬件。商业工具、OpenBSW 现场运行和个人实操能力不由此验收。

## 一条命令生成交付证据

构建环境需要 Python 3.11 或以上和项目开发依赖。以下命令在仓库根目录执行，输出目录必须不存在或为空。

Linux：

```bash
python3 -m venv .venv-delivery
.venv-delivery/bin/python -m pip install '.[can,dev]'
.venv-delivery/bin/python scripts/check_installed_projects.py --output output/installed-projects
```

Windows PowerShell：

```powershell
py -3.11 -m venv .venv-delivery
.\.venv-delivery\Scripts\python.exe -m pip install '.[can,dev]'
.\.venv-delivery\Scripts\python.exe scripts/check_installed_projects.py --output output/installed-projects
```

脚本构建 wheel、下载平台适配的二进制依赖，然后创建第二个全新 venv，以 `--no-index` 从归档 wheelhouse 安装。清除 PYTHONPATH/PYTHONHOME、关闭用户 site，验证包来源和解释器 prefix。所有工程步骤通过安装后的绝对路径 `workbench` 在仓库外执行；旧项目审查引用的独立复验通过该 venv 的 Python 调用已有验证接口。

成功后保留：

- `summary.json`：实际解释器/依赖、耗时、输入及发行物 SHA-256、各项目状态、迁移证据库存。
- `commands.json`：每步命令、实际与预期退出码、stdout/stderr、耗时。临时绝对路径仅是执行记录，重跑使用下方相对路径。
- `wheelhouse/`：本次 wheel 及完整 CAN 依赖，适用于所记录的平台/Python；不是跨平台通用依赖包。
- `portable/examples/`：每项目仅复制 project 和声明的四个输入；`scale-failure` 只修改 ThermalControl DBC 的第一个温度缩放系数 0.1 → 0.2。
- `portable/projects/`、`reviews/`、`impact/`、`comparison/`、`impact-review/`、`replay/`：工程报告及来源、引用和迁移复验结果。打开各项目的 `bundle/index.html` 查看报告。

网络只用于构建环境准备和依赖下载。已有同平台依赖可通过 `--wheelhouse PREVIOUS_OUTPUT/wheelhouse` 复用；脚本仍从当前源码重新构建 workbench wheel，不误用旧实现。下载/安装失败返回非零，不算安装验收通过。

## 在仓库外手动重跑归档

把输出整个目录复制到新工作目录。新建 venv 后安装归档中的 wheel（用实际文件名替换），Linux 使用 `./env/bin/`，PowerShell 使用 `.\env\Scripts\`：

```bash
python -m venv env
./env/bin/python -m pip install --no-index --find-links wheelhouse 'wheelhouse/automotive_workbench-0.1.0-py3-none-any.whl[can]'
./env/bin/workbench run-project portable/examples/window/project.json --output rerun/window
./env/bin/workbench run-project portable/examples/thermal/project.json --output rerun/thermal
./env/bin/workbench run-project portable/examples/scale-failure/project.json --output rerun/scale-failure
./env/bin/workbench compare-communication-config portable/examples/thermal/project.json portable/examples/scale-failure/project.json --output rerun/impact
./env/bin/workbench run-project-review rerun/scale-failure/bundle/project-report.json --output rerun/review
./env/bin/workbench compare-projects rerun/thermal/bundle/project-report.json rerun/scale-failure/bundle/project-report.json --output rerun/comparison
./env/bin/workbench verify-project-comparison rerun/comparison/project-comparison.json
```

故障 `run-project` 和回归 `compare-projects` 的预期退出码为 **2**；前两个正常项目、影响比较和有效报告复验为 **0**。故障项目应显示 failed，通信阶段 skipped；影响向量为 `thermal-status`，不应包含 `pump-status`。复验 passed 表示报告与证据一致，不把原项目失败改成通过。自动脚本逐项检查上述状态，并在原路径不存在时重放全部三组项目证据、三组审查引用、影响、比较与工程答案。

## 演示与学习

建议按“两个正常项目 → 改缩放 → 静态失败阻止通信 → 定位受影响验收项 → 审查引用 → 迁移复验”演示。`summary.json.seconds` 是本次自动流程实测耗时，不等同于人工讲解十分钟的验收；人工演示和真实外部反馈尚需单独记录。

工具链方向可据本次证据讲解发行物、依赖隔离、静态门控和可重放报告；BSW 方向可讲解映射与 Tx/Rx 影响范围，但不据此声称掌握供应商 ECUC 或硬件调试。练习：独立解释为何缩放变化影响 thermal-status、为何失败报告也可复验通过，并指出引用落在哪个文件/字段。
