# Database Guide

## System DB

- `bun:sqlite` + Drizzle ORM, `packages/server/src/db/connection.ts`
- WAL mode, 5s busy timeout, foreign keys ON
- Path: `DATABASE_PATH` env var or `data/chat-database.db`

## Schema (`db/schema.ts`)

`users` (email unique, password bcrypt, isAdmin), `external_databases` (connection configs, FK→users), `custom_charts` (SQL+chart JSON, FK→external_databases+users), `custom_dashboards` (render JSON, FK→users).

## Migrations

`schema.ts` → `bun run db:generate` → review SQL in `drizzle/` → `bun run db:migrate`.

## Adapters

```ts
interface DatabaseAdapter {
  executeQuery(sql: string): Promise<QueryResult>
  getSchema(): Promise<TableSchema[]>
  testConnection(): Promise<boolean>
  close(): Promise<void>
}
```

- Factory: `adapters/factory.ts` — `postgresql` → `PostgreSQLAdapter` (pg.Pool), `sqlite` → `SQLiteAdapter` (bun:sqlite readonly)
- Pool manager: `adapters/pool-manager.ts` — singleton cache keyed `db_${id}`, deduplicates concurrent gets, `invalidate()` on config change

## SQL Injection Prevention

PRAGMA table names escaped via `escapeSqliteIdentifier()` in `lib/system-schema.ts` — rejects `;`, `"`, `'`, `\`, escapes internal `"` → `""`.

## System Query Restriction

Enforced in `routes/database-query.ts` and `ai/tools/database-query.ts`: system DB only allows SELECT/PRAGMA. External DBs unrestricted (prompt-level SELECT-only).
