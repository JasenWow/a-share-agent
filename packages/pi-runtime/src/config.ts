/**
 * Configuration for PiRuntime.
 *
 * The runtime is provider-agnostic but defaults to ZAI (GLM) which is
 * the cheapest path to a working in-process agent in China and is a
 * first-class builtin of the Pi SDK (verified via spike, see
 * docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md).
 *
 * Override provider/model/apiKey per environment. Auth prefers an
 * explicit apiKey option and falls back to the provider's conventional
 * env var (e.g. ZAI_API_KEY for zai).
 */

/** Default provider + model — cheap, China-available, Pi SDK builtin. */
export const DEFAULT_PROVIDER = "zai" as const
export const DEFAULT_MODEL = "glm-4.5-air" as const

export interface PiRuntimeOptions {
  /**
   * LLM provider id (e.g. "zai", "openai", "anthropic", "google").
   * Must be a Pi SDK builtin. Default: "zai".
   */
  provider?: string

  /**
   * Model id under that provider (e.g. "glm-4.5-air", "gpt-4o").
   * Default: "glm-4.5-air".
   */
  model?: string

  /**
   * API key for the provider. If omitted, the SDK falls back to the
   * provider's env var (ZAI_API_KEY for zai, OPENAI_API_KEY for openai, ...).
   * Provide this when you cannot or do not want to use env vars.
   */
  apiKey?: string

  /**
   * Default thinking level. "off" for speed; "low"/"medium"/"high" for
   * models that support reasoning. Default "off".
   */
  thinkingLevel?: "off" | "low" | "medium" | "high"

  /**
   * Hard turn cap per `runTurn` call. The Pi SDK has no native maxTurns
   * knob; PiSession enforces this via an AbortController that fires after
   * the Nth turn_end event. Default: 20.
   */
  maxTurnsPerRun?: number

  /**
   * If true, the runtime registers NO CLI tools on the agent (pure chat).
   * Useful for tests that don't want the agent attempting tool calls.
   * Default: false (CLI tools enabled).
   */
  disableCliTools?: boolean
}

/** Normalize a partial options bag into a fully-resolved config. */
export function resolvePiRuntimeOptions(
  opts: PiRuntimeOptions = {},
): Required<Pick<PiRuntimeOptions, "provider" | "model" | "thinkingLevel" | "maxTurnsPerRun" | "disableCliTools">> &
  Pick<PiRuntimeOptions, "apiKey"> {
  return {
    provider: opts.provider ?? DEFAULT_PROVIDER,
    model: opts.model ?? DEFAULT_MODEL,
    apiKey: opts.apiKey,
    thinkingLevel: opts.thinkingLevel ?? "off",
    maxTurnsPerRun: opts.maxTurnsPerRun ?? 20,
    disableCliTools: opts.disableCliTools ?? false,
  }
}
