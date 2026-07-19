# Testing (TDD)

Bun built-in test runner. Files: `*.test.ts` co-located with source.

## TDD Cycle

Write failing test → confirm fail → implement → confirm pass → refactor → `bun test` + `bun run dep-check` green before commit.

## Test Layers

**Layer 1 — Pure functions** (no mocks): type guards in `shared/types/`, formatters/parsers in `server/lib/`.

**Layer 2 — Adapters**: `createMockAdapter(overrides?)` from `server/src/test-setup.ts`.

**Layer 3 — Routes**: Hono `app.request("/path")` for HTTP simulation. Mock deps:

```ts
import { mock } from "bun:test"
mock.module("../lib/auth", () => ({
  validateSession: async () => ({ id: 1, email: "test@test.com", name: "Test", isAdmin: false }),
  // ...other exports
}))
mock.module("../adapters/pool-manager", () => ({
  poolManager: { getAdapter: async () => createMockAdapter(), invalidate: async () => {}, closeAll: async () => {} },
}))
```

## Conventions

`describe()` by function, `test()` by behavior. No test-only exports — only export genuinely useful functions.
