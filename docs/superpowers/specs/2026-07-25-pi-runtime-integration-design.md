# Pi Runtime In-Process 接入设计（Stage 1）

**日期**: 2026-07-25
**状态**: Approved（实施中）
**作者**: jasenwood + ZCode
**关联**:
- 上游：`2026-07-19-agent-orchestration-vision.md`（产品愿景，Stage 1）
- 前置：`2026-07-25-orchestrator-hardening-design.md`（hardening 已就位，PromptParts 设计正确）
- 外部参考：
  - [`earendil-works/pi`](https://github.com/earendil-works/pi)（Pi SDK 源）
  - [`edgehero/pi-dispatch`](https://github.com/edgehero/pi-dispatch)（运营层参考）

---

## 0. 背景

### 0.1 起点

Phase 5 交付了 `@aquan/pi-runtime` 骨架（PiSession/PiRuntime/events/tools 四个 stub）。hardening（2026-07-25）加固了 orchestrator 但 pi-runtime 仍是 stub —— 内层 turn loop 实际不工作。本 spec 把 stub 升级为真实可用的 Pi agent runtime。

### 0.2 目标

让 `@aquan/pi-runtime` 直接 import `@earendil-works/pi-agent-core` + `@earendil-works/pi-ai`，在 in-process 模式下跑通真实 agent turn（用 ZAI/GLM）。**不引入 Docker / 子进程 / Redis**。

### 0.3 范围说明

聚焦：
- ✅ PiRuntime/PiSession 用真 SDK
- ✅ 事件流真实翻译
- ✅ ZAI/GLM provider 配置
- ✅ smoke 测试（真实 LLM 调用）
- ✅ 单元测试（事件翻译表）

不做（明确 out of scope）：
- ❌ MCP tools 桥接（Step 2）
- ❌ Docker 隔离（hardening spec 已决定不做）
- ❌ coding tools（read/bash/edit/write）—— 我们不是 coding agent
- ❌ orchestrator scheduling / 持久化（Stage 2）

---

## 1. Spike 发现（关键事实）

### 1.1 真实包名 + 入口

| 包 | 用途 | 版本 |
|---|---|---|
| `@earendil-works/pi-agent-core` | `Agent` 类、agentLoop、消息/会话 | 0.82.0 |
| `@earendil-works/pi-ai` | LLM provider/model catalog、streaming | 0.82.0 |

入口：
- `@earendil-works/pi-agent-core` → `{ Agent, ... }`
- `@earendil-works/pi-ai/providers/all` → `{ getBuiltinModel, builtinModels, ... }`
- `@earendil-works/pi-ai/api/openai-completions` → `{ streamSimple }`（ZAI 用这个 API）

### 1.2 In-process 可行性：✅ 已验证

spike + 我本机验证：
- Bun 下 `import('@earendil-works/pi-agent-core')` 成功
- `getBuiltinModel('zai', 'glm-4.5-air')` 返回有效 model
- `new Agent({ streamFn, initialState })` 实例化成功，subscribe/prompt/waitForIdle 都在
- 无 native modules；无子进程；纯 ESM TypeScript

### 1.3 真实 API 表面（验证过）

**ZAI/GLM 配置**：
```
provider: "zai"
model id: "glm-4.5-air"
api: "openai-completions"
baseUrl: "https://api.z.ai/api/coding/paas/v4"
auth env: ZAI_API_KEY
```

**Agent 构造**（验证过）：
```typescript
import { Agent } from "@earendil-works/pi-agent-core"
import { getBuiltinModel } from "@earendil-works/pi-ai/providers/all"
import { streamSimple } from "@earendil-works/pi-ai/api/openai-completions"

const model = getBuiltinModel("zai", "glm-4.5-air")
const agent = new Agent({
  streamFn: streamSimple,  // 必需！否则抛 "No default stream function configured"
  initialState: {
    systemPrompt,
    model,
    thinkingLevel: "off",
    tools: [],
    messages: [],
  },
})
```

**关键发现（spike 报告漏了的）**：`AgentOptions.streamFn` 是**必需字段**。`streamSimple` 从 `@earendil-works/pi-ai/api/openai-completions` 导入（ZAI/OpenAI 兼容路径）。

**事件流**：`agent.subscribe((event: AgentEvent, signal) => ...)`，事件类型包括 `agent_start`、`turn_start`、`message_start/update/end`、`tool_execution_start/update/end`、`turn_end`、`agent_end`。

**运行 turn**：`await agent.prompt(text)` 启动；`await agent.waitForIdle()` 等结束；`agent.state.messages.at(-1)` 拿最后 assistant message。

### 1.4 pi-dispatch 对照（再次确认）

pi-dispatch **不直接 import Pi SDK** —— 全靠 Docker 容器内跑 pi CLI。它的 worker `runContainer({ onOutput })` 只管调度/隔离/预算。

我们走不同路径（in-process），但借鉴：
- pi-dispatch 的 `{ code, aborted, turns, tokens }` 返回契约 → 影响 RunOutcome（但 orchestrator 接口已稳定，仅记录）
- prepare-local vs prepare-github 两套 workspace 策略 → 后续 workspace.ts 升级时参考
- 凭证 env 注入不写盘 → pi-runtime 配置遵循

---

## 2. Turn 模型适配（关键设计）

### 2.1 冲突

- **orchestrator 的 agent-runner**：外部循环 `for turn in 1..N: session.runTurn(prompt)`
- **Pi SDK**：内部循环 `agent.prompt(text)` 自己跑到 model 不再调 tool 才停

### 2.2 解决

**orchestrator 接口不变**（保持 `AgentSession.runTurn(): TurnResult`）。所有适配在 PiSession 内部：

- `PiSession.runTurn(prompt)` 调 `agent.prompt(prompt) + waitForIdle()`
- 让 SDK 跑完整内部 loop，返回 `kind: "done"`
- orchestrator 外部 for 循环看到第一次 `done` 就退出

**maxTurns 处理**：
- spike 报告说 SDK 没有直接 `maxTurns` 字段，但有 `AgentLoopConfig.shouldStopAfterTurn(ctx)` 钩子
- 我们的 PiSession 用闭包计数实现"跑 N turn 后停"
- 当前 SDK 版本的 AgentOptions 不直接暴露 loopConfig；如果 SDK 不支持，**回退方案**：用 `AbortController` + 在 subscribe 里监听 `turn_end` 计数，达到 N 就 `agent.abort()`。这是 pi-dispatch 风格的硬停止。

→ **首版用回退方案**（更可控，不依赖 SDK 内部 API 稳定性）。

---

## 3. PromptParts 对接（验证 hardening 设计）

spike 确认：Pi SDK 的 `systemPrompt` 在 `AgentState`，user prompt 通过 `agent.prompt(text)` 传。**正好对应** hardening 时设计的 `buildInitialPromptParts(work): { system, user }`。

### 接口小调整

当前 `AgentRuntime.startSession({ workspacePath, workId, prompt: string })` 只收单个 prompt 字符串。为了正确分离 system/user，扩展接口：

```typescript
// packages/orchestrator/src/runtime.ts
export interface AgentRuntime {
  startSession(opts: {
    workspacePath: string
    workId: string
    prompt: string           // 保留（向后兼容）
    systemPrompt?: string    // 新增（可选）；PiRuntime 优先用
  }): Promise<AgentSession>
  ...
}
```

orchestrator 的 `agent-runner.ts` 检查：如果 `buildInitialPromptParts` 可用，传 `systemPrompt + prompt`（user slot）；否则只传 `prompt`（legacy）。StubRuntime 忽略 `systemPrompt`。

---

## 4. 文件改动

| # | 文件 | 类型 | 内容 |
|---|---|---|---|
| 1 | `docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md` | 新（本文档） |
| 2 | `packages/pi-runtime/package.json` | 改 | + `pi-agent-core@0.82.0` + `pi-ai@0.82.0` |
| 3 | `packages/pi-runtime/src/config.ts` | 新 | `PiRuntimeOptions`：provider/model/apiKey/workspaceRoot/maxTurns |
| 4 | `packages/pi-runtime/src/events.ts` | 改 | 真实 AgentEvent 类型 + 精确翻译表 |
| 5 | `packages/pi-runtime/src/session.ts` | 改 | PiSession.runTurn 调 agent.prompt + subscribe + AbortController maxTurns |
| 6 | `packages/pi-runtime/src/runtime.ts` | 改 | PiRuntime.startSession 实例化真 Agent |
| 7 | `packages/pi-runtime/src/index.ts` | 改 | 导出新 config 类型 |
| 8 | `packages/pi-runtime/src/events.test.ts` | 新 | 翻译表单元测试（不需 LLM） |
| 9 | `packages/pi-runtime/src/smoke.test.ts` | 新 | 真实 LLM smoke（skip if no ZAI_API_KEY） |
| 10 | `packages/pi-runtime/README.md` | 改 | stub → 已实现，记录 env 要求 |
| 11 | `packages/orchestrator/src/runtime.ts` | 改 | startSession 加可选 systemPrompt 字段 |
| 12 | `packages/orchestrator/src/agent-runner.ts` | 改 | 用 PromptParts 构造，分别传 systemPrompt + prompt |

**不改**：core 包（PromptParts 已存在）、server/web、其他。

---

## 5. 事件翻译表

| Pi SDK event | @aquan/core AgentEventKind | detail 取值 |
|---|---|---|
| `agent_start` | （丢弃，元事件） | — |
| `turn_start` | （丢弃，元事件） | — |
| `message_start` | `message` | 空或首字符 |
| `message_update` | `message` | 增量文本 |
| `message_end` | `message` | 完整文本 |
| `tool_execution_start` | `tool_call` | tool 名 |
| `tool_execution_update` | （丢弃，太碎） | — |
| `tool_execution_end` | `tool_result` | tool 名 + 结果摘要 |
| `turn_end` | `turn_end` | 完成 |
| `agent_end` | `turn_end` | 最终（覆盖前面） |
| 其他/error | `error` | 错误消息 |

---

## 6. 测试策略

### 单元测试（无需 LLM）

`events.test.ts`：mock Pi SDK event 对象，验证翻译表。例如：

```typescript
test("message_update → message", () => {
  const e = translatePiEvent({ type: "message_update", payload: { text: "hello" }, timestamp: "..." })
  expect(e.kind).toBe("message")
  expect(e.detail).toContain("hello")
})
```

### Smoke 测试（需 `ZAI_API_KEY`）

`smoke.test.ts`：

```typescript
const hasKey = !!process.env.ZAI_API_KEY

test("hello turn", async () => {
  if (!hasKey) return test.skip("no ZAI_API_KEY")
  const runtime = new PiRuntime({ provider: "zai", model: "glm-4.5-air" })
  const session = await runtime.startSession({
    workspacePath: "/tmp", workId: "smoke",
    prompt: "Say hello in one word.",
    systemPrompt: "You are a test agent. Reply concisely.",
  })
  const result = await session.runTurn("Say hello in one word.")
  expect(result.kind).toBe("done")
  expect(result.events.length).toBeGreaterThan(0)
})
```

CI 无 key 时 test 自动 skip。

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ZAI_API_KEY 未配置 → smoke 无法跑 | `test.skip` 自动跳过；单元测试不依赖 |
| `agent.prompt()` 内部行为未知（compaction 等） | smoke 验证；问题记录到 follow-up |
| Bun 与 Node 22.19 目标兼容性 | spike + 本地验证通过；CI 用 Bun 跑 |
| `streamSimple` 仅适用 openai-completions API | 当前 ZAI/OpenAI/Anthropic 大部分走这个；其他 API 后续按需加 |
| 多个 PiRuntime 实例并发 | ConcurrencyPolicy 默认 1（串行） |

---

## 8. 后续（不在本 spec）

- **Step 2**：MCP client 桥接（让 agent 调 akshare/tushare/internal-store/qlib MCP server）
- **Step 3**：tool spec 暴露（AgentTool 注册，含铁律 3 的工具白名单）
- **Stage 2**：orchestrator scheduling + DuckDB 持久化
- **Stage 3**：dashboard `/orchestration` 三态页
