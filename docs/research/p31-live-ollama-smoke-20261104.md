# P31 本机 Ollama 回答与检索现状检查（2026-11-04）

这是四条新问题的开发冒烟与人工证据对照，不是 P30 冻结题、盲审或模型质量验收。原始输入、模型响应、HTTP 传输和工作台证据保存在本机忽略目录 `output/p31-live-ollama-quality-20261104-live/` 与 `output/p31-live-ollama-quality-20261104-web/`，不随仓库公开提交。

## 运行条件

- 复用既有 `simulink-assistant-ollama` 容器，端口只绑定 `127.0.0.1:11434`；Ollama 版本 `0.31.1`，模型 `qwen3.5:2b`，digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df`。
- 图谱来自本机已导入快照：66 节点、90 关系，全部作为待核实候选；项目使用既有 `project-acceptance-0.8` transmitter 报告，报告 SHA-256 `f0b96213e1d8c13deeb5928f5734e630da0d88e29f0870a821f4bef6496f74aa`。
- 三条经 `knowledge_chat.ask`，一条经真实网页 `/api/chat`；四次均记录 `/api/tags`、`/api/version`、`/api/chat`、复查 `/api/tags` 的 HTTP 200，得到 `draft_unassessed`。最初默认沙箱内两轮 `/api/tags` 失败仅有错误 trace、没有模型生成调用；在回环网络可用的执行环境重新运行后成功。

## 人工对照

| 问题与输入 | 实际表现 | 对照结论 |
|---|---|---|
| CanTp 与 PduR 关系；只用图谱 | 找到 K006/K007 和候选数据流向，草稿称其为待核实线索 | 基本关系和候选边界正确；“本地 PDU ID”来自节点的 `source` 提示，非编造，但回答加入了未提问的 CF01 细节。 |
| COMMUNICATION 状态、reason、实车 CAN；图谱加项目报告 | 草稿说 `passed`，正确拒绝实车运行推断 | 已检索事实包含 `/checks/communication/reason = linked_in_scope`，回答却漏掉该值；`passed` 的引号损坏，并把已重放的项目事实称作待核实线索。 |
| CanTp 故障是否由 PduR 引起；图谱加项目报告 | 草稿指出候选关系不能证明因果，结论未知 | 关键拒答边界正确；项目通信检查实际为 `passed`，没有故障根因证据。 |
| COMMUNICATION status/reason；网页 API、仅项目报告 | 草稿正确输出 `passed` 与 `linked_in_scope` | 随后编造一个 64 位 `artifact_id`；该值不在传给模型的事实，也不在项目报告中。 |

本次四条短样本中，图谱关系题和因果拒答题基本维持了证据边界；另两条分别遗漏明确要求的事实和虚构引用。这个观察只支持“草稿需要核实”，不能外推成模型总体通过率或微调收益。混合输入可能干扰第二条问题，但仅项目报告的第四条仍会补造引用，因此不能把问题完全归因于图谱。

## 目前的检索增强范围

`knowledge_chat.ask` 在有图谱快照时调用 `search_graph`，按问题中的英文词或连续中文词匹配节点的标签/别名，最多取 6 个节点及其相连关系；传给模型的是节点摘要、关系、来源文件名和候选状态。项目报告通过 `build_request` 或 MCP 重放取得事实，最多传入 16 条。模型没有直接读取完整来源 Markdown，也没有使用向量索引或已安装的 embedding 模型；返回的 `citations` 仍为空。`output/knowledge-chat` 默认网页目录当前没有 `active.json`，因此直接从该目录启动网页时，须先显式导入图谱；选择项目报告后仍可使用项目事实检索。长期记忆只作为用户偏好，不作为事实。

后续模型质量工作应先固定可核对问题、事实引用与留出集，分别观察检索遗漏、上下文噪声和模型无依据补充。模型草稿保持 `unassessed`；微调仅在确认稳定的模型内容错误、准备经核实样本后评估。P31 的下一主实现任务仍是 Generate-Arxml 真实输出与回读的受控工具。
