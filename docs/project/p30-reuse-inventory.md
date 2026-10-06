# P30 现有 LLM 资产复用盘点（2026-10-06 更新）

盘点基于同级 `simulink-assistant` 的当前源码（HEAD `33b5fdbb1b9522ff18627965adbf955c968c6b76`）、配置和本机探测。源码存在、历史文档记载、当前服务运行分别记录；没有把历史知识条目数或模型名当作本次现场验收。

| 已有资产 | 复用判断 | 接入方式 / 限制 |
|---|---|---|
| Ollama、对话模型和 embedding 配置 | 已实测复用服务和已安装模型 | 现有默认 `qwen3.5:2b` / `qwen3-embedding:0.6b`；工作台要求显式模型名，读取服务版本、模型 digest，不自动下载或切模型 |
| `POST /api/search` 混合检索 | 直接消费已有入口 | 复用 BM25/Dense 和现有索引；工作台显式关闭 query rewrite / rerank，不重建 embedding 或 Qdrant |
| 已审核资料过滤 | 复用并收紧入口 | 原检索限制 enabled/ready/approved/非 ai_draft 与活动索引；工作台再核对 `/api/documents`，接受 approved 的 official / user_reviewed / legacy_trusted，保留原来源等级，拒绝 ai_draft / unreviewed |
| `GET /api/evidence/{chunk_id}` | 直接消费 | 对照检索结果核对 chunk/document/content/page/title，保存来源哈希、资料版本与摘录 |
| 文档导入、解析、影子构建、发布与回滚 | 保留现有系统管理 | 工作台只读，不上传资料，不重建索引，不切换活动版本 |
| 前端、对话历史、人工反馈 | 后续可复用 | 首轮接 CLI 和归档，不把工作台事实写入普通聊天记忆；界面接入未实施 |
| `ensure_evidence_citations` | 不可直接用于工程事实 | 当前会把非法 E 编号改成已有编号、给无引用回答追加依据；工程路径绕开 `/api/chat/stream`，直接消费检索原文并调用 Ollama |
| 知识覆盖、问题路由、评测脚本 | 可参考并单独验收 | 其评测对象主要是资料问答；不能替代项目运行证据或 P30 模型独立验收 |
| OCR / Docling / VLM 试点 | 按已有边界复用 | 历史记录表明视觉摘要可作候选，精确图连接和公式未通过；不生成已验证 BSW 关系 |
| `pdf-audit` | 仅复用抽查截图 | 当前为四张页面截图，没有可检索正文或索引，不能算新知识库 |
| Workbench 既有项目/审查/事实门 | 直接复用 | 项目复验、类型化事实、状态和引用保持原有判定权 |

## 这次实际补上的接口

`explain-project` 使用已有知识助手 `/api/search`、`/api/documents`、`/api/evidence`，直接调用 Ollama 结构化生成；不触及知识助手原文件。保存完整请求、原始响应、来源快照、错误与耗时。`verify-model-explanation` 用当前项目闭包及保存的服务响应离线重算，不再次请求模型。

缺口识别明确区分：项目中 failed/blocked/unassessed/skipped 的已记录门、当前上下文未选取的事实、资料查询未请求/失败/无命中、模型缺失/不可用/输出被拒绝，以及语义与人工可用性尚未验收。一次检索无命中不证明整个知识库缺失某类资料；资料说明也不证明项目已经执行通过。

## 现场实际缺口

首次探测（恢复前）：WSL 中没有 Linux `docker` 命令；Windows `docker.exe ps` 返回 Docker Desktop Linux engine 命名管道不存在；Windows 18080 就绪探测超时；本机 11434 无服务。Compose 配置只发布 API 18080 / Web 13000，Ollama 位于内部 backend 网络，默认不发布 11434。

恢复：启动现有 Docker Desktop / 原知识助手部署；核对 `/health/ready` 与已安装模型。工作台应在可达的 backend 网络中使用 `http://ollama:11434`，或由用户部署环境显式提供仅本机可达的 Ollama 地址。不为测试而下载新模型或把内部端口公开到外网。随后已启动原 Docker Desktop 及 Ollama / Qdrant / API 三个现有容器，`/health/ready` 返回 ready，三个服务均 ok；没有重建容器、下载模型或新建知识库。Web 与 worker 保持停止。

实际清单已核实：23 份文档中 15 份 enabled/ready/approved（legacy_trusted）、4 份 AI 草稿 pending、1 份解析 failed、3 份 disabled。三个原模型均存在；资料检索已真实命中原文，模型调用与失败拒绝已实测。现有资料主要是 Simulink / Stateflow / SWC 建模，清单未见独立的 COM/PduR/CanIf/CanTp/Dcm 规范条目；这是目录观察，不等于全文中没有相关内容。

六类冻结题已完成十次真实配对推理，均被校验器拒绝。仍缺：合格模型输出、问题相关事实选择、手册适用版本/问题相关性验证、人工可用性反馈和前端集成。当前协议夹具证明适配器行为，真实开发样例也不能代替独立问题验收。


## Docker 与磁盘核查

- 2026-10-06 Windows C 盘剩约 56.93 GiB，D 盘剩约 46.17 GiB；WSL 显示的约 945 GiB 可用是虚拟文件系统容量，不应当作 Windows 物理剩余空间。
- Docker 共 6 个镜像，逻辑占用约 9.409 GB；其中已有 Ollama 镜像约 8.01 GB，API 517 MB、Web 280 MB、Qdrant 270 MB。基础 Python/Node 镜像共享多数层，不能把显示大小当作可独立回收量。
- 已有模型卷约 5.27 GB，Qdrant 卷约 822.8 MB，业务数据库卷约 26.54 MB，可直接复用。三个模型原始 size 合计约 5.27 GB，这已包含在模型卷统计里，不能重复相加。
- Docling 模型缓存约 597.5 MB 当前无挂载，可在恢复解析试点时复用。其他未挂载 PostgreSQL 49.07 MB、匿名卷约 114.6 MB 等须确认用途，不自动删除。旧 Stateflow 验收容器停止，不作为当前验收或直接重启对象。
- Docker 显示约 761.2 MB 未使用卷空间与约 2.579 MB 可回收镜像独有层；这是工具分类，不等于这些资料无用。本轮未 prune 或删除任何原资产。
- 接入只使用已有镜像（`--pull never`）和已有模型，临时验证容器 `--rm` 自动删除。新增的是工作台代码、wheel 和测试/现场证据，按当前空间无需扩容；最终新增证据大小见本轮完整报告。

## 下一阶段复用检查（2026-10-06）

原 API 镜像缺少汽车报告复验所需 cantools。已验证其 Python 3.12 可只读复用工作台现有 Python 3.12 site-packages，cantools 44.0.0、python-can 4.6.1 导入及 bitstruct 编解码通过；无需安装或构建新镜像。这是当前机器实证，不是任意 Python 环境的兼容保证。

LLM 顶层另有 `python-3.12.10-amd64.exe` 安装包（26,964,224 字节），属于既有 Windows 安装介质；当前解释器可用，不需要再次安装，也未删除。顶层 `.git/.agents/.codex` 为已有仓库/工具配置，未改动，不能算作模型或知识库资产。
