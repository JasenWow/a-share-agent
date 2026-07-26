import { describe, expect, test, beforeEach, afterEach } from "bun:test"
import { Database } from "bun:sqlite"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { InternalStoreReader } from "./internal-store-reader"

/**
 * Build a throwaway SQLite file that mirrors internal-store's factor_library
 * schema, seed it with rows, and point the reader at it.
 */
function makeTempDb(seed: Array<Record<string, unknown>>): { path: string; cleanup: () => void } {
  const dir = mkdtempSync(join(tmpdir(), "aquan-reader-"))
  const path = join(dir, "meta.db")
  const db = new Database(path, { create: true })
  db.run(`
    CREATE TABLE IF NOT EXISTS factor_library (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      name          TEXT NOT NULL,
      expression    TEXT NOT NULL,
      hypothesis    TEXT,
      operators     TEXT NOT NULL,
      data_fields   TEXT NOT NULL,
      ic            REAL,
      icir          REAL,
      turnover      REAL,
      sharpe        REAL,
      max_drawdown  REAL,
      universe      TEXT,
      period        TEXT,
      walk_forward  TEXT,
      status        TEXT DEFAULT 'active',
      source_experiment_id INTEGER,
      created_at    TEXT DEFAULT (datetime('now'))
    );
  `)
  for (const row of seed) {
    const cols = Object.keys(row)
    const placeholders = cols.map(() => "?").join(", ")
    db.run(
      `INSERT INTO factor_library (${cols.join(", ")}) VALUES (${placeholders});`,
      ...cols.map((c) => (row as Record<string, unknown>)[c]),
    )
  }
  db.close()
  return { path, cleanup: () => rmSync(dir, { recursive: true, force: true }) }
}

describe("InternalStoreReader", () => {
  let dir: string
  let path: string
  let cleanup: () => void

  beforeEach(() => {
    const made = makeTempDb([
      {
        name: "momentum_20d",
        expression: "close/Ref(close,20)-1",
        hypothesis: "20-day momentum",
        operators: '["div","sub","ref"]',
        data_fields: '["close"]',
        ic: 0.05,
        icir: 0.42,
        turnover: 0.3,
        sharpe: 1.1,
        max_drawdown: 0.18,
        universe: "csi300",
        period: "2020-2024",
        walk_forward: null,
        status: "active",
        source_experiment_id: null,
        created_at: "2026-07-20T00:00:00Z",
      },
      {
        name: "reversal_5d",
        expression: "-1*(close/Ref(close,5)-1)",
        hypothesis: "5-day reversal",
        operators: '["mul","sub"]',
        data_fields: '["close"]',
        ic: 0.04,
        icir: 0.35,
        turnover: 0.5,
        sharpe: 0.9,
        max_drawdown: 0.22,
        universe: "csi300",
        period: "2020-2024",
        walk_forward: '{"confidence":0.7,"rationale":"stable in backtest"}',
        status: "candidate",
        source_experiment_id: 3,
        created_at: "2026-07-25T00:00:00Z",
      },
      {
        name: "vol_20d",
        expression: "Std(close/Ref(close,1)-1,20)",
        hypothesis: "20-day realized vol",
        operators: '["std","sub","ref"]',
        data_fields: '["close"]',
        ic: 0.02,
        icir: 0.18,
        turnover: 0.4,
        sharpe: 0.6,
        max_drawdown: 0.3,
        universe: "csi500",
        period: "2020-2024",
        walk_forward: '{"confidence":0.4,"rationale":"weak signal"}',
        status: "candidate",
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
    ])
    path = made.path
    cleanup = made.cleanup
  })

  afterEach(() => cleanup())

  test("listCandidates returns candidate rows, newest first, with parsed walk_forward", () => {
    const reader = new InternalStoreReader(path)
    const cands = reader.listCandidates()
    expect(cands).toHaveLength(2)
    // ORDER BY id DESC → vol_20d (id 3) before reversal_5d (id 2)
    expect(cands[0].name).toBe("vol_20d")
    expect(cands[0].confidence).toBe(0.4)
    expect(cands[0].rationale).toBe("weak signal")
    expect(cands[1].name).toBe("reversal_5d")
    expect(cands[1].confidence).toBe(0.7)
    expect(cands[1].sourceExperimentId).toBe(3)
  })

  test("listCandidates parses JSON-array operators/data_fields", () => {
    const reader = new InternalStoreReader(path)
    const [first] = reader.listCandidates()
    expect(first.operators).toEqual(["std", "sub", "ref"])
    expect(first.dataFields).toEqual(["close"])
  })

  test("listActiveFactorExpressions returns only active expressions", () => {
    const reader = new InternalStoreReader(path)
    const exprs = reader.listActiveFactorExpressions()
    expect(exprs).toEqual(["close/Ref(close,20)-1"])
  })

  test("candidateCount counts only candidate rows", () => {
    const reader = new InternalStoreReader(path)
    expect(reader.candidateCount()).toBe(2)
  })

  test("isAvailable returns true when DB + table exist", () => {
    const reader = new InternalStoreReader(path)
    expect(reader.isAvailable()).toBe(true)
  })

  test("methods return empty / false when DB file does not exist", () => {
    const reader = new InternalStoreReader("/nonexistent/path/to/meta.db")
    expect(reader.listCandidates()).toEqual([])
    expect(reader.listActiveFactorExpressions()).toEqual([])
    expect(reader.candidateCount()).toBe(0)
    expect(reader.isAvailable()).toBe(false)
  })

  test("methods return empty when DB exists but factor_library table is missing", () => {
    // Fresh DB with no schema.
    const dir2 = mkdtempSync(join(tmpdir(), "aquan-empty-"))
    const emptyPath = join(dir2, "empty.db")
    const db = new Database(emptyPath, { create: true })
    db.run("CREATE TABLE unrelated (x INTEGER);")
    db.close()
    try {
      const reader = new InternalStoreReader(emptyPath)
      expect(reader.listCandidates()).toEqual([])
      expect(reader.listActiveFactorExpressions()).toEqual([])
      expect(reader.candidateCount()).toBe(0)
      expect(reader.isAvailable()).toBe(false)
    } finally {
      rmSync(dir2, { recursive: true, force: true })
    }
  })

  test("walk_forward with non-confidence shape degrades gracefully", () => {
    const made = makeTempDb([
      {
        name: "legacy_factor",
        expression: "x",
        hypothesis: "",
        operators: '["x"]',
        data_fields: '["close"]',
        ic: null,
        icir: null,
        turnover: null,
        sharpe: null,
        max_drawdown: null,
        universe: "",
        period: "",
        walk_forward: '{"windows":[2020,2021,2022]}', // legacy walk-forward windows
        status: "candidate",
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
    ])
    try {
      const reader = new InternalStoreReader(made.path)
      const [cand] = reader.listCandidates()
      expect(cand.confidence).toBeNull()
      expect(cand.rationale).toBeNull()
    } finally {
      made.cleanup()
    }
  })
})

describe("InternalStoreReader — promote / reject write path", () => {
  test("promoteCandidate moves candidate → active", () => {
    const made = makeTempDb([
      {
        name: "mom20",
        expression: "close/Ref(close,20)-1",
        hypothesis: "",
        operators: '["div"]',
        data_fields: '["close"]',
        ic: 0.05, icir: 0.4, turnover: 0.3, sharpe: 1.1, max_drawdown: 0.18,
        universe: "csi300", period: "2020-2024",
        walk_forward: '{"confidence":0.7,"rationale":"ok"}',
        status: "candidate",
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
    ])
    try {
      const reader = new InternalStoreReader(made.path)
      // candidate id is 1 (first autoincrement row)
      const res = reader.promoteCandidate(1, "alice", "good IC")
      expect(res.ok).toBe(true)
      expect(res.targetStatus).toBe("active")
      expect(res.reviewer).toBe("alice")
      expect(res.notes).toBe("good IC")
      // No longer in candidate list
      expect(reader.listCandidates()).toHaveLength(0)
      // Now in active expressions
      expect(reader.listActiveFactorExpressions()).toContain("close/Ref(close,20)-1")
    } finally {
      made.cleanup()
    }
  })

  test("promoteCandidate on non-candidate returns not-candidate error", () => {
    const made = makeTempDb([
      {
        name: "active_factor",
        expression: "x",
        hypothesis: "",
        operators: '["x"]',
        data_fields: '["close"]',
        ic: null, icir: null, turnover: null, sharpe: null, max_drawdown: null,
        universe: "", period: "",
        walk_forward: null,
        status: "active", // already active — can't promote
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
    ])
    try {
      const reader = new InternalStoreReader(made.path)
      const res = reader.promoteCandidate(1)
      expect(res.ok).toBe(false)
      expect(res.error).toBe("not-candidate")
      expect(res.currentStatus).toBe("active")
    } finally {
      made.cleanup()
    }
  })

  test("promoteCandidate on missing id returns not-found", () => {
    const made = makeTempDb([])
    try {
      const reader = new InternalStoreReader(made.path)
      const res = reader.promoteCandidate(999)
      expect(res.ok).toBe(false)
      expect(res.error).toBe("not-found")
    } finally {
      made.cleanup()
    }
  })

  test("rejectCandidate sets rejected (no status guard)", () => {
    const made = makeTempDb([
      {
        name: "c1",
        expression: "expr1",
        hypothesis: "",
        operators: '["x"]',
        data_fields: '["close"]',
        ic: null, icir: null, turnover: null, sharpe: null, max_drawdown: null,
        universe: "", period: "",
        walk_forward: null,
        status: "candidate",
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
      {
        name: "a1",
        expression: "expr2",
        hypothesis: "",
        operators: '["x"]',
        data_fields: '["close"]',
        ic: null, icir: null, turnover: null, sharpe: null, max_drawdown: null,
        universe: "", period: "",
        walk_forward: null,
        status: "active", // reject works on active too
        source_experiment_id: null,
        created_at: "2026-07-26T00:00:00Z",
      },
    ])
    try {
      const reader = new InternalStoreReader(made.path)
      // Reject the candidate (id 1)
      const r1 = reader.rejectCandidate(1, "low IC", "bob")
      expect(r1.ok).toBe(true)
      expect(r1.targetStatus).toBe("rejected")
      expect(r1.reason).toBe("low IC")
      expect(r1.reviewer).toBe("bob")
      // Reject the active one (id 2) — no guard
      const r2 = reader.rejectCandidate(2)
      expect(r2.ok).toBe(true)
      // Neither appears in candidates nor active anymore
      expect(reader.listCandidates()).toHaveLength(0)
      expect(reader.listActiveFactorExpressions()).toHaveLength(0)
    } finally {
      made.cleanup()
    }
  })

  test("write methods return unavailable when DB missing", () => {
    const reader = new InternalStoreReader("/nonexistent/meta.db")
    expect(reader.promoteCandidate(1).error).toBe("unavailable")
    expect(reader.rejectCandidate(1).error).toBe("unavailable")
  })
})
