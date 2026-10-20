# P30 控制面证据计划

状态：**local-accepted**（2026-10-20）；实现已完成本地与隔离安装验证，远端 CI 待本轮实现提交后记录。

## 为什么增加这条路径

复杂解释与官方资料适用性 v1 的固定 `qwen3.5:2b` 结果为 0/4。失败集中在三处：模型选错 read tool、产生非法 finish action、取得多个 observation 后漏引证据。按用户建议，Codex 又对同一 review pack 做了回答对照；该审阅因已经看到 Qwen 输出，明确属于**非盲、非独立、非人工质量门**，只用于定位问题，不能替代原计划的独立 assessment。

本轮不修改、不重跑旧 cohort，而是新增 `agent-evidence-plan-0.1`：调用者在推理前选择解释范围，控制面据此封存固定的只读工具序列；模型只生成一次结构化摘要，不能选择工具、改参数、决定 finish action 或填写 observation ID。所有成功 observation 由控制面按顺序完整附到最终回答。

## 范围与不变量

三个范围映射为确定性步骤：

| scope | 控制面步骤 |
|---|---|
| `project_detail` | `project_query_facts` |
| `reviewed_knowledge` | `knowledge_retrieve_reviewed` |
| `project_and_reviewed_knowledge` | 先项目事实，再已审核资料 |

plan ID 绑定 goal、scope、步骤、参数和边界。result ID 绑定 plan、顶层状态、完整兼容 trace 与边界；顶层 `status` 必须与 trace 一致。离线 verifier 重新验证哈希链、固定步骤前缀、成功时的完整步骤、唯一模型调用和全部 observation 引用。输出路径必须不存在，避免覆盖既有证据。

这条路径仍只读：不写配置、不访问 SocketCAN 或硬件，不产生 approval、decision、claim 或 execution。模型摘要保持 `semantic_status=unassessed`；结构和引用通过不代表文字正确，也不证明资料适用于真实商业工程。

## 操作入口

项目与资料混合解释示例：

```bash
python -m automotive_workbench.cli create-agent-evidence-plan \
  --goal "解释项目阻塞原因，并说明已审核官方资料的适用边界。" \
  --scope project_and_reviewed_knowledge \
  --output output/explanation-plan.json

python -m automotive_workbench.cli verify-agent-evidence-plan \
  output/explanation-plan.json

python -m automotive_workbench.cli run-agent-evidence-plan \
  output/project/bundle/project-report.json \
  output/explanation-plan.json \
  --model qwen3.5:2b \
  --knowledge-url http://127.0.0.1:18081 \
  --knowledge-policy examples/knowledge/p30-vector-official-policy.json \
  --output output/explanation-result.json

python -m automotive_workbench.cli verify-agent-evidence-plan-result \
  output/explanation-plan.json output/explanation-result.json
```

资料 endpoint 与 policy 必须成对提供；选择包含资料的 scope 而 registry 中没有该工具，会在模型摘要前失败。默认最多一次模型调用、两次只读工具调用；预算不足也在推理前拒绝。

## 本地验收证据

- 完整回归 514 tests 通过，2 项按环境条件跳过；新增 4 项专项覆盖固定读取/完整引用、篡改与 scope 拒绝、缺工具/预算的预推理拒绝，以及不覆盖文件和 schema 验证。
- 87 schemas / 79 schema-bound examples / 25 syntax-only examples、Ruff、scoped mypy、CI topology 与 diff check 通过。
- 合成 HTTP 场景实际执行两个计划 read tool、一次结构化模型调用、两个引用，并在服务停止后离线复验；`model_selected_tools=false`。合成服务只证明协议，不是真实模型质量。
- 隔离无依赖 wheel 从临时 site-packages 导入并完成两工程及完整模型协议；wheel SHA-256 为 `3f2c5bc9cb2440c267e38707d4b12e18419177a79baa0744ea2f70eb47733af4`。计划结果 `3684f112047f99275e240fa520050347d90c7bdcdeaf9859b1bedb6169c6e826` 离线复验通过。

## 下一步

先提交、推送并取得本实现 head 自己的远端七 job 结论。远端成功后，再冻结一个全新复杂解释 cohort：Codex 参考答案必须先于任何目标模型输出固定，并清楚标注为 agent-authored reference；随后固定 `qwen3.5:2b` 只运行一次并进行逐项对比。旧 v1 的 0/4 与 pending 独立人工门保持不变。
