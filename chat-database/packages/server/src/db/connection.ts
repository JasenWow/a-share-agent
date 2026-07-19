import { Database } from "bun:sqlite"
import { drizzle } from "drizzle-orm/bun-sqlite"
import * as schema from "./schema"
import path from "path"
import { mkdirSync } from "fs"
import { env } from "../config/env"

const DB_PATH = env.databasePath || path.join(import.meta.dir, "../../data/chat-database.db")

// Ensure the directory exists
mkdirSync(path.dirname(DB_PATH), { recursive: true })

const sqlite = new Database(DB_PATH)

// Enable WAL mode for better concurrent read performance
sqlite.exec("PRAGMA journal_mode = WAL")
sqlite.exec("PRAGMA busy_timeout = 5000")
sqlite.exec("PRAGMA foreign_keys = ON")

export const db = drizzle(sqlite, { schema })
export { sqlite }
