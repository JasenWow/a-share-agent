# 阶段三（起点）：Candidate 审阅面板 — promote/reject 闭环

## 背景（探索结论）

agent 把因子持久化为 `factor_library.status='candidate'`，但人在 UI 上**无法操作**这些候选——半自动 feedback loop 断在审阅环节。闭环这条断链是最务实的阶段三起点：自包含、薄覆盖、是工具级 approve/reject 的铺垫。

关键发现：
- **promote/reject MCP 工具已就位**（server.py:779/825），CLI 动作也齐（factor.py ACTION_MAP）
- **InternalStoreReader 严格只读**（`readonly: true`），无写路径
- **orchestrator 只有一个 POST**（`/api/v1/tick`），无 promote/reject 端点
- **审计缺口**：reviewer/notes/reason 不存 DB 列（server.py 注释 "lives in agent logs"），promote/reject 后即丢
- **写路径选项**：(a) 进程内 bun:sqlite 写 vs (b) spawn CLI vs (c) 浏览器直连 MCP。**选 (a)**——代码最少、复用 reader 接线、无 IPC 开销；需在 TS 重实现"仅 candidate 可 promote"守卫

## 目标

dashboard 上看到 candidate 列表 → 点 Promote（→ active）或 Reject（→ rejected）→ 列表实时刷新。闭环 agent 产出 → 人审阅 → active 库更新（active 库反过来喂给 FactorMiningTracker 做去重上下文，整个 feedback loop 通了）。

## 文件改动

| 文件 | 类型 | 内容 |
|---|---|---|
| `packages/orchestrator/src/internal-store-reader.ts` | 改 | 加 `promoteCandidate(id, reviewer?, notes?)` + `rejectCandidate(id, reason?, reviewer?)` 写方法；开读写连接 + busy_timeout + WAL pragma；重实现 candidate 守卫 |
| `packages/orchestrator/src/internal-store-reader.test.ts` | 改 | 加 promote/reject 测试（candidate→active、非 candidate promote 拒绝、reject 任意状态、审计字段不持久但日志记）|
| `packages/orchestrator/src/http.ts` | 改 | 加 `POST /api/v1/factors/:id/promote` + `POST /api/v1/factors/:id/reject`；JSON body 收 reviewer/notes/reason；写后日志记审计 |
| `packages/orchestrator/src/http.test.ts` | 改 | 加 promote/reject 端点测试 |
| `packages/web/api-clients/orchestration.ts` | 改 | 加 promoteCandidate/rejectCandidate 函数 |
| `packages/web/components/orchestration/candidate-panel.tsx` | 新 | candidate 列表表格 + 每行 Promote/Reject 按钮 + 审阅 dialog（输 reviewer/reason）|
| `packages/web/app/(main)/orchestration/page.tsx` | 改 | 加 CandidatesPanel（或单独 /candidates 页，倾向 panel 嵌入现有页右侧 aside）|

## 核心设计

### 1. InternalStoreReader 写方法

```typescript
// internal-store-reader.ts
promoteCandidate(factorId: number, reviewer?: string, notes?: string): PromoteResult {
  // 开读写连接（非 readonly），设 busy_timeout + WAL
  const db = new Database(this.dbPath)
  db.run("PRAGMA busy_timeout = 5000")
  try {
    // 重实现 MCP 守卫：仅 status='candidate' 可 promote
    const row = db.query("SELECT status FROM factor_library WHERE id = ?").get(factorId)
    if (!row) return { ok: false, error: "not-found" }
    if (row.status !== "candidate") return { ok: false, error: "not-candidate", currentStatus: row.status }
    db.run("UPDATE factor_library SET status = 'active' WHERE id = ?", factorId)
    return { ok: true, factorId, reviewer, notes }
  } finally { db.close() }
}

rejectCandidate(factorId: number, reason?: string, reviewer?: string): RejectResult {
  // reject 无状态守卫（MCP 行为一致）——任意状态可 reject
  // ... UPDATE status = 'rejected'
}
```

**审计**：reviewer/notes/reason 进返回值（调用方可见），但**不写 DB**（与 MCP 一致，避免 schema 迁移）。HTTP handler 层 `console.log` 记审计行（"promote factor 7 by alice: good IC"）。

**并发**：busy_timeout=5000ms 处理与 MCP 的写冲突；WAL 减少锁竞争。每次操作开短连接（与 MCP 的 per-call connect 模式一致）。

### 2. HTTP 端点

```
POST /api/v1/factors/:id/promote    body: { reviewer?, notes? }  → { ok, factorId, reviewer?, notes? }
POST /api/v1/factors/:id/reject     body: { reason?, reviewer? }  → { ok, factorId, reason?, reviewer? }
```

reader 不可用时返回 `{ ok: false, error: "unavailable" }`（503）。非 candidate promote 返回 `{ ok: false, error: "not-candidate" }`（409）。handler 读 JSON body（triggerTick 用 query string 无 body；这里用 body 因为 reviewer/notes 是文本）。

### 3. Web CandidatePanel

```
┌─ Candidates (3) ──────────────────────────┐
│ name            expression       ic  conf  │
│ momentum_20d    close/Ref(...)-1  0.05 0.7 │ [Promote] [Reject]
│ reversal_5d     -1*(close/...)   -0.04 0.6 │ [Promote] [Reject]
│ vol_20d         Std(...)         0.02  0.4 │ [Promote] [Reject]
└───────────────────────────────────────────┘
```

- 用 shadcn Table 渲染列表
- Promote 按钮 `variant="default"`，Reject `variant="destructive"`
- 点 Promote → 直接调（可选弹 dialog 输 notes）；点 Reject → 弹 dialog 输 reason
- 成功后 `toast.success` + `mutate()` 刷新 SWR（镜像 triggerTick 模式）
- 嵌入 `/orchestration` 页右侧 aside（SpendPanel/SchedulerPanel 下方），或做成独立 `/candidates` 页——**倾向 panel**，因为 candidate 数量少且与 orchestration 上下文强相关

### 4. reviewer 身份

当前无 auth，reviewer 字段可选。UI 默认填 `"anonymous"` 或留空。后续加 auth 时从 session 取。

## 测试策略

- **reader 写方法**（临时 DB）：promote candidate→active、promote 非 candidate→not-candidate 错、promote 不存在→not-found、reject 任意状态→rejected、reject 后 listCandidates 不再返回
- **HTTP**：POST promote/reject 返回形状、守卫错误码、reader 不可用 503
- **typecheck**：web 新文件过 tsc
- **端到端**：internal-store + orchestrator → seed candidate → POST promote → GET candidates 不再返回它 → GET factors/candidates source=internal-store

## 范围外

- ❌ 工具调用级 approve/reject（阶段三后续，需 agent 可中断）
- ❌ DB schema 加 reviewer/notes 列（避免迁移，日志层审计够用）
- ❌ auth / 127.0.0.1 绑定（保持与 /tick 一致的无 auth 模型，单独加固时做）
- ❌ 独立 /candidates 页（先 panel 嵌入，必要时再拆）

## 验收

- `bun run test` 全绿（含新 reader 写方法 + http 测试）
- `bun run dep-check` 0 violations
- `bun run typecheck`（web）无新错误
- 端到端：seed candidate → UI/POST promote → candidate 消失、active 库 +1