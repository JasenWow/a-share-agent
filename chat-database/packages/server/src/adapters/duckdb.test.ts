import { describe, test, expect, beforeAll, afterAll } from "bun:test"
import { DuckDBInstance } from "@duckdb/node-api"
import { DuckDBAdapter } from "./duckdb"
import { createAdapter } from "./factory"
import type { ExternalDbConfig } from "@chat-database/shared"
import { mkdirSync, rmSync } from "fs"
import { join } from "path"
import { tmpdir } from "os"

/**
 * DuckDB adapter integration tests.
 *
 * Creates a real DuckDB file with test data, then exercises the adapter.
 * Requires @duckdb/node-api native binding (Node-API addon).
 * If Bun runtime fails to load the binding, this test will fail —
 * that's the R4 risk from the integration spec. Run under Node as fallback.
 */

const TEST_DIR = join(tmpdir(), `chatdb-duckdb-test-${Date.now()}`)
const TEST_DB = join(TEST_DIR, "test.duckdb")

beforeAll(async () => {
  mkdirSync(TEST_DIR, { recursive: true })
  // Seed a test DuckDB file with a small table
  const instance = await DuckDBInstance.create(TEST_DB)
  const conn = await instance.connect()
  try {
    await conn.run(`
      CREATE TABLE factors (
        id INTEGER,
        name VARCHAR,
        ic DOUBLE,
        universe VARCHAR
      )
    `)
    await conn.run(`
      INSERT INTO factors VALUES
        (1, 'momentum_20d', 0.045, 'csi300'),
        (2, 'value_pe', -0.032, 'csi500')
    `)
  } finally {
    await conn.close()
  }
})

afterAll(() => {
  try {
    rmSync(TEST_DIR, { recursive: true, force: true })
  } catch {
    // best effort
  }
})

describe("DuckDBAdapter", () => {
  test("testConnection returns true on valid file", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    expect(await adapter.testConnection()).toBe(true)
    await adapter.close()
  })

  test("testConnection returns false on missing file", async () => {
    const adapter = new DuckDBAdapter("/nonexistent/path/test.duckdb")
    expect(await adapter.testConnection()).toBe(false)
    await adapter.close()
  })

  test("executeQuery returns rows", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    const result = await adapter.executeQuery("SELECT * FROM factors ORDER BY id")
    expect(result.rowCount).toBe(2)
    expect(result.columns).toEqual(["id", "name", "ic", "universe"])
    expect(result.rows[0]).toMatchObject({ name: "momentum_20d", universe: "csi300" })
    await adapter.close()
  })

  test("executeQuery handles empty result", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    const result = await adapter.executeQuery("SELECT * FROM factors WHERE id < 0")
    expect(result.rowCount).toBe(0)
    expect(result.rows).toEqual([])
    await adapter.close()
  })

  test("executeQuery aggregates", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    const result = await adapter.executeQuery(
      "SELECT universe, COUNT(*) AS n, AVG(ic) AS avg_ic FROM factors GROUP BY universe ORDER BY universe"
    )
    expect(result.rowCount).toBe(2)
    await adapter.close()
  })

  test("executeQuery throws on invalid SQL", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    await expect(adapter.executeQuery("SELECT FROM nonexistent_table")).rejects.toThrow(
      /DuckDB query error/
    )
    await adapter.close()
  })

  test("getSchema returns table definitions", async () => {
    const adapter = new DuckDBAdapter(TEST_DB)
    const schema = await adapter.getSchema()
    const factorsTable = schema.find((t) => t.name === "factors")
    expect(factorsTable).toBeDefined()
    expect(factorsTable!.columns.map((c) => c.name)).toEqual(["id", "name", "ic", "universe"])
    const idCol = factorsTable!.columns.find((c) => c.name === "id")
    expect(idCol!.type.toLowerCase()).toContain("integer")
    await adapter.close()
  })

  test("read-only mode rejects writes", async () => {
    const adapter = new DuckDBAdapter(TEST_DB, true) // readOnly=true
    await expect(adapter.executeQuery("INSERT INTO factors VALUES (3, 'x', 0.1, 'csi300')")).rejects
      .toThrow()
    await adapter.close()
  })
})

describe("factory integration", () => {
  test("createAdapter returns DuckDBAdapter for type=duckdb", async () => {
    const config: ExternalDbConfig = {
      type: "duckdb",
      filePath: TEST_DB,
    }
    const adapter = createAdapter(config)
    expect(adapter).toBeInstanceOf(DuckDBAdapter)
    expect(await adapter.testConnection()).toBe(true)
    await adapter.close()
  })
})
