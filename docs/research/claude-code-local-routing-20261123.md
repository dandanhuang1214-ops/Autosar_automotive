# VS Code Claude Code 本地模型路由核查（2026-11-23）

## 范围与配置

本轮只调整用户 Windows 侧的 Claude Code 和 LiteLLM 配置，不修改 Workbench 模型默认值或项目实现。配置文件分别为 `C:\Users\20261\.claude\settings.json` 和 `C:\Users\20261\.ollama-proxy\litellm_config.yaml`；原件已在原目录备份为 `settings.json.bak-20261123-model-routing` 和 `litellm_config.yaml.bak-20261123-model-routing`。密钥不写入仓库。

| Claude Code 别名 | LiteLLM 模型 | 上游 | 本轮变化 |
|---|---|---|---|
| Haiku | `qwen3.5:4b` | 本机 Ollama | 保持路由，`num_ctx=16384` |
| Sonnet | `deepseek-v4-pro` | DeepSeek | 保持路由，未做本轮真实云端调用 |
| Opus | `ministral-3:3b` | 本机 Ollama | 新增路由，`num_ctx=16384`；该路由过滤 `thinking` 和 `reasoning_effort` |

LiteLLM `1.110.0` 代理重启后 `/v1/models` 列出 `deepseek-v4-pro`、`deepseek-v4-flash`、`qwen3.5:4b` 和 `ministral-3:3b`。Ollama `/api/ps` 分别确认两个本地模型以 16384 context 加载；近期重放没有再出现 `truncating input prompt`。模型原生 context 均允许 16K，较长上下文仍会增加本机内存占用和延迟。`/model` 在旧 VS Code 会话中实测 Haiku→Qwen、Sonnet→DeepSeek；本轮用扩展自带 Claude Code `2.1.330` 验证 Haiku/Opus 别名。系统另装的 CLI `2.1.185` 较旧，不能把其重试/超时当作当前扩展的验收结果。

## 故障与复测

旧 VS Code 会话 `2.1.323` 中，Qwen 面对“列出当前目录”和“上网搜索”只输出模拟工具文字或 `file://` 链接，没有真正的 `tool_use`。原配置 Ollama context 为 4096；本轮诊断日志见过 6491-token 输入被截到 2050 token。旧会话没有同次服务端日志，因此只能把截断视为强线索，不把它写成唯一根因。

用 VS Code 扩展自带客户端 `2.1.330`、项目目录 `D:\workspace\matlab_project\WW`、只读工具复测：

| 场景 | 实际工具和结果 | 最终状态 |
|---|---|---|
| Haiku→Qwen，指定 `BuildWiperSpeedModel.m` | `Glob` 返回该文件 | 模型准确回答文件名；闭环通过 |
| Haiku→Qwen，自然语言列当前目录，完整工具描述但只允许读工具 | `Glob` 使用 `*`，返回目录文件 | 模型列出的前三个文件名实际存在；附加文件用途描述未经核验，不计入通过范围 |
| Opus→Ministral，指定同一文件 | `Glob` 返回 `BuildWiperSpeedModel.m` | 模型错误回答“未找到”；工具协议通过，回答质量失败 |
| Haiku→Qwen，`WebSearch` 查 Ollama 官方说明 | 模型发出 `WebSearch`；首个工具结果没有可核对网址，第二次搜索等待至 150 秒上限 | 真实网页搜索未验收 |
| Haiku→Qwen，`WebFetch` 抓取官方页面 | 模型发出 `WebFetch`，150 秒内没有工具结果 | 真实网页抓取未验收 |
| Haiku→Qwen，受限 `Bash(curl.exe *)` 抓取已知官方网址 | 真正执行 `curl.exe --max-time 12 ... https://docs.ollama.com/context-length`，工具结果为 HTTP `200` | 模型准确报告 `200`；已知网址的本机命令访问通过，不等于搜索能力 |

Windows `curl.exe` 访问 `https://docs.ollama.com/context-length` 返回 HTTP 200，Qwen 经 Claude Code 的受限 Bash 命令也得到同样结果，因此机器和本地模型调用命令工具均可访问已知网页；不能把内置搜索/抓取工具的超时归因于整机断网。LiteLLM `/v1/messages` 的小型工具请求在 Qwen 和 Ministral 上均能返回结构化 `tool_use`；Qwen 在注入工具结果后也能准确回答。完整 Claude Code 请求与简短协议请求是不同验收层级。Opus 别名最初因 Ministral 不支持 `thinking` 返回 400，单路由过滤后扩展客户端能够完成工具回合；仍有上述内容错误。

本轮未操作 VS Code 图形界面里的新会话；扩展自带二进制的命令行重放不等同用户交互验收。原始 CLI 事件和临时请求保留在本机 `/tmp/vscode330-*20261123.jsonl` 与忽略目录 `output/local-routing-test/`，不提交私有会话、请求或代理凭据。

## 使用边界与下一步

Qwen 现可在新短会话中执行只读文件工具，并通过受限本机命令访问已知公开网址；较长工程会话和有副作用工具尚未稳定验收。Ministral 只是 Opus 别名的本地后端，不具备真实 Claude Opus 的质量保证；其工具结果误读需要新题复测与约束。Claude Code 当前 `WebSearch`/`WebFetch` 没有形成可引用的网页结果，若要本地模型稳定搜索，应另接可验证的搜索服务或 MCP 工具，并保留来源与超时证据。

这项本机环境支持不改变 AI 平台 Agent 主门：来源 ID 冻结前校验、本地动作可靠性、新留出和逐句人工审阅；Workbench P31 与 P25 人工门状态不变。本轮没有仓库实现变更，也没有可宣称的远端实现 CI 验收。
