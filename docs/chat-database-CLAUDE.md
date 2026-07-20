# CLAUDE.md

Bun monorepo. `packages/shared` (types), `packages/server` (Hono+SQLite), `packages/web` (Next.js 15).

## Commands

```bash
bun run dev          # server (:3001) + web (:3000)
bun run db:seed      # admin user (admin@example.com / 123456)
bun test             # run all tests
bun test --watch     # watch mode
bun run dep-check    # architecture rules
```

## Contributing Docs

- [contributing/architecture.md](contributing/architecture.md) — structure, deps, where to put code
- [contributing/api-guide.md](contributing/api-guide.md) — routes, auth, ownership
- [contributing/database-guide.md](contributing/database-guide.md) — schema, adapters, pool manager
- [contributing/ai-integration.md](contributing/ai-integration.md) — providers, streaming, tools
- [contributing/testing.md](contributing/testing.md) — TDD workflow, mock patterns

## Rules

- Env vars: read via `packages/server/src/config/env.ts` only, never `process.env` directly
- Passwords: never in API responses
- Ownership: `createdBy === user.id || user.isAdmin` on GET single / PUT / DELETE
- System DB: SELECT/PRAGMA only (`/^\s*(SELECT|PRAGMA)/i`)
- PUT: only set fields `!== undefined`, never nullify missing fields
- API clients: try/catch + `response.ok` check, return error-shaped fallback
- New types: `packages/shared/src/types/<name>.ts` → re-export from `types/index.ts`
- Migrations: modify `schema.ts` → `db:generate` → review → `db:migrate`
- TDD: test first, `bun test` + `bun run dep-check` must pass before commit
