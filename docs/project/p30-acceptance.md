# P30 验收表

整阶段：implementing。首轮只读事实门 local-accepted，待本次实现提交的远端 CI。模型解释不在首轮已验收范围。

| 门 | 状态 | 证据与范围 |
|---|---|---|
| 只读复验事实输入 | local-accepted | 项目 0.6–0.9 完整复验；报告、来源、问题、类型化值和策略绑定 |
| 严格引用与值校验 | local-accepted | 非法编号、重复编号、值改写、额外文本、跨请求、历史运行、请求/依赖篡改拒绝；不补号 |
| 两工程 CLI / 搬移 | local-accepted | 127 / 70 facts；各 4 类 CLI 拒绝；中文空格路径、删除原输入后复验 |
| 隔离安装 | local-accepted | 无依赖 wheel、仓库外运行、排除 checkout、两工程流程与归档复验 |
| 双平台远端 | 待运行 | 本次实现提交的七 job 及 Windows/Ubuntu 场景、安装、上传尚待核对 |
| Ollama 与现有知识助手 | planned | 模型身份、提示版本、输入与原始输出、服务缺失回退 |
| 项目事实与资料知识分离 | 部分实现 | 当前仅允许 project facts；手册检索和解释尚未接入 |
| 模型回答独立评测 | planned | 开发/独立问题、配置拒绝、影响、CAN 超时、诊断负响应、缺证据、历史替换；延迟与人工可用性 |

本地证据：`output/p30-fact-validation/`。全量回归 400 项（398 passed、2 环境跳过），随后增加数值类型/对象身份负例，P30 与 topology 定向 9 项通过；56 schemas、76 bound/25 syntax-only、57-source mypy、Ruff、topology、pip check 与 whitespace 通过。源码与最终隔离安装场景通过。首次安装脚本误解析 venv Python 符号链接，修正为保留 venv 可执行路径后重跑通过。

后续状态回填固定实现 SHA 和真实 run/jobs，不把文档状态提交当实现验证。P25 人工验收、物理 ECU、商业生成边界保持。
