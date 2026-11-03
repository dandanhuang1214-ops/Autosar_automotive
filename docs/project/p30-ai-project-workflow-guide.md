# AI 需求到项目验收入口 0.1

这项能力接在现有本地汽车知识图谱聊天网页上，复用同一 Ollama 服务、同一 `workbench-project` 执行器和原项目报告。当前支持 `workbench-project-0.6` 的**静态 ECUC 项目**，其 `applications`、`tool_logs` 均为空。一次只让模型从该项目已声明的验收 ID 中选一项；平台据此生成一份独立项目声明，用户检查后再点击运行。模型不能提出新验收 ID、路径或执行命令。

模型请求只包含本次需求和原项目验收项的 ID/描述；DPA、collection 与模块原文不发送给模型。任务目录可能含私有需求、路径和模型原始响应，应放在仓库忽略的本地 `--data` 目录。

## 使用

```sh
PYTHONPATH=src .venv/bin/python -m automotive_workbench.knowledge_chat_server \
  --data output/knowledge-chat --port 8767 \
  --ollama-url http://127.0.0.1:11434 --model qwen3.5:2b
```

打开 `http://127.0.0.1:8767/`，在左侧“AI 需求 → 项目验收”填写现有静态 ECUC 项目声明的绝对路径和需求。点击“让 AI 生成验收项目”后，先核对所选 ID 与原项目验收描述；再点击“运行项目验证”。页面会显示实际项目状态、包完整性、离线复验状态，并把生成的 `project-report.json` 填入工程报告栏。随后可直接提问，**无需先导入知识图谱**；若已导入图谱，工程事实与候选图谱线索仍分开显示。

`<data-dir>/project-tasks/<task-id>/` 保存：

- `model-trace.json`：本次需求、可选验收 ID、原始模型响应和传输记录；模型无效或不可用时记录拒绝原因，不创建生成项目。
- `proposal.json`：源项目文件与所选 ECUC 输入的 SHA-256、模型身份、选择结果和生成项目哈希。状态 `draft_unassessed` 表示模型选择尚待人审。
- `generated-project.json`：仅保留所选验收项的 `workbench-project-0.6` 声明；输入路径指向当前机器上的原始 DPA。它是本地候选，不是可移植交付包。
- `validation/` 与 `validation-result.json`：点击运行后由原 `run-project` 生成的快照、报告、manifest 和完整性复验；项目报告可用原 `verify-ecuc-project` 复验。

执行前平台再次核对原项目文件、DPA/collection/模块哈希、生成声明与保存的模型原文。被改动的输入、响应或生成文件均拒绝；任务只运行一次，输出目录不被覆盖。已有项目其他验收项未被这份 AI 选择声明纳入，仍为未验收。模型选择的**相关性尚无独立人工质量结论**，用户需审阅 ID；工程 `passed` 只来自实际 `run-project`，不来自模型。

## 本轮公开场景

使用 `examples/ecuc_acceptance/transmitter.project.json` 的合成通信需求，经真实 `qwen3.5:2b` / Ollama `0.31.1` 选出 `COMMUNICATION`，生成项目并运行；实际项目、证据完整性、项目包重放均 `passed`。网页 API 场景还确认无效本地令牌返回 403，生成报告可在未导入图谱时进入问答。重放入口：

```sh
PYTHONPATH=src .venv/bin/python scripts/run_ai_project_web_scenario.py \
  --project examples/ecuc_acceptance/transmitter.project.json \
  --output output/ai-project-web-scenario.json
```

此脚本需要本地 Ollama 与上面的网页服务。公开静态测试使用伪模型验证未知 ID、源输入漂移、生成声明篡改和模型原文篡改被拒；它不替代真实模型质量评估。首次结构化输出请求在真实模型处返回空内容，未生成项目；改用单 ID 原文协议后，上述新需求通过。该开发冒烟使用了提示中明确的 `COMMUNICATION`，不能当作自然语言泛化或 P30 独立人工内容门通过。

此入口目前生成的是**项目验收声明**，并运行静态 ECUC 验证；不生成 ARXML、ECUC 写回或供应商代码，不执行 CAN/诊断。下一扩展应在同一受控入口接入已有 Generate-Arxml 的实际产物生成、版本/来源记录及回读验收，且对生成器执行条件单独验收。P30 的 0.7 development v1 独立人工审阅与 P25 人工演示仍待完成。
