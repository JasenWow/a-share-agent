/**
 * Four domain-aggregated AgentTools backed by the `aquan` Python CLI.
 *
 * Each tool is one Pi SDK AgentTool whose execute() spawns `aquan <domain>
 * <action> --args...` and returns the CLI's stdout (table/JSON) as the
 * tool result text. The agent sees four tools, not the 44 raw MCP tools.
 *
 * Why a fixed-shape schema per domain instead of dynamic discovery:
 *   - Stable schemas let the provider cache the system prompt + tool list
 *     across turns (Pi SDK requirement).
 *   - The CLI is the source of truth for which actions exist; surfacing
 *     them as a free-text `action` string in the description is enough
 *     for the model to choose correctly.
 *   - Adding a new action needs no TS change, only a Python-side update.
 *
 * Safety:
 *   - `action` is a free string at the schema level, but the CLI's argparse
 *     choices reject unknown actions. The agent cannot run arbitrary code.
 *   - runCli never spawns a shell; argv goes directly to Bun.spawn.
 */

import type { AgentTool } from "@earendil-works/pi-agent-core"
import { Type, type TSchema } from "typebox"
import { runCli } from "./cli-runner"

/** Shared shape: every domain tool takes an `action` + a bag of params. */
function domainParams(extra: Record<string, TSchema> = {}) {
  return Type.Object({
    action: Type.String({
      description: "The domain action to run. See this tool's description for the list.",
    }),
    ...extra,
  })
}

/** Common optional args every domain accepts. */
const COMMON_ARGS: Record<string, TSchema> = {
  code: Type.Optional(Type.String({ description: "Stock/index code (e.g. 600519, 000300, sh000300)." })),
  start: Type.Optional(Type.String({ description: "Start date YYYYMMDD." })),
  end: Type.Optional(Type.String({ description: "End date YYYYMMDD." })),
  limit: Type.Optional(Type.Integer({ description: "Max rows in output table (default 20)." })),
  json: Type.Optional(Type.Boolean({ description: "Emit raw JSON instead of a table." })),
}

async function executeDomain(
  domain: string,
  params: Record<string, unknown>,
): Promise<{ content: Array<{ type: "text"; text: string }>; details: unknown }> {
  const { action, ...rest } = params
  if (typeof action !== "string" || !action) {
    return {
      content: [{ type: "text", text: `error: 'action' is required for the ${domain} tool` }],
      details: { domain, error: "missing-action" },
    }
  }
  const result = await runCli(domain, action, rest)
  const text = result.ok
    ? result.stdout
    : `[aquan ${domain} ${action} failed (exit ${result.exitCode})]\n${result.stderr || result.stdout}`
  return {
    content: [{ type: "text", text }],
    details: { domain, action, exitCode: result.exitCode },
  }
}

export const stockTool: AgentTool<TSchema, unknown> = {
  name: "stock",
  label: "A-share market data",
  description: `Query A-share market data via the aquan CLI. Actions:
- quotes: spot, hist, daily
- fundamentals: financial, financial_report, income, balancesheet, cashflow, fina_indicator
- boards: concept, concept_detail, index_cons, index_weight, index_daily
- flow: northbound, lhb
- meta: health

Common flags: --code --start --end --period --adjust --indicator --limit --json.
Examples:
  {action: "hist", code: "600519", start: "20240101", end: "20240601"}
  {action: "daily", code: "600519.SS", limit: 10}
  {action: "northbound"}`,
  parameters: domainParams(COMMON_ARGS),
  execute: async (_id, params) => executeDomain("stock", params as Record<string, unknown>),
}

export const factorTool: AgentTool<TSchema, unknown> = {
  name: "factor",
  label: "Factor lifecycle",
  description: `Factor lifecycle via the aquan CLI. Actions:
- read: list, candidates
- write: register (needs --name --expression --operators --fields)
- transitions: promote, deprecate, reject (need --id)

Common flags: --status --universe --limit --id --reason --reviewer --json.
Examples:
  {action: "list"}
  {action: "list", status: "deprecated"}
  {action: "register", name: "momentum_20d", expression: "close/ref(close,20)-1", operators: "mean,stddev", fields: "close"}`,
  parameters: domainParams({
    ...COMMON_ARGS,
    name: Type.Optional(Type.String({ description: "Factor name (register)." })),
    expression: Type.Optional(Type.String({ description: "Factor expression (register)." })),
    operators: Type.Optional(Type.String({ description: "Comma-separated operators (register)." })),
    fields: Type.Optional(Type.String({ description: "Comma-separated data fields (register)." })),
    status: Type.Optional(Type.String({ description: "Filter by status (list)." })),
    universe: Type.Optional(Type.String({ description: "Filter by universe (list)." })),
    id: Type.Optional(Type.Integer({ description: "Factor id (promote/deprecate/reject)." })),
    reason: Type.Optional(Type.String({ description: "Reason (deprecate/reject)." })),
    reviewer: Type.Optional(Type.String({ description: "Reviewer (promote/reject)." })),
  }),
  execute: async (_id, params) => executeDomain("factor", params as Record<string, unknown>),
}

export const experimentTool: AgentTool<TSchema, unknown> = {
  name: "experiment",
  label: "Experiments, backtests, strategies",
  description: `Experiment lifecycle via the aquan CLI. Actions:
- read: list, steps, latest_step, best, failures, episode_summaries, backtests, portfolio
- similarity: similar, matrix (need --state as JSON)
- write: record, transitions, record_episode

Common flags: --id --name --top --limit --json. JSON-shape args: --strategy --params --result --state.
Examples:
  {action: "list"}
  {action: "best", top: 5}
  {action: "steps", id: 42}`,
  parameters: domainParams({
    ...COMMON_ARGS,
    id: Type.Optional(Type.Integer({ description: "Experiment id." })),
    name: Type.Optional(Type.String({ description: "Experiment/portfolio name." })),
    top: Type.Optional(Type.Integer({ description: "top_k (best/similar)." })),
    strategy: Type.Optional(Type.String({ description: "Strategy JSON (record)." })),
    params: Type.Optional(Type.String({ description: "Params JSON (record)." })),
    result: Type.Optional(Type.String({ description: "Result JSON (record)." })),
    state: Type.Optional(Type.String({ description: "State vector JSON (similar/matrix)." })),
  }),
  execute: async (_id, params) => executeDomain("experiment", params as Record<string, unknown>),
}

export const qlibTool: AgentTool<TSchema, unknown> = {
  name: "qlib",
  label: "Qlib quant engine",
  description: `Qlib quant engine via the aquan CLI. Actions:
- init: initialize the data provider
- data: fetch raw feature data (--instruments --fields --start --end)
- eval: evaluate a factor expression (--expression)
- operators: list available operators
- universe: read a stock universe (--name)

Common flags: --instruments --fields --expression --start --end --name --limit --json.
Examples:
  {action: "operators"}
  {action: "eval", expression: "Mean($close, 20)", instruments: "csi300"}
  {action: "universe", name: "csi300"}`,
  parameters: domainParams({
    ...COMMON_ARGS,
    instruments: Type.Optional(Type.String({ description: "Instrument set or universe name (data/eval)." })),
    fields: Type.Optional(Type.String({ description: "Comma-separated feature fields (data)." })),
    expression: Type.Optional(Type.String({ description: "Factor expression to evaluate (eval)." })),
    name: Type.Optional(Type.String({ description: "Universe name (universe)." })),
  }),
  execute: async (_id, params) => executeDomain("qlib", params as Record<string, unknown>),
}

/** All four domain tools, ready to register on an Agent. */
export const ALL_CLI_TOOLS: AgentTool<TSchema, unknown>[] = [
  stockTool,
  factorTool,
  experimentTool,
  qlibTool,
]
