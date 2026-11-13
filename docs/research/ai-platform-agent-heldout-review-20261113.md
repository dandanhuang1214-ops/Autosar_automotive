# AI 平台只读 Agent 0.1：新题留出结果

题目与判据在模型调用前以提交 `9245adb96e90933c0e0ad762407e848219473da5` 封存于 [留出题集](ai-platform-agent-heldout-20261113.json)，题集 SHA-256 `7cbe3d982471b87faeec5c6444de4ca2099f784444b8f1571fc54715f7e54b35`。这是同一图谱快照、同一 ECUC 报告上的**新问题留出**，不是独立外部数据集。每个模型只完整运行一次，原始结果和 trace 在本机忽略目录 `output/ai-agent-cohort-20261113/`；没有按失败结果改题或重跑。

| 题目 | 冻结所需工具 / 目标片段 | DeepSeek `deepseek-flash` | 本地 `qwen3.5:2b` |
|---|---|---|---|
| Rte_IRead 快照 | `graph_search` / `chunk.week07.K050` | 工具正确、完成；取到实际存在的 `chunk.did-rte-runtime.K013`，冻结目标 ID 不存在 | 动作查询为空，拒绝；0 工具 |
| 静态项目与 CAN 运行边界 | `project_evidence` | 工具正确、完成；报告哈希精确匹配 | 选了不可用的图谱工具且查询为空，拒绝；0 工具 |
| Rte_Write 与 CAN 发出/接收边界 | `project_evidence` + `graph_search` / `chunk.week07.K064` | 两工具正确、完成；取到实际存在的 `chunk.did-rte-runtime.K028` 和 K007，冻结目标 ID 不存在 | 非法 JSON 动作，拒绝；0 工具 |

**勘误（2026-11-13）**：冻结时把实体 `K050`、`K064` 误写成 `chunk.week07.K050`、`chunk.week07.K064`；两者在固定图谱中均不存在。实体到来源的真实映射是 `K050 → chunk.did-rte-runtime.K013`、`K064 → chunk.did-rte-runtime.K028`，DeepSeek 实际取到了这两个片段。因此按原错误 ID 机械比较得到的 **1/3 不能作为检索失败或质量未通过的证据**；保留原冻结题、原始结果和原机械分数，不事后改题重跑。DeepSeek 工具集与完成态为 3/3；实际选中片段包含快照在 Runnable 内不变、稳定不代表硬件新鲜，以及 RTE 提交不证明 CAN 发出或远端接收的相关文字。Codex 非盲核对三条回答与实际观测相符，但这是开发诊断。用户在收到开发题与留出题两个审阅包后回复“我觉得是可用的”，记录为**两包回答的整体可用性反馈**；没有逐题逐句依据标注，正式内容审阅仍 pending。

六条保存 trace 均通过哈希链、引用与工具清单离线复验。DeepSeek 三题的图谱 SHA 为 `c5ec7ffa61365ee0d179911b846dd26799eab014ea675a0b701facabd642489f`，两次项目报告 SHA 均为 `8d82549975c0d91eece9de658cd6e1016edb7d3eea34ea0aa38c738276b35460`。三题 trace ID 为 `a7df97ecced6483188e1ba13205c4cfd`、`4fb3eef4eea749bd8c2713ec8e503fa7`、`ee29c13d8cc444dc94c357f4fd452607`；本地三题为 `c4728b8461b445aeb568c023555f53a9`、`521d77da96464b95b026c9421f12f0f4`、`be3e44e7d14746b2983bf0383d9741a5`。原始汇总文件 SHA 分别为 `1e3c863fc5b284ca78d0afc962aad820f9b7d7e4437774a4ba01b9765afac3f9`、`a9960aa32555c1d3e39dcbc9460eb7fe08a0628c10fe14623a619148f4fa3214`。

DeepSeek 合计 5,440 输入 token（缓存命中 0）、530 输出 token、7 次模型/4 次工具调用，完整耗时约 5.4 / 10.8 / 13.0 秒。按 2026-11-13 查阅的 [DeepSeek 官方价格表](https://api-docs.deepseek.com/quick_start/pricing/) 的 Flash 缓存未命中与输出单价估算，此三题费用约 **US$0.00113～0.00227**（离峰至高峰）；这是 token 估算，非账户账单。本地 2b 合计 780 输入/90 输出 token、3 次模型/0 次工具调用；首题约 42.7 秒含本机冷加载，后两题约 1.3 / 1.1 秒。Agent 仍是同步接口，未测首字时延。

下一质量门：独立审阅者逐句核对两组已保存的云端回答及选中片段；用**新版本与新题集**重建存在性已核验的来源判据，并处理本地 2b 动作协议，不改本次冻结题或重跑本次结果。现有工具编排和证据完整性结论与模型内容质量分别记录；项目静态通过不代表 CFG 生成、CAN 运行或物理 ECU 实测。

工程实现提交 `6f785aa7494b493216411032aa493875f10b89ad` 对应 [core-ci run `43351005891`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/43351005891) head 一致、七 job success。冻结题集和 runner 扩展提交 `9245adb96e90933c0e0ad762407e848219473da5` 对应 [core-ci run `43351815636`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/43351815636) head 一致、七 job success。这两项仅证明实现/运行器回归，不替代留出来源门或内容审阅。
