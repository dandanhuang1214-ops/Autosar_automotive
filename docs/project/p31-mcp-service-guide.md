# P31 Workbench MCP 服务化：工程证据与项目候选

状态：0.1 首版已远端验收，实现 `67092d9` / [run `41586327182`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/41586327182) head 一致、七 job `success`。0.2 项目候选工具正在验收。P30 仅按受限范围交付；本阶段不改变原有模型质量结论。

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

## 0.2 项目候选与显式验证

项目操作工具需要显式开启。服务的 `--root` 必须是一个普通目录，包含要选择的静态 `workbench-project-0.6` 项目 JSON、两份 ECUC DPA 和它们引用的文件；候选任务与验证输出保存在该目录的 `project-tasks/`。网页 `--data` 可使用另一个目录。项目和 DPA 路径必须在服务根目录内；网页表单填写项目 JSON 的绝对路径。

```bash
workbench-mcp --root /absolute/project-workspace \
  --transport streamable-http --port 8768 --enable-project-actions
workbench-chat --data output/knowledge-chat --port 8767 \
  --mcp-url http://127.0.0.1:8768/mcp
```

启用后增加三个工具：只读的 `project_check_catalog` 返回已有验收项及项目/输入哈希；`create_project_candidate` 只接受网页 Host 从这些 ID 中取得的模型选择，复核哈希后写入候选声明和模型 trace；`validate_project_candidate` 在用户点击“运行项目验证”后执行已有 `run-project` 并重放验证报告。写入工具默认不注册。模型调用留在网页 Host，MCP 服务不生成或审阅模型文字。网页 `/api/project/propose` 和 `/api/project/validate` 的响应合约不变；指定 `--mcp-url` 后它们都通过 MCP 执行，停服时返回错误，不回退到本地项目执行。

本阶段生成的是从已声明验收项中选择一项的**项目声明候选**。验证结果只覆盖所选验收项；未选择的验收项保持未评估。没有生成 ECUC/ARXML，也没有做实车验证。Ollama 未启动时，候选选择无法完成，不能将确定性证据摘要当成模型草稿。

## 当前门与下一步

首版门：SDK 能发现两个只读工具、读取真实项目报告并核对 SHA/状态；越界路径拒绝；网页经独立 MCP 进程返回工程证据；停服后网页失败关闭；原直读路径和全量回归保持通过；实现提交须有 head 一致的七 job 远端 CI。模型文本本身不纳入工程验收。

0.2 门：三个工具的 SDK 注册/边界/真实项目运行检查；独立 MCP 进程经网页 API 完成候选、显式验证和报告问答，停服后失败关闭；原直读模式和全量回归通过；实现提交须有 head 一致的七 job 远端 CI。独立双进程开发场景使用测试模型选择，不能证明本机 Ollama 成功推理。

下一步：以 Generate-Arxml 的实际输出和回读证据设计受控生成工具，不把项目声明生成写成 ECUC/ARXML 生成。远端服务、身份授权及跨机器部署需另立安全与验收门。
