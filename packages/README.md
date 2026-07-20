# packages/

Bun workspace（TS 主体）。重构完成后本目录包含全部 TypeScript/JavaScript 代码。

## 状态

🚧 **建设中** — 见根目录 `RESTRUCTURE-PLAN.md`

当前为空目录。Phase 5 扁平化 `chat-database/` 后填充：

| 包 | 名称 | 来源 |
|---|---|---|
| `core/` | `@aquan/core` | 合并自 `@chat-database/shared` + 新增 work/types/utils |
| `orchestrator/` | `@aquan/orchestrator` | 新建（Symphony-like 编排引擎） |
| `pi-runtime/` | `@aquan/pi-runtime` | 新建（Pi agent runtime 适配层） |
| `server/` | `@aquan/server` | 原 `@chat-database/server`（Hono + Bun） |
| `web/` | `@aquan/web` | 原 `@chat-database/web`（Next.js 15） |

## 命令约定（迁移完成后）

```bash
# 在仓库根目录
bun install
bun run dev          # 启动 web + server
bun run build
bun test
bun run dep-check
```
