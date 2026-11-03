# P31 Workbench MCP 服务化：首条工程证据链

状态：0.1 首版本地验证通过，远端 CI 待验收。P30 仅按受限范围交付；本阶段不改变原有模型质量结论。

## 调研与架构

2026-11-03 查阅 [MCP 2026-07-28 版本说明](https://blog.modelcontextprotocol.io/posts/2026-07-28/)、[Python SDK 入门](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)、[安装](https://py.sdk.modelcontextprotocol.io/get-started/installation/)、[运行与传输](https://py.sdk.modelcontextprotocol.io/run/)及[客户端传输](https://py.sdk.modelcontextprotocol.io/client/transports/)。首版采用官方 Python SDK 2.3 的 `MCPServer`/`Client`，本机网页与独立服务之间使用 Streamable HTTP；命令行工具可用 stdio。采用当前 2026-07-28 模式调用，依赖放在可选的 `mcp` extra，核心 wheel 不要求 MCP。决策见 [ADR 0001](../adr/0001-workbench-mcp-host-boundary.md)。

网页 Host 保留会话、用户记忆、图谱候选与 Ollama 草稿；MCP 服务仅重放 ECUC 项目包并返回结构化事实。`verify_project_report` 给出重放状态和报告 SHA；`project_evidence` 给出问题绑定的报告 SHA、项目状态、事实及证据边界。两工具均标记只读。报告须为配置根目录下的绝对普通文件，项目包现有验证器拒绝符号链接并检查库存。网页指定 `--mcp-url` 后仅通过 MCP 读取项目证据，服务不可用时返回错误，不使用直读降级。未指定时原网页路径保持兼容。

## 运行

```bash
python -m pip install '.[diag,mcp]'
workbench-mcp --root output/my-project --transport streamable-http --port 8768
workbench-chat --data output/knowledge-chat --port 8767 \
  --mcp-url http://127.0.0.1:8768/mcp
```

两个进程分别运行。`--root` 应覆盖要读取的项目报告及完整项目包；网页中选择其 `bundle/project-report.json` 的绝对路径。模型仍由网页的 `--model`、`--ollama-url` 控制。MCP stdio 模式为默认传输，供其他本地 Host 按相同工具契约连接。

## 当前门与下一步

首版门：SDK 能发现两个只读工具、读取真实项目报告并核对 SHA/状态；越界路径拒绝；网页经独立 MCP 进程返回工程证据；停服后网页失败关闭；原直读路径和全量回归保持通过；实现提交须有 head 一致的七 job 远端 CI。模型文本本身不纳入工程验收。

下一步 0.2：把用户的“需求 → 候选项目声明 → 显式验证”拆成版本化 MCP 工具，网页继续拥有模型选择和确认动作；现有 `/api/project/propose`、`validate` 合约先保持兼容。随后以 Generate-Arxml 的实际输出和回读证据设计受控生成工具，不把项目声明生成写成 ECUC/ARXML 生成。远端服务、身份授权及跨机器部署需另立安全与验收门。
