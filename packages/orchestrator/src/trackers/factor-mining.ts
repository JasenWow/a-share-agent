/**
 * FactorMiningTracker — daily sedimentation work source.
 *
 * Unlike a queue-backed tracker, this one *generates* one mining WorkItem per
 * local day. There is no "pending hypothesis" queue in internal-store —
 * `factor_library.status='candidate'` is a post-mining state (an agent has
 * already evaluated and persisted a factor awaiting human promote/reject).
 * So the tracker's job is to seed today's exploration theme, and the agent's
 * job is to discover, evaluate, and persist factors via the CLI tools.
 *
 * Daily rotation by weekday gives the agent a different factor family each
 * day, so repeated runs explore orthogonal territory instead of re-deriving
 * the same momentum factor:
 *
 *   Mon  momentum        (price-trend)
 *   Tue  mean-reversion  (counter-trend)
 *   Wed  volatility      (realized / GARCH-like)
 *   Thu  volume          (turnover / liquidity)
 *   Fri  cross-sectional (rank / neutralize)
 *   Sat/Sun  momentum    (fallback — weekend, light)
 *
 * Dedup context: the tracker injects the active factors' expressions into
 * the WorkItem description so the agent can avoid re-mining known factors.
 * The agent is also instructed to persist anything with |IC| > 0.03 as a
 * candidate via `factor register`.
 *
 * State is in-memory + date-stamped id (`factor-mine-YYYY-MM-DD`), mirroring
 * FreeExplorationTracker. The orchestrator's persistent store dedupes across
 * restarts for the same date.
 */

import type { WorkItem, RunState } from "@aquan/core"
import type { Tracker, AgentToolSpec } from "./tracker"
import type { InternalStoreReader } from "../internal-store-reader"

interface TrackedItem {
  item: WorkItem
  state: RunState
  error?: string
}

/** A weekday-indexed mining theme (0=Sun .. 6=Sat). */
interface MiningTheme {
  name: string
  family: string
  /** Seed expressions the agent can vary, not exhaustive. */
  seeds: string[]
}

// getDay(): 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
const DAILY_THEMES: MiningTheme[] = [
  // 0 Sun — fallback to momentum
  { name: "momentum", family: "price-trend", seeds: ["$close/Ref($close,20)-1", "$close/Ref($close,60)-1"] },
  // 1 Mon
  { name: "momentum", family: "price-trend", seeds: ["$close/Ref($close,5)-1", "$close/Ref($close,20)-1", "$close/Ref($close,60)-1"] },
  // 2 Tue
  { name: "mean-reversion", family: "counter-trend", seeds: ["-1*($close/Ref($close,5)-1)", "-1*($close/Ref($close,10)-1)"] },
  // 3 Wed
  { name: "volatility", family: "realized-vol", seeds: ["Std($close/Ref($close,1)-1,20)", "Std($close/Ref($close,1)-1,60)"] },
  // 4 Thu
  { name: "volume", family: "turnover-liquidity", seeds: ["$volume/Mean($volume,20)", "$volume/Ref($volume,5)-1"] },
  // 5 Fri
  { name: "cross-sectional", family: "rank-neutralize", seeds: ["Rank($close/Ref($close,20)-1)"] },
  // 6 Sat — fallback to momentum
  { name: "momentum", family: "price-trend", seeds: ["$close/Ref($close,20)-1", "$close/Ref($close,60)-1"] },
]

export class FactorMiningTracker implements Tracker {
  readonly name = "factor-mining"

  private items = new Map<string, TrackedItem>()

  /**
   * @param reader Optional internal-store reader. When supplied, the tracker
   *               injects active factor expressions into the prompt as dedup
   *               context. Without it, the agent still mines (just without
   *               dedup awareness) — useful for tests.
   */
  constructor(private reader?: InternalStoreReader) {}

  async fetchByStates(states: RunState[]): Promise<WorkItem[]> {
    this.ensureToday()
    const out: WorkItem[] = []
    for (const v of this.items.values()) {
      if (states.includes(v.state)) out.push(v.item)
    }
    return out
  }

  async fetchById(id: string): Promise<WorkItem | undefined> {
    this.ensureToday()
    return this.items.get(id)?.item
  }

  async updateState(id: string, state: RunState, error?: string): Promise<void> {
    const existing = this.items.get(id)
    if (!existing) return
    this.items.set(id, { ...existing, state, error })
  }

  agentToolSpecs(): AgentToolSpec[] {
    // The agent evaluates expressions via qlib and persists via factor.
    // (PiRuntime already wires all four CLI tools regardless; these specs
    // exist for inspection/dashboard use.)
    return [
      {
        name: "qlib",
        description: "Evaluate a factor expression via `aquan qlib eval --expression ... --instruments csi300`.",
        inputSchema: {
          type: "object",
          properties: {
            action: { type: "string", description: "qlib subcommand action, e.g. eval / operators / universe" },
            expression: { type: "string", description: "Qlib factor expression to evaluate." },
          },
          required: ["action"],
        },
      },
      {
        name: "factor",
        description: "Persist a mined factor as a candidate via `aquan factor register --name ... --expression ... --ic ...`.",
        inputSchema: {
          type: "object",
          properties: {
            action: { type: "string", description: "factor subcommand action, e.g. list / candidates / register" },
            name: { type: "string" },
            expression: { type: "string" },
          },
          required: ["action"],
        },
      },
    ]
  }

  /** Create today's mining task if it doesn't exist yet. */
  private ensureToday(): void {
    const today = todayLocalDate()
    const id = `factor-mine-${today}`
    if (this.items.has(id)) return
    const theme = DAILY_THEMES[new Date().getDay()] ?? DAILY_THEMES[1]
    const activeExprs = (() => {
      try {
        return this.reader?.listActiveFactorExpressions() ?? []
      } catch {
        return []
      }
    })()
    this.items.set(id, {
      item: {
        id,
        title: `Factor mining — ${theme.name} (${today})`,
        type: "sedimentation",
        description: buildMiningPrompt(theme, activeExprs),
        labels: ["daily", "mining", theme.name],
        createdAt: new Date().toISOString(),
      },
      state: "pending",
    })
  }
}

/**
 * Build the mining prompt. The description goes into the agent's user slot
 * (prompt-builder.ts), so it is untrusted-by-construction — we only put
 * trusted scaffolding here. Active expressions come from the reader (our
 * own process reading our own DB), so they're safe to include.
 */
function buildMiningPrompt(theme: MiningTheme, activeExpressions: string[]): string {
  const seedLines = theme.seeds.map((s) => `  - ${s}`).join("\n")
  const dedupBlock =
    activeExpressions.length > 0
      ? [
          "",
          "Existing active factor expressions (do NOT duplicate these — vary them or pick different parameters):",
          ...activeExpressions.map((e) => `  - ${e}`),
        ].join("\n")
      : "\n(No existing active factors recorded yet — you're starting fresh.)"
  return [
    `Today's factor family: ${theme.name.toUpperCase()} (${theme.family}).`,
    "",
    "Goal: discover 1-3 factors in this family with predictive power on A-shares,",
    "evaluate them, and persist any with |IC| > 0.03 as candidates.",
    "",
    "Steps:",
    "1. Run `factor list` to see existing active factors (avoid duplicates).",
    "2. Run `qlib operators` and `qlib universe --name csi300` to review available building blocks.",
    "3. Construct 2-3 candidate expressions in this family. Seed ideas:",
    seedLines,
    "4. Evaluate each with `qlib eval --expression '<expr>' --instruments csi300`.",
    "5. For any factor with |IC| > 0.03, persist it via:",
    "   `factor register --name <descriptive_name> --expression '<expr>' \\",
    "      --operators '<comma,sep>' --fields 'close' --ic <val> --icir <val>`.",
    "6. Summarize: what you tried, what stuck, what you persisted.",
    dedupBlock,
    "",
    "Keep the writeup concise.",
  ].join("\n")
}

/** Local-time YYYY-MM-DD (en-CA locale yields ISO order). */
function todayLocalDate(): string {
  return new Date().toLocaleDateString("en-CA")
}
