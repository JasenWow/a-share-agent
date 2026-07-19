import { app } from "./app"
import { poolManager } from "./adapters/pool-manager"
import { sqlite } from "./db/connection"

const port = Number(process.env.SERVER_PORT) || 3001
const host = process.env.SERVER_HOST || "localhost"

console.log(`🚀 Server starting on http://${host}:${port}`)

Bun.serve({
  port,
  hostname: host,
  fetch: app.fetch,
})

// Graceful shutdown
async function shutdown() {
  console.log("Shutting down gracefully...")
  await poolManager.closeAll()
  sqlite.close()
  process.exit(0)
}

process.on("SIGINT", shutdown)
process.on("SIGTERM", shutdown)
