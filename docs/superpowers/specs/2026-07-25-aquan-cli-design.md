# aquan-cli 设计：领域聚合 tool 封装

**日期**: 2026-07-25
**状态**: Approved（实施中）
**作者**: jasenwood + ZCode
**关联**:
- 上游：`2026-07-25-pi-runtime-integration-design.md`（pi-runtime 已接入真 SDK）
- 替代：原计划的 MCP 桥接（Step 2）—— 用户反馈"MCP 太笨重，浪费 token"

---

## 0. 背景与动机

### 0.1 起点

Stage 1（pi-runtime in-process 接入）已完成，agent 能跑真 LLM turn，但**没有工具可调**（只有纯对话）。

原计划 Step 2 是 MCP 桥接：TS 写 MCP client，把 4 个 server 的 44 个工具直接暴露给 agent。

### 0.2 为什么换方向

用户反馈："用 mcp 太笨重了，很浪费 token 能封装一层 tool cli 吗"

具体问题：
1. **token 浪费**：44 个工具的 schema（每个含 name/description/inputSchema 字段）塞进 system prompt，每次请求都付这个固定开销
2. **协议开销**：MCP HTTP 握手（initialize + notifications/initialized + session）+ SSE 解析 + JSON-RPC 包装，每次调用都走这套
3. **agent 认知负担**：44 个细粒度工具（`stock_zh_a_hist` / `stock_financial_report_sina` / `record_experiment_step`）名称混乱、语义重叠，agent 选错工具的概率高

### 0.3 目标

用 Python CLI + 领域聚合 tool 让 agent 高效调数据：
- agent 只看 **4 个 tool**（不是 44 个）
- 每次调用是**一次 subprocess**（不是 MCP HTTP 往返 + SSE）
- 输出**紧凑文本表格**（不是 raw JSON，省 token）

---

## 1. 架构

```
Agent (Pi SDK)
    │
    │ 4 个 AgentTool:
    │   stock / factor / experiment / qlib
    │
    ▼
cli-runner.ts (Bun.spawn)
    │
    │ spawn: aquan <domain> <action> --args...
    │
    ▼
aquan-cli (Python console script)
    │
    │ 4 个 subparser:
    │   stock → akshare/tushare MCP
    │   factor → internal-store MCP
    │   experiment → internal-store MCP
    │   qlib → qlib MCP
    │
    ▼
aquan.utils.http.call (复用现有 MCP HTTP client)
    │
    │ POST tools/call
    │
    ▼
4 个 MCP servers (不动)
```

**关键设计**：
- **MCP servers 完全不动**（dashboard / 其他消费者仍用 MCP）
- **CLI 是 agent 友好的额外层**（不是 MCP 的替代）
- **复用 `aquan.utils.http`**（不重写 MCP 握手）

---

## 2. 领域划分

| CLI 子命令 | 覆盖 MCP server | 工具数 | 主要 actions |
|---|---|---|---|
| `aquan stock <action>` | akshare + tushare | 17 | spot, hist, daily, financial, income, balancesheet, cashflow, fina_indicator, concept, concept_detail, index_cons, index_weight, index_daily, northbound, lhb, health |
| `aquan factor <action>` | internal-store (factor 部分) | 5 | list, register, deprecate, candidates, promote |
| `aquan experiment <action>` | internal-store (实验部分) | 12 | list, record, steps, latest_step, best, failures, transitions, episode_summaries, similar_states, transition_matrix, backtest_results, portfolio |
| `aquan qlib <action>` | qlib | 5 | init, data, eval, operators, universe |

**共 39 个 action 覆盖全部 44 个 MCP 工具**（部分工具合并，如 query_cache 不直接暴露）。

---

## 3. 文件改动

### Python 侧（`python/aquan/cli/`）

| 文件 | 内容 |
|---|---|
| `main.py` | 顶层 subparser + dispatch；注册 console script entry |
| `_format.py` | 输出格式化（list[dict] → 紧凑表格 / JSON） |
| `_mcp_proxy.py` | 薄包装：调 `aquan.utils.http.call` + 错误友好化 |
| `stock.py` | stock 领域：action → MCP tool 映射 + 参数构造 |
| `factor.py` | factor 领域 |
| `experiment.py` | experiment 领域 |
| `qlib.py` | qlib 领域 |
| `tests/test_format.py` | 格式化测试 |
| `tests/test_stock.py` | stock action 映射测试（mock MCP） |

### TS 侧（`packages/pi-runtime/`）

| 文件 | 内容 |
|---|---|
| `cli-runner.ts` | `runCli(domain, action, args)`：Bun.spawn + 超时 + 解码 |
| `cli-tools.ts` | 4 个领域 AgentTool（typebox schema） |
| `runtime.ts` | startSession 注册 4 个 cli tool |
| `cli-tools.test.ts` | schema + execute 单元测试 |
| `smoke.test.ts` | 加"agent 调 CLI"测试 |

---

## 4. 核心代码形状

### Python: `aquan stock hist --code 600519 --start 20240101`

```bash
$ aquan stock hist --code 600519 --start 20240101 --end 20240601

date        open    close    high    low     volume      pct_chg
2024-01-02  1715.0  1685.5   1719.0  1680.0  23456       +0.8%
2024-01-03  1685.5  1690.2   1695.0  1680.0  19876       +0.3%
...（最多 20 行，--limit 控制）
```

`--json` 切换完整 JSON 输出。

### Python: `stock.py`

```python
ACTION_TO_MCP = {
    "spot":        ("akshare", "stock_zh_a_spot",       {"code": "symbol"}),
    "hist":        ("akshare", "stock_zh_a_hist",       {"code":"symbol","period":"period","start":"start_date","end":"end_date","adjust":"adjust"}),
    "daily":       ("tushare", "daily",                 {"code":"ts_code","start":"start_date","end":"end_date","limit":"limit"}),
    "financial":   ("akshare", "stock_financial_abstract", {"code":"symbol","indicator":"indicator"}),
    "income":      ("tushare", "income",                {"code":"ts_code","period":"period"}),
    # ...
}

def run(args) -> int:
    source, tool, param_map = ACTION_TO_MCP[args.action]
    params = {mcp_key: getattr(args, cli_key) for cli_key, mcp_key in param_map.items() if getattr(args, cli_key) is not None}
    result = mcp_call(source, tool, params)
    print(format_output(result, json_out=args.json))
    return 0
```

### TS: 4 个领域 tool

```typescript
// packages/pi-runtime/src/cli-tools.ts
export const stockTool: AgentTool = {
  name: "stock",
  label: "A-share market data",
  description: `Query A-share stock data. Actions:
    spot [code] — realtime quote
    hist --code --start --end --period --adjust — historical OHLCV
    daily --code --start --end — tushare daily
    financial --code --indicator — financial abstract
    income/balancesheet/cashflow --code --period — financial statements
    concept / concept_detail --id — concept board
    index_cons --symbol / index_weight --code — index constituents
    index_daily --symbol — index history
    northbound — northbound net flow
    lhb --start --end — dragon-tiger list
    health — data source health`,
  parameters: Type.Object({
    action: Type.String({ description: "One of: spot, hist, daily, financial, ..." }),
    code: Type.Optional(Type.String()),
    start: Type.Optional(Type.String()),
    end: Type.Optional(Type.String()),
    // ... 通用字段
  }),
  execute: async (_id, params) => {
    const out = await runCli("stock", params.action, params)
    return { content: [{ type: "text", text: out }], details: { tool: "stock" } }
  },
}
```

### TS: `cli-runner.ts`

```typescript
export async function runCli(domain, action, args, opts = {}): Promise<string> {
  const cliArgs = [domain, action]
  for (const [k, v] of Object.entries(args)) {
    if (v != null && k !== "action") {
      cliArgs.push(`--${snakeCase(k)}`, String(v))
    }
  }
  const proc = Bun.spawn(["aquan", ...cliArgs], {
    cwd: opts.cwd ?? REPO_ROOT,
    stdout: "pipe", stderr: "pipe",
    env: { ...process.env },
  })
  // 30s timeout, return stdout or formatted stderr
}
```

---

## 5. 关键决策

### 5.1 CLI 输出格式

默认**紧凑表格**（agent 友好）：
```
date        close    pct_chg
2024-01-02  1685.5   +0.8%
```

`--json` 切换完整 JSON。表格限制默认 20 行（`--limit` 控制）。

### 5.2 Console script entry（避免 uv run 开销）

`python/pyproject.toml` 加：
```toml
[project.scripts]
aquan = "aquan.cli.main:main"
```

`uv sync` 后 `aquan` 直接在 PATH（不用 `uv run`，省 ~1s 启动）。

TS 侧 `Bun.spawn(["aquan", ...])`，但需要 PATH 包含 python/.venv/bin。两种方案：
- **(A)** TS 显式 `Bun.spawn(["uv", "run", "--directory", "python", "aquan", ...])` —— 简单，有 ~1s 开销
- **(B)** TS 配置 `PATH` 加 `python/.venv/bin`，直接 `aquan` —— 快，需配置

→ **首版选 A**（简单可靠），后续按需切 B。

### 5.3 安全（hardening 铁律 3）

`runCli` 只接受预定义 domain（stock/factor/experiment/qlib）。Bun.spawn 命令固定为 `aquan <domain>`，不暴露通用 shell。args 经 typebox schema 校验。

**永不暴露**：bash / exec / read_file / write_file / merge_pr / commit / modify_ci（Pi SDK 不注册这些 tool）。

---

## 6. 测试

### Python 单元测试

`tests/test_format.py`：
- `format_table([{a:1,b:2},{a:3,b:4}])` → 含 "a" "b" "1" "2" "3" "4"
- 空列表 → "(no rows)"
- 长 cell 截断

`tests/test_stock.py`：
- mock `mcp_call`，验证 `stock hist --code X --start Y` → 调 `akshare.stock_zh_a_hist({symbol:X, start_date:Y})`
- 未知 action → argparse 报错

### TS 单元测试

`cli-tools.test.ts`：
- 4 个 tool 的 name/description 校验
- mock runCli，验证 execute 正确调用 + 返回 content

`cli-runner.test.ts`：
- mock Bun.spawn，验证参数拼装（camelCase → kebab-case）

### Smoke 测试

需 `ZAI_API_KEY` + MCP server 运行：
```typescript
test("agent calls stock tool", async () => {
  const runtime = new PiRuntime()
  const session = await runtime.startSession({
    ..., prompt: "What's the close price of 600519 yesterday? Use the stock tool."
  })
  const result = await session.runTurn("...")
  expect(result.events.some(e => e.kind === "tool_call" && e.detail === "stock")).toBe(true)
})
```

---

## 7. 范围外

- ❌ 逐工具暴露（只做 4 个领域聚合）
- ❌ TS 端 MCP client（不需要，CLI 走 Python MCP client）
- ❌ CLI 输出流式（首版同步）
- ❌ 工具调用持久化（Stage 2）
- ❌ REPL 交互式模式
- ❌ 修 tushare import-time raise（独立任务）

---

## 8. 风险

| 风险 | 缓解 |
|---|---|
| `uv run` 每次启动开销 ~1s | 首版接受；后续切 console script + PATH |
| CLI action 漏某个 MCP 工具 | 首版覆盖常用；不常用的按需加 |
| MCP server down → CLI crash | `_mcp_proxy` 捕获 + 输出友好错误文本（exit 0 + stderr message） |
| Bun.spawn 超时 | 默认 30s，可配 |
| agent 传错 action 名 | typebox schema 校验 + CLI argparse choices 双重保险 |

---

## 9. 验收

- `cd python && uv run aquan stock hist --code 600519 --start 20240101` 输出表格（需 MCP server 跑）
- `cd python && uv run aquan factor list` 输出表格
- `cd python && uv run pytest aquan/cli/tests/` 全绿
- `bun test packages/pi-runtime/` 全绿
- `bun run dep-check` 0 violations
- agent 在 smoke test 中成功调 stock tool
