import type { ExternalDbConfig } from "@chat-database/shared"
import type { DatabaseAdapter } from "./types"
import { PostgreSQLAdapter } from "./postgresql"
import { SQLiteAdapter } from "./sqlite"

export function createAdapter(config: ExternalDbConfig): DatabaseAdapter {
  switch (config.type) {
    case "postgresql":
      return new PostgreSQLAdapter({
        host: config.host || "localhost",
        port: config.port || 5432,
        database: config.database || "",
        username: config.username || "",
        password: config.password || "",
        sslEnabled: config.sslEnabled || false,
      })
    case "sqlite":
      return new SQLiteAdapter(config.filePath || "")
    default:
      throw new Error(`Unsupported database type: ${(config as any).type}`)
  }
}
