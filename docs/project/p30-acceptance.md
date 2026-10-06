# P30 验收表

整阶段：implementing。首轮只读事实门 remote-accepted。实现 `a82ee62c758c82741aa083636744b5c6766892a3` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job 全部 success；Windows/Ubuntu 事实场景、隔离安装、证据上传均 success。模型解释不在首轮已验收范围。

| 门 | 状态 | 证据与范围 |
|---|---|---|
| 只读复验事实输入 | remote-accepted | 项目 0.6–0.9 完整复验；报告、来源、问题、类型化值和策略绑定 |
| 严格引用与值校验 | remote-accepted | 非法编号、重复编号、值改写、额外文本、跨请求、历史运行、请求/依赖篡改拒绝；不补号 |
| 两工程 CLI / 搬移 | remote-accepted | 127 / 70 facts；各 4 类 CLI 拒绝；中文空格路径、删除原输入后复验 |
| 隔离安装 | remote-accepted | 无依赖 wheel、仓库外运行、排除 checkout、两工程流程与归档复验 |
| 双平台远端 | remote-accepted | `a82ee62` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job success，双平台新增三步骤 success |
| Ollama 与现有知识助手 | remote-accepted | 原服务已恢复；只读接口、模型/提示/原始输出/回退、12 个协议场景及安装验证通过；真实模型质量另列 |
| 项目事实与资料知识分离 | remote-accepted | 原文检索与审核/来源核对，手册逐字摘录检查；草稿语义始终 unassessed |
| 模型回答独立评测 | implementing | 开发/独立问题、配置拒绝、影响、CAN 超时、诊断负响应、缺证据、历史替换；延迟与人工可用性 |

本地证据：`output/p30-fact-validation/`。全量回归 400 项（398 passed、2 环境跳过），随后增加数值类型/对象身份负例，P30 与 topology 定向 9 项通过；56 schemas、76 bound/25 syntax-only、57-source mypy、Ruff、topology、pip check 与 whitespace 通过。源码与最终隔离安装场景通过。首次安装脚本误解析 venv Python 符号链接，修正为保留 venv 可执行路径后重跑通过。

后续状态回填固定实现 SHA 和真实 run/jobs，不把文档状态提交当实现验证。P25 人工验收、物理 ECU、商业生成边界保持。

## 远端记录（2026-10-04）

实现 `a82ee62c758c82741aa083636744b5c6766892a3` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job 全部 success；Windows/Ubuntu 事实场景、隔离安装、证据上传均 success。

- `runtime-currency`：job `111380561415`，success。
- `core-contracts (windows-latest)`：job `111380561531`，success。
- `core-contracts (ubuntu-22.04)`：job `111380561539`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111381028146`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111381028182`，success。
- `runtime-evidence (windows-latest)`：job `111381028187`，success。
- `controlled-rejections (windows-latest)`：job `111381028195`，success。

原始记录 `output/p30-fact-validation/remote-ci.json`，双平台 artifact 为 `project-explanation-Windows` / `project-explanation-Linux`。本次回填是后续纯文档 `[skip ci]` 提交，固定引用上述实现 CI，不代表模型阶段验收。


## 模型适配本轮验收（2026-10-05）

- 协议/工程门 local-accepted：最终 409 tests（407 passed、2 环境跳过）；57 schemas、76 bound/25 syntax-only、61-source mypy、Ruff、topology、pip check、whitespace 通过。源码和无依赖隔离 wheel 各 12 个合成 HTTP 场景，含 schema、服务停止后的复验与归档复验；新增 8 项模型专项测试。
- 现场恢复原 Docker Desktop 及 Ollama/Qdrant/API，不下载镜像/模型，不改动原资料。原知识库 23 文档 / 15 可检索，模型三份均存在。真实检索取得 3 份原文摘录，保留 legacy_trusted 来源等级。
- 真实模型为 qwen3.5:2b，服务报告 digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df`，Ollama 0.31.1。共 6 次开发调用，1 次结构化单事实引用通过、5 次拒绝。提示 0.1 字段缺失，0.2 截断，0.3 双摘要误抄，0.4 单事实成功但带资料摘录与缺证据问题引用不合格；旧提示和原始失败可离线重放。
- 这些是开发观察，不是独立模型质量评测；不能把拒绝正确等同模型拒答正确，也不能用一条成功证明复杂解释可用。自然语言语义、问题相关性和建议可用性均未自动认证。
- 原服务缺失时的真实 blocked 回退另存 `live-unavailable`。本轮最终归档 `output/p30-model-validation/`，具体磁盘与资产结果见[复用盘点](p30-reuse-inventory.md)。
- P30 整阶段 implementing；下一项独立问题评测、输出约束适配和资料适用性/人工可用性。实现 `21a495e2047662084a6a30f78196ed6fd2f3f148` / [run `37264801076`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37264801076) 七 job 全部 success，双平台事实场景、模型场景、隔离安装及证据上传均 success。

## 模型适配远端记录（2026-10-06）

实现 `21a495e2047662084a6a30f78196ed6fd2f3f148` / [run `37264801076`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37264801076) 七 job 全部 success。固定 LF 写入确保模型归档可跨平台复验。

- `runtime-currency`：job `111619216006`，success。
- `core-contracts (windows-latest)`：job `111619216183`，success。
- `core-contracts (ubuntu-22.04)`：job `111619216213`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111620503794`，success。
- `runtime-evidence (windows-latest)`：job `111620503805`，success。
- `controlled-rejections (windows-latest)`：job `111620503826`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111620503830`，success。

原始记录：`output/p30-model-validation/remote-ci.json`。后续状态文档提交不是新的实现验收；真实模型质量仍未通过，六类评测在 P30 内继续。

跨平台实证（2026-10-06）：下载上述 run 的 `project-explanation-Windows`，源码 12 例及安装后 12 例共 24 份模型解释在 Linux 完整离线复验通过；原始结果 `output/p30-model-validation/windows-linux-replay.json`。
