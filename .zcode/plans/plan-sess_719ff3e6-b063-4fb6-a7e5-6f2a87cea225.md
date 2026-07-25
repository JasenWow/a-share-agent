# Stage 4：Dashboard `/orchestration` 三态页

## 目标

让用户从浏览器实时看到 agent 编排状态：running / retrying / blocked / done 列表 + spend 统计 + scheduler 状态。Symphony 三态视图的 aquan 版。

**web 直连 orchestrator :3010**（不经 @aquan/server 代理，简化架构）。orchestrator 的 `/api/v1/state` 已就位，只需 web 侧加消费层。

## 架构

```
Browser → @aquan/web (/orchestration 页)
              │
              │ SWR poll (refreshInterval: 2s)
              ▼
        orchestrator :3010
              │
              │ /api/v1/state
              │ /api/v1/work/:id
              │ /api/v1/schedules (新增)
              │ /api/v1/spend (新增)
              ▼
        SqliteStateStore (data/orchestrator/state.db)
```

## 文件改动

| 文件 | 类型 | 内容 |
|---|---|---|
| `packages/orchestrator/src/http.ts` | 改 | 加 `/api/v1/schedules`（scheduler.status()）+ `/api/v1/spend`（spend.getStats()）端点 |
| `packages/orchestrator/src/presenter.ts` | 改 | statePayload 加 spend stats 字段（从 orch.spend.getStats()）|
| `packages/web/api-clients/orchestration.ts` | 新 | API client：getState/getWork/getSchedules + SWR keys |
| `packages/web/api-clients/config.ts` | 改 | 加 ORCHESTRATOR_URL（默认 http://localhost:3010）|
| `packages/web/app/(main)/orchestration/page.tsx` | 新 | 三态主页面（counts + per-state lists）|
| `packages/web/components/orchestration/state-overview.tsx` | 新 | counts 卡片（running/retrying/blocked/done/failed）|
| `packages/web/components/orchestration/work-card.tsx` | 新 | 单 WorkItem 卡片（id/title/turn/lastEvent/error）|
| `packages/web/components/orchestration/work-list.tsx` | 新 | 按 state 分组的 work 列表 |
| `packages/web/components/orchestration/scheduler-panel.tsx` | 新 | scheduler 状态（schedules + fireCount/errorCount）|
| `packages/web/components/orchestration/spend-panel.tsx` | 新 | spend 统计（daily/weekly/monthly + caps）|
| `packages/web/components/sidebar/app-sidebar.tsx` | 改 | 加 Orchestration 导航项 |

## 核心组件形状

### `state-overview.tsx`（counts 卡片）

```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Running │ │Retrying │ │ Blocked │ │  Done   │
│    3    │ │    1    │ │    0    │ │   42    │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

每个卡片用 RUN_STATE_META（已在 @aquan/core/constants）的 tone 上色。

### `work-card.tsx`（单 work 卡）

```
┌──────────────────────────────────────────┐
│ ● factor-mine-2026-07-25-momentum        │  ← id + state dot
│ turn 7/20 · 1.2k tok · started 10:32     │  ← 进度
│ last: "found IC=0.08, registering..."    │  ← lastMessage
└──────────────────────────────────────────┘
```

blocked 的加显眼 error 提示。

### `scheduler-panel.tsx`

```
Schedules
─────────────────────────────
factor-loop        */30 * * * * *   fired 142 · 0 err
daily-exploration  0 18 * * 1-5     fired 5   · 1 err (last: ...)
```

### `spend-panel.tsx`

```
Spend (last 24h: 12 / 50 · weekly: 80/200 · monthly: 300/800)
[████████░░░░░░░░░░░░] daily cap progress bar
```

## 数据流

`page.tsx` 用 SWR 双 poll：
```typescript
const { data: state } = useSWR(getOrchestrationStateKey(), getOrchestrationState, { refreshInterval: 2000 })
const { data: schedules } = useSWR(getOrchestrationSchedulesKey(), getOrchestrationSchedules, { refreshInterval: 5000 })
```

页面布局：
1. 顶部：StateOverview（counts 卡片）
2. 中间左：WorkList（三态分组，可展开）
3. 中间右：SpendPanel + SchedulerPanel（侧边栏）
4. 底部：recent（最近 20 条状态变化）

## orchestrator HTTP 扩展

`/api/v1/schedules` 返回 `scheduler.status()` 数组。
`/api/v1/spend` 返回 `orch.spend.getStats()` + policy caps。
`/api/v1/state` 在 statePayload 里加 `spend` 字段（合并 spend + caps）。

## 测试策略

- **orchestrator HTTP 测试**：用 Bun.serve 启动，fetch /api/v1/schedules + /api/v1/spend 验证返回
- **web 组件**：Bun test 渲染组件（mock SWR 数据）—— 但 Next.js 组件用 bun test 测比较重，首版**不写组件单测**，靠手动验证 + typecheck
- **typecheck**：所有新 TS 文件过 tsc

## 范围外

- ❌ WebSocket/SSE 实时推送（SWR 2s poll 够用）
- ❌ 单 work 详情页（首版卡片够展示）
- ❌ agent event 流可视化（后续）
- ❌ 手动触发 tick 的 UI（保留 HTTP POST /api/v1/tick 即可）
- ❌ auth（orchestrator :3010 当前无 auth，localhost only）

## 验收

- `bun run test` 全绿（含新 orchestrator HTTP 测试）
- `bun run dep-check` 0 violations
- `bun run typecheck`（web 包）无新错误
- 手动：启动 orchestrator（StubRuntime + MemoryTracker + seed work），web `bun run dev`，访问 `/orchestration` 看到三态

## 后续

- 实际启动 orchestrator entry（Stage 4 部署脚本）
- SSE 替代 SWR poll（如果 2s 不够实时）
- 单 work 详情页（点击 work-card 展开 turn 历史）