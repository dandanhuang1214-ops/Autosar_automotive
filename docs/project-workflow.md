# 一条命令验收通信项目

P15 把平台已有的输入校验、通信实验和工程证据串为项目工作流。第一条工作流使用公开车窗通信模型：`WindowStatus` / `WindowCommand`、`0x100` / `0x200`。不将其当作任意 ECU 的通用测试生成器。

在仓库根目录运行：

```bash
python -m pip install -e '.[diag,dev]'
python -m automotive_workbench.cli run-project examples/window_control/project.json --output output/my-project-run
```

在已有 WSL 虚拟环境中可用 `.venv/bin/python` 替换 `python`。执行完成后，用浏览器打开 `output/my-project-run/bundle/index.html`。无需启动网页服务。

`project.json` 包含输入与声明验收项：

- `inputs`：DBC、Generate-Arxml canonical contract、BSW intent，路径相对于项目文件。
- `requirements`：唯一 ID、验收说明、阶段、JSON Pointer 和期望的 JSON 标量值。
- 阶段只支持 `canonical`、`mapping`、`communication`，比较方式为精确相等。布尔值不等于数字；整数与浮点数按 JSON number 数值比较。

验收项示例：

```json
{
  "id": "WIN-TRACE-001",
  "text": "两条声明的静态路径均绑定到同次运行观测",
  "stage": "communication",
  "pointer": "/bound_count",
  "expected": 2
}
```

项目报告显示各阶段状态、每项验收的期望/实际值以及对应报告链接。机器可读报告另外保留报告 SHA-256 和 JSON Pointer。原始 findings 保存在 `canonical.json`、`mapping.json` 和 `communication/` 报告中。

| 场景 | 项目结果 | 通信阶段 |
|---|---|---|
| 配置校验及声明验收项均通过 | passed | 执行 |
| canonical 的 scale 与 DBC 不符 | failed | skipped，相关验收项 blocked |
| 静态通过，但 SocketCAN 后端不可用 | blocked | blocked |
| 证据字段缺失或与期望不符 | failed | 保留实际执行状态 |

CLI 退出码：通过 `0`，验收失败 `2`，后端阻断 `3`，输入/执行异常 `1`。输出目录必须为空或不存在；再次运行请换目录，避免混入旧结果。

要观察配置错误，可复制 `examples/window_control/` 到自己的目录，将复制件 `canonical_contract.json` 第一个信号的 `resolution` 从 `1` 改为 `2`，再用复制件的 `project.json` 运行。应看到 `MAP-NUMERIC-MISMATCH`，且通信实验未执行。不要修改原始基线来保存故障案例。

一次运行保存完整输入快照及输出。整个输出目录可以迁移后复验：

```bash
python -m automotive_workbench.cli verify-evidence output/my-project-run/bundle output/my-project-run/manifest.json --base output/my-project-run --output output/my-project-recheck
```

`bundle/inputs/project.json` 保存原始项目声明用于审计，其他输入使用固定快照文件名；不要把该归档声明当作可直接重跑的项目配置。重新执行使用原始项目目录，或另建一份指向快照文件的项目配置。

需要 SocketCAN 时显式传 `--interface socketcan --channel vcan0`。入口不创建接口、不自动取得通道锁，也不把不可用 SocketCAN 静默改为 virtual。应保证同一通道没有其他 Workbench 实验占用相关 CAN ID。

这 5 项是公开样例的声明验收项，不代表完整车窗需求覆盖率。P15 不自动调用 Generate-Arxml 生成器或商业工具，也未接入目标 ECU。

P16 增加 project 0.2：导入实际 Generate-Arxml 的 DOCX、contract 和 issue report，新增 `generation` 阶段；先校验声明哈希，再读取完整上游 findings。上游阻塞或任一静态失败均跳过通信。公开三例含正常、分辨率变化和初值缺失，另有显式调用固定生产者的重放脚本，详见 [Generate-Arxml 桥接](../examples/generate_arxml/bridge/README.md)。0.1 项目继续可用。

P17 在项目输出之上增加确定性工程审查。它读取 `project-report.json` 及报告中声明的阶段文件，为项目状态、各阶段状态、非通过验收项和每条 finding 的 severity/code/message 建立精确 JSON Pointer 断言，并锁定源文件 SHA-256：

```bash
python -m automotive_workbench.cli run-project-review \
  output/my-project-run/bundle/project-report.json \
  --output output/my-project-review
```

`project-review.md` 回答哪些阶段执行、哪里失败、通信是否被门控，并在每条结论下显示来源和定位；`review-result.json` 保留完整 citation 与复验结果。缺少阶段报告时不猜测，结果为 `refused`。可用 `--claim "..."` 检查一条自由声明；如果全部项目证据都不能覆盖该声明，同样返回 `refused`。

完整公开验收会重跑 Generate-Arxml 桥接的 baseline、scale-change、missing-init 三份固定导出，并确认“已测量并认证物理 ECU flash timing”不受这些 virtual/合成证据支持：

```bash
python scripts/run_project_review_scenarios.py --output output/p17-review
```

该入口仍为 retrieval-only，不调用 LLM、embedding 或外部服务。引用正确和拒答边界先于自然语言生成；是否接入 LLM 由后续真实使用反馈决定。

P18 对两份独立项目验收报告做确定性比较：

```bash
python -m automotive_workbench.cli compare-projects \
  output/baseline/bundle/project-report.json \
  output/candidate/bundle/project-report.json \
  --output output/project-comparison
```

可比较的前提是 project report schema version、阶段集合和验收项 ID 集合一致。比较逐项报告阶段状态、验收状态与理由，并把 stage finding 作为集合计算新增和移除；finding 中随归档位置变化的来源路径不参与指纹。每项变化引用 baseline/candidate 的精确 JSON Pointer 和 SHA-256。

`stable` 表示未发现稳定字段变化，`regressed`/`improved` 表示项目结果相对通过状态变差/变好，`changed` 表示存在其他可审计变化，`not-comparable` 表示比较前提或证据完整性不成立。阶段文件缺失、未被项目报告唯一哈希绑定或字节被修改时不会继续推断 finding 差异。完整目录迁移后仍可调用 `validate_project_comparison` 复验相对引用。

公开验收入口重跑 baseline、scale-change 和 missing-init 项目，生成稳定、两类回归及反向改善四份比较：

```bash
python scripts/run_project_comparison_scenarios.py --output output/p18-comparison
```

比较只说明声明的项目结果和 artifact 差异，不证明根因或物理 ECU 行为。
