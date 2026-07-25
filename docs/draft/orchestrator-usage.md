# Orchestrator 使用说明

> 如何启动 agent 编排系统、让它干活、在 dashboard 看状态。

## 1. 前置准备

### 1.1 安装依赖

```bash
# Python 侧（MCP servers + ETL + aquan CLI）
cd python
uv sync
cd ..

# TS 侧（orchestrator + web dashboard）
bun install
```

### 1.2 配置 .env

复制 `.env.example` 为 `.env`，填入 LLM 凭证：

```bash
cp .env.example .env
```

`.env` 关键字段（按你的 LLM provider 选一组）：

**MiniMax（推荐，中国可用，已验证）**：
```
AQUAN_PROVIDER=minimax-cn
AQUAN_MODEL=MiniMax-M2.7
AQUAN_API_KEY=sk-cp-...        # 从 https://platform.minimaxi.com 拿
AQUAN_BASE_URL=https://api.minimaxi.com/anthropic/v1
```

**ZAI / GLM（默认，中国可用）**：
```
AQUAN_PROVIDER=zai
AQUAN_MODEL=glm-4.5-air
AQUAN_API_KEY=...              # 从 https://z.ai 拿
# AQUAN_BASE_URL 不需要（用 Pi SDK 内置）
```

**OpenAI / Anthropic / Google**：把 `AQUAN_PROVIDER` 改成对应 id（`openai` / `anthropic` / `google`），`AQUAN_MODEL` 改成对应模型名。查看所有支持的 provider：

```bash
cd packages/pi-runtime
bun -e "import('@earendil-works/pi-ai/providers/all').then(m=>console.log(m.builtinModels().getProviders().map(p=>p.id).join('\n')))"
```

可选：填 `TUSHARE_TOKEN`（让 tushare-server 能拉历史数据）。

### 1.3 启动 MCP servers

agent 通过 4 个 MCP server 访问数据。至少启动你需要的那几个（每个一个终端）：

```bash
cd python

# akshare — 实时行情（默认端口 8000）
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000

# tushare — 历史数据 + 财报（需 TUSHARE_TOKEN，端口 8001）
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001

# internal-store — 缓存 + 实验 + 因子库（端口 8002）
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# qlib — Qlib 量化引擎（可选，端口 8003）
uv run uvicorn mcp-servers.qlib-server.server:mcp_app --port 8003
```

验证 MCP 通：
```bash
uv run aquan experiment list    # 应输出 internal-store 里的实验
uv run aquan stock health       # 应输出 akshare 数据源健康状态
```

## 2. 跑通最小 agent（无 orchestrator）

最快验证 LLM + CLI tools 端到端工作：

```bash
# 加载 .env（zsh 示例；bash 用 source）
export $(grep -v '^#' .env | xargs)

# 跑 MiniMax smoke（单次 LLM 调用）
bun test packages/pi-runtime/src/minimax-smoke.test.ts

# 跑 MiniMax + CLI tools smoke（agent 真调 experiment 工具）
# 需要 internal-store MCP 在 :8002 跑着
bun test packages/pi-runtime/src/minimax-cli-smoke.test.ts
```

预期输出（CLI smoke）：
```
[minimax-cli-smoke] events: 18, tool_calls: 1, message: 
There are 3 experiments currently in the system.
(pass) PiRuntime + MiniMax + CLI tools > agent calls the experiment tool and reports results
```

如果看到 "aquan executable is not found"，cli-runner 会自动 fallback 到 `uv run --directory python aquan`，确保 PATH 不影响。

## 3. 启动 orchestrator（自驱动循环 + 持久化）

orchestrator 是独立 Bun 进程，负责：
- 按 cron 节奏轮询 tracker
- 跑 agent work（spend cap + 并发控制）
- 把状态写 SQLite（重启不丢）
- 在 :3010 暴露 HTTP API 给 dashboard

**目前还没有可执行 entry**（Stage 5 的任务），所以用 inline 方式跑：

```bash
# 加载 .env
export $(grep -v '^#' .env | xargs)

# 启动 orchestrator（StubRuntime + 内存 tracker，用于演示）
bun -e '
  import { Orchestrator, MemoryTracker, StubRuntime, startOrchestratorServer } from "@aquan/orchestrator";

  const tracker = new MemoryTracker();
  tracker.seed([{
    id: "demo-1", title: "Demo work", type: "sedimentation",
    description: "List current experiments and summarize.", createdAt: new Date().toISOString(),
    state: "pending",
  }]);

  const orch = new Orchestrator({
    runtime: new StubRuntime(),  // 换成 new PiRuntime() 跑真 LLM
    trackers: [tracker],
  });

  orch.start([{ cron: "*/30 * * * * *", name: "demo-loop" }]);
  startOrchestratorServer(orch, 3010);
  console.log("orchestrator on http://localhost:3010 (Ctrl+C to stop)");
'
```

要跑**真 LLM agent**，把 `new StubRuntime()` 换成 `new PiRuntime()`（从 `@aquan/pi-runtime` import）。会读 `.env` 里的 `AQUAN_*` 配置。

## 4. 启动 dashboard（看三态视图）

```bash
# 另一个终端
bun run dev
```

打开 http://localhost:3000/orchestration —— 看到：
- **顶部**：6 个 state count 卡（running / retrying / blocked / pending / done / failed）
- **左侧**：按 state 分组的 work 卡片（id / turn / last message / error）
- **右侧**：Spend 预算条 + Scheduler 状态（每个 schedule 的 fire/error 数）

页面每 2 秒 SWR poll 一次 `/api/v1/state`。orchestrator 没启动时显示"orchestrator unreachable"红色提示。

手动触发一次 tick（调试用）：点页面右上角 "Run tick now" 按钮，或：
```bash
curl -X POST http://localhost:3010/api/v1/tick
```

## 5. API 参考

orchestrator :3010 暴露的 HTTP 端点：

| 方法 + 路径 | 作用 |
|---|---|
| `GET /api/v1/state` | 全部状态：counts + 各 state 的 work 列表 + spend + schedules |
| `GET /api/v1/work/:id` | 单个 work item 详情 |
| `GET /api/v1/schedules` | scheduler 状态（每个 cron spec 的 fire/error 计数）|
| `GET /api/v1/spend` | spend 计数 + caps + 窗口边界 |
| `POST /api/v1/tick?trackers=name1,name2` | 手动触发一次 tick（可选过滤 tracker）|
| `GET /healthz` | liveness probe |

## 6. CLI 工具参考

agent 通过 4 个领域 tool 调数据（底层都走 `aquan` Python CLI → MCP）。你也可以手动调：

```bash
cd python

# 行情
uv run aquan stock spot --code 600519              # 实时报价
uv run aquan stock hist --code 600519 --start 20240101 --end 20240601
uv run aquan stock daily --code 600519.SS --limit 10
uv run aquan stock northbound                       # 北向资金
uv run aquan stock health                           # 数据源健康

# 因子
uv run aquan factor list                            # 列出活跃因子
uv run aquan factor list --status deprecated        # 含废弃的
uv run aquan factor register --name momentum_30d --expression 'close/ref(close,30)-1' --operators 'div,sub,ref' --fields 'close'

# 实验
uv run aquan experiment list
uv run aquan experiment best --top 5                # 按 final_nav 排序
uv run aquan experiment backtests                   # 回测历史
uv run aquan experiment portfolio --portfolio default

# Qlib
uv run aquan qlib operators                         # 可用算子
uv run aquan qlib universe --name csi300            # 沪深 300 成分
uv run aquan qlib eval --expression 'Mean($close, 20)' --instruments csi300
```

加 `--json` 切换完整 JSON 输出。加 `--limit N` 限制表格行数。

## 7. 故障排查

### "orchestrator unreachable"（dashboard 红色提示）
- orchestrator :3010 没启动 → 按 §3 启动
- 端口被占 → 改 `ORCHESTRATOR_PORT` 或 `startOrchestratorServer(orch, 别的端口)`
- 浏览器跨域 → 默认无 CORS 限制，应该不会有这问题

### "aquan executable not found"（agent 反馈）
- cli-runner 会自动 fallback 到 `uv run --directory python aquan`
- 如果还是失败，确认 `cd python && uv sync` 跑过（生成 `.venv/bin/aquan`）

### "MCP server unreachable"（CLI 报 503 或连接失败）
- 系统代理劫持 localhost：已修，CLI 对 loopback URL 自动绕过 proxy
- MCP server 没启动 → 按 §1.3 启动
- 端口冲突 → 改 `.env` 里的 `*_PORT`

### MiniMax 报 401 / 403
- `AQUAN_API_KEY` 没填或填错
- `AQUAN_BASE_URL` 路径错：MiniMax CN 用 `https://api.minimaxi.com/anthropic/v1`（注意 `/v1`）
- key 过期 → 重新去 platform.minimaxi.com 申请

### agent 不调 tool
- 检查 `disableCliTools` 是否被设为 true（默认 false）
- model 上下文不够：减小 `maxTurnsPerRun` 或换更小模型
- prompt 不明确：在 description 里明说"Use the X tool"

## 8. 当前限制

| 限制 | 说明 | 计划 |
|---|---|---|
| 无 orchestrator 可执行 entry | 只能 `bun -e` 跑 | Stage 5：`packages/orchestrator/src/entry.ts` |
| Tracker 是 stub | FactorMining/FreeExploration 返回空 | 后续：真接 internal-store / 定时生成任务 |
| 无 auth | orchestrator :3010 任何人可访问 | localhost-only 部署足够；多用户时加 |
| 无 SSE | dashboard 2s poll | 后续如需更实时改 SSE |
| tushare import-time raise | 缺 TUSHARE_TOKEN 时 server.py 直接崩 | 改 lazy raise（独立任务）|
