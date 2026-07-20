import { Database } from "bun:sqlite"
import path from "path"
import { readFileSync, readdirSync } from "fs"

const DB_PATH = process.env.DATABASE_PATH || path.join(import.meta.dir, "../../data/chat-database.db")
const MIGRATIONS_DIR = path.join(import.meta.dir, "../../drizzle")

console.log("Running migrations...")

const sqlite = new Database(DB_PATH)
sqlite.exec("PRAGMA journal_mode = WAL")
sqlite.exec("PRAGMA foreign_keys = ON")

// Create migrations tracking table
sqlite.exec(`
  CREATE TABLE IF NOT EXISTS __drizzle_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
  )
`)

// Read and apply migration files
const migrationFiles = readdirSync(MIGRATIONS_DIR)
  .filter(f => f.endsWith(".sql"))
  .sort()

for (const file of migrationFiles) {
  const hash = file.replace(".sql", "")
  const applied = sqlite.prepare("SELECT id FROM __drizzle_migrations WHERE hash = ?").get(hash)

  if (!applied) {
    console.log(`Applying migration: ${file}`)
    const sql = readFileSync(path.join(MIGRATIONS_DIR, file), "utf-8")
    sqlite.exec(sql)
    sqlite.prepare("INSERT INTO __drizzle_migrations (hash) VALUES (?)").run(hash)
    console.log(`Applied: ${file}`)
  } else {
    console.log(`Already applied: ${file}`)
  }
}

sqlite.close()
console.log("Migrations completed successfully!")
