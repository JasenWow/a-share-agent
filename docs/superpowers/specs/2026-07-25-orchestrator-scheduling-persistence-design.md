# Orchestrator Scheduling + Persistence（Stage 3）

**日期**: 2026-07-25
**状态**: Approved（实施中）
**作者**: jasenwood + ZCode
**关联**:
- 前置：`2026-07-25-orchestrator-hardening-design.md`（spend/concurrency/injection 已就位）
- 前置：`2026-07-25-pi-runtime-integration-design.md`（PiRuntime 真实接入）
- 前置：`2026-07-25-aquan-cli-design.md`（CLI 工具桥接完成）

---

## 0. 背景

Stage 1 + Step 2 完成后，agent 全链路打通（LLM + 4 个领域 tool + MCP）。但 orchestrator 仍是：
- ❌ **被动**：只有 POST /api/v1/tick 才跑
- ❌ **易失**：StateStore + SpendGuard 全 in-memory，进程重启即丢

Stage 3 升级为**自驱动 + 持久化**。

## 1. Scheduling：in-process cron

不同 tracker 不同节奏。在 orchestrator 内建 Scheduler，不走外部 cron（部署复杂）或任务队列（BullMQ 过重）。

```typescript
interface ScheduleSpec {
  /** 5-field cron（min hour dom mon dow）。例 "0 18 * * 1-5" = 周一到周五 18:00 */
  cron: string
  /** 这个 schedule 触发哪些 tracker（按 name 过滤）；空 = 所有 */
  trackers?: string[]
  /** 显示名 */
  name?: string
}
```

依赖 `cron` npm 包（v4，纯 TS，无 native binding）。

## 2. Persistence：bun:sqlite

- **不用 DuckDB**（需要 @aquan/server adapter，违反 dep-cruiser `no-runtime-to-app`）
- 用 **Bun 内置 `bun:sqlite`**（零新增依赖）
- 独立 .db：`data/orchestrator/state.db`（gitignored）
- 抽出 `IStateStore` interface，现有 StateStore = 内存实现，新增 `SqliteStateStore`
- 新增 `PersistedSpendGuard` extends SpendGuard，写 spend_log，启动重建计数

## 3. Schema

```sql
CREATE TABLE IF NOT EXISTS tracked_works (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  session_id TEXT, turn_count INTEGER,
  started_at TEXT, last_event_at TEXT, last_event TEXT,
  last_message TEXT, state_changed_at TEXT, error TEXT,
  work_item_json TEXT NOT NULL  -- 完整 WorkItem 备份（防 schema 演进）
);

CREATE TABLE IF NOT EXISTS spend_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,  -- tracker name 或 "global"
  at TEXT NOT NULL       -- ISO8601
);
CREATE INDEX IF NOT EXISTS idx_spend_log_at ON spend_log(at);
```

## 4. tick 接口扩展

```typescript
async tick(opts?: { trackerNames?: string[] }): Promise<TickOutcome>
```

Scheduler 用 filter 只跑指定 tracker。

## 5. 关键路径

```typescript
const store = new SqliteStateStore("data/orchestrator/state.db")
const spend = new PersistedSpendGuard(DEFAULT_POLICY.budget, store.db)
const orch = new Orchestrator({
  runtime: new PiRuntime(),
  trackers: [new FactorMiningTracker(), new FreeExplorationTracker()],
  store, policy: { ...DEFAULT_POLICY, budget: spend.policy },
})

orch.start([
  { name: "factor-loop", cron: "*/30 * * * * *", trackers: ["factor-mining"] },
  { name: "daily-exploration", cron: "0 18 * * 1-5", trackers: ["free-exploration"] },
])

process.on("SIGINT", () => { orch.stop(); process.exit(0) })
```

## 6. 范围外

- ❌ DuckDB adapter（SQLite 够当前阶段）
- ❌ 多进程同步（单进程场景）
- ❌ Dashboard 可视化（Stage 4）
- ❌ RetryPolicy with backoff
- ❌ orchestrator 可执行 entry（Stage 4 部署）

## 7. 风险

| 风险 | 缓解 |
|---|---|
| cron v4 API 与文档差异 | 已验证 CronJob.start/stop 工作；运行状态自己跟踪 |
| bun:sqlite 并发锁 | ConcurrencyGate 默认 1（串行），无并发写 |
| SpendGuard 重建性能 | 启动只查最近 31 天；spend_log 可周期清理 |

## 8. 验收

- `bun install` 成功（cron 包）
- `bun test packages/orchestrator/` 全绿
- `bun run dep-check` 0 violations
- spec 文档完整
