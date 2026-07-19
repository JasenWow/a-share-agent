# Architecture

## Structure

```
packages/shared/src/   # types, constants (no runtime, no deps on server/web)
packages/server/src/   # Hono API, bun:sqlite (Drizzle), AI agent, DB adapters
  ├── adapters/        # DatabaseAdapter interface, factory, pool-manager, postgresql, sqlite
  ├── ai/              # providers.ts, tools/
  ├── config/          # env.ts (single source of truth for env vars)
  ├── db/              # connection.ts, schema.ts, migrate.ts, seed.ts
  ├── lib/             # auth.ts, agent-prompt.ts, system-schema.ts
  ├── middleware/       # auth.ts, error-handler.ts
  └── routes/          # auth, chat, databases, database-query, charts, dashboards, admin-users, ai
packages/web/          # Next.js 15 App Router, Tailwind v4, shadcn/ui
  ├── app/(main)/      # authenticated pages: agent, data-studio, custom-charts, databases, dashboard/[id], admin/users
  ├── api-clients/     # typed fetch wrappers
  └── components/      # ai-elements/, chart/, chat/, dashboard/, sidebar/, ui/
```

## Dependency Flow

```
server → shared ← web
web --HTTP--> server
```

dep-check enforces: server↔web no imports, shared→nothing.

## Where to Put Code

| Add a... | Location |
|----------|----------|
| shared type | `shared/src/types/<name>.ts` → export from `types/index.ts` |
| server route | `server/src/routes/<name>.ts` → mount in `app.ts` + `authMiddleware` |
| web page | `web/app/(main)/<name>/page.tsx` |
| API client | `web/api-clients/<name>.ts` |
| DB adapter | `server/src/adapters/<name>.ts` → register in `factory.ts` + `shared/types/database.ts` |
| AI provider | `server/src/ai/providers.ts` + `shared/constants/ai-providers.ts` + `shared/types/ai.ts` |
| env var | `server/src/config/env.ts` + `.env.example` |
