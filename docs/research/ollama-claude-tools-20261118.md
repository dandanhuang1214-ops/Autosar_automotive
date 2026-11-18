# 本机 Ollama 与 Anthropic 接口工具选择核查（2026-11-18）

本轮是 AI 平台 Agent 主线的模型环境与可用性核查。用户的另一条接法通过 Claude SDK 将 Anthropic Messages 请求路由到 Ollama；这里直接调用同一个 Ollama `/v1/messages` 接口验证模型返回的 `tool_use`。没有运行用户的 Claude SDK 进程，也没有连接真实网页搜索或真实 MCP 服务；搜索与 MCP 的工具返回由测试 Host 注入。Generate-Arxml 的检查结果来自仓库真实脚本，模型只负责选工具并解释报告。

## 环境和候选

- Windows RTX 3050 Ti Laptop GPU，4096 MiB；Ollama 容器 `simulink-assistant-ollama`，版本 0.31.1。
- 用户已删除 `qwen3.5:2b` 和 `qwen3:4b-instruct-2507-q4_K_M`。按[官方模型页](https://ollama.com/library/ministral-3:3b)选取支持中文和函数调用的 `ministral-3:3b`，本机下载后 `ollama show` 为 3.8B、Q4_K_M、`tools` 能力。Docker 模型卷由 5.853 GB 增至 8.807 GB。4096 context 驻留时 `ollama ps` 为 67% GPU / 33% CPU；文件下载大小和运行内存不可混同。
- 同题对照使用已安装的 `qwen3.5:4b`。这不是固定模型权重、温度和缓存条件的质量评测，延迟仅作为本次观察。

## Generate-Arxml skill 场景

按 skill 读取 `SKILL.md`、`project-workflow.md` 与 `document-contract.md`；确认 Generate-Arxml 仓库身份和现有虚拟环境。仓库自带 `docs/horn_standard.docx` 的 21 张表包含多个 Component/Composition、S/R、C/S、Operations、Runnable 和 Connector，故检查模式应为 `--mode mixed --profile mixed_signal_soa`。实际执行的 **inspection-only** 命令只写 contract、Excel 和 issue 报告，未请求 ARXML。脚本以 exit 1 返回：3 个 open issue、14 个模型验证错误、9 个 CORE finding（其中 7 个 ERROR、2 个 WARNING），因此生成门关闭。首个问题是 Runnable Access 引用未定义 S/R 信号 `Rp_Horn_Atm_SR`。报告在 Generate-Arxml 仓库的 `output/deliverables/horn_model_probe_20261118/`。

Anthropic 接口工具集中同时提供 `inspect_docx`、`generate_arxml`、`web_search` 和 `mcp_read_report`。`ministral-3:3b` 首轮正确选择 `inspect_docx`，参数为 `docs/horn_standard.docx`、`mixed`、`mixed_signal_soa`；没有调用生成工具。首轮自由回答虽然读对主要数量，却补写了报告未支持的缺口描述，且 240/500 输出 token 上限导致回答截断，不能作为可用结论。将最终回答约束为五行、精确报告字段后，同一候选再次选对检查工具，并正确列出 3/14/9（7 ERROR）、未生成 ARXML、首个 open issue 和报告路径。`qwen3.5:4b` 在同一技能题中误选 `web_search`，没有进入文档检查；该样本只证明这一次路由失败，不能代表全部任务分布。

## 搜索与 MCP 工具场景

`ministral-3:3b` 对“从哪个版本开始兼容 Anthropic Messages API”正确选择 `web_search`，非空查询；Host 将[Ollama 官方说明](https://ollama.com/blog/claude)的网页片段作为搜索结果返回后，模型答出 v0.14.0 并附来源链接。此项验证工具选择与给定片段使用，不验证模型或 Host 真的联网搜索。

对合成项目报告 `test-project-42`，候选正确选择 `mcp_read_report` 并传入指定 ID；Host 返回 `COMMUNICATION=attention-required`、`TEST-SHA-42` 和 `synthetic=true` 后，模型保留状态、哈希和合成边界。此项验证 MCP 风格工具参数与结果使用，不代替真实 MCP 握手、服务错误或多轮 Agent 评测。

## 决定与边界

保留 `ministral-3:3b` 作为 Claude SDK 本地工具选择的**试用候选**：三个受控首轮场景均选对工具；严格限定输出字段时 Generate-Arxml 解释正确。它尚未达到“稳定执行 Skill＋真实网页搜索＋MCP”的验收：自由回答出现无依据扩写，4096 context 在完整 skill 与更多工具描述下会紧张，且本机需部分 CPU 卸载。应由 Host 执行确定性检查、限制模型可见工具与输出字段，并用新任务复测真实客户端与 MCP。现存 `qwen3.5:4b` 按用户要求作为 Workbench 默认本地文本模型；这一配置选择与候选 Agent 工具质量分开记录。

原始 Anthropic 请求/响应保存在本机忽略目录 `output/ollama-model-eval-20261118/`；没有把私有图谱内容写入仓库。后续 AI 平台 Agent 主任务仍是来源 ID 冻结前校验、本地动作可靠性及新留出逐句审阅，不能把本轮开发场景当正式内容验收。
