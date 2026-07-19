import type { DatabaseAdapter } from "./types"
import type { ExternalDbConfig } from "@chat-database/shared"
import { createAdapter } from "./factory"

const adapterCache = new Map<string, DatabaseAdapter>()
const pendingRequests = new Map<string, Promise<DatabaseAdapter>>()

export const poolManager = {
  async getAdapter(databaseId: string): Promise<DatabaseAdapter> {
    const key = `db_${databaseId}`
    const cached = adapterCache.get(key)
    if (cached) return cached

    // Deduplicate concurrent requests for the same key
    const pending = pendingRequests.get(key)
    if (pending) return pending

    const promise = this._createAdapter(databaseId, key)
    pendingRequests.set(key, promise)
    try {
      return await promise
    } finally {
      pendingRequests.delete(key)
    }
  },

  async _createAdapter(databaseId: string, key: string): Promise<DatabaseAdapter> {
    // Dynamically import db to avoid circular deps at module level
    const { db } = await import("../db/connection")
    const { externalDatabases } = await import("../db/schema")
    const { eq } = await import("drizzle-orm")

    const row = await db
      .select()
      .from(externalDatabases)
      .where(eq(externalDatabases.id, Number(databaseId)))
      .get()

    if (!row) {
      throw new Error(`Database ${databaseId} not found`)
    }

    const config: ExternalDbConfig = {
      type: (row.dbType as "postgresql" | "sqlite") || "postgresql",
      host: row.host,
      port: row.port,
      database: row.database,
      username: row.username,
      password: row.password,
      sslEnabled: row.sslEnabled,
      filePath: row.filePath || undefined,
    }

    const adapter = createAdapter(config)
    adapterCache.set(key, adapter)
    return adapter
  },

  async invalidate(databaseId: string): Promise<void> {
    const key = `db_${databaseId}`
    const adapter = adapterCache.get(key)
    if (adapter) {
      await adapter.close()
      adapterCache.delete(key)
    }
  },

  async closeAll(): Promise<void> {
    for (const adapter of adapterCache.values()) {
      await adapter.close()
    }
    adapterCache.clear()
  },
}
