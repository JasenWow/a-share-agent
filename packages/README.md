# packages/

Bun workspace — TypeScript primary side of the aquan monorepo.

## Packages

| Package | Name | Purpose |
|---|---|---|
| `core/` | `@aquan/core` | Shared types, errors, constants, utils. Dependency-free foundation. |
| `orchestrator/` | `@aquan/orchestrator` | Symphony-like work orchestration engine. Polls trackers, runs work via an `AgentRuntime`, exposes state over HTTP. |
| `pi-runtime/` | `@aquan/pi-runtime` | `AgentRuntime` adapter backed by the Pi SDK. Skeleton only — concrete bindings land in a follow-up spec. |
| `server/` | `@aquan/server` | Hono + Bun API server, Drizzle ORM, multi-DB adapters (sqlite/postgres/duckdb). |
| `web/` | `@aquan/web` | Next.js 15 dashboard (shadcn/ui + Tailwind v4 + recharts). |

## Common commands (from repo root)

```bash
bun install                  # workspace-wide install
bun run dev                  # @aquan/server (3001) + @aquan/web (3000)
bun run build                # build every package
bun run test                 # bun test across all packages
bun run typecheck            # tsc --noEmit across all packages
bun run dep-check            # dependency-cruiser boundary rules
```

## Boundary rules

Enforced by `/.dependency-cruiser.cjs`:

- `@aquan/core` depends on nothing internal.
- `@aquan/{server, web, orchestrator, pi-runtime}` may depend on `@aquan/core`.
- `@aquan/{server, web}` must NOT import each other.
- `@aquan/{orchestrator, pi-runtime}` must NOT depend on `@aquan/{server, web}`.
