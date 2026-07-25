/**
 * Configuration for PiRuntime.
 *
 * The runtime is provider-agnostic but defaults to ZAI (GLM) which is
 * the cheapest path to a working in-process agent in China and is a
 * first-class builtin of the Pi SDK (verified via spike, see
 * docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md).
 *
 * Override provider/model/apiKey/baseUrl per environment. Auth prefers
 * an explicit apiKey option and falls back to the provider's conventional
 * env var (e.g. ZAI_API_KEY for zai).
 *
 * The provider/model/apiKey/baseUrl options can also be supplied via env
 * vars: AQUAN_PROVIDER / AQUAN_MODEL / AQUAN_API_KEY / AQUAN_BASE_URL.
 * This lets the orchestrator entry point read from .env without callers
 * having to thread options through every layer.
 */

import { env } from "node:process"

/** Default provider + model — cheap, China-available, Pi SDK builtin. */
export const DEFAULT_PROVIDER = "zai" as const
export const DEFAULT_MODEL = "glm-4.5-air" as const

export interface PiRuntimeOptions {
  /**
   * LLM provider id (e.g. "zai", "openai", "anthropic", "google",
   * "minimax", "minimax-cn"). Must be a Pi SDK builtin.
   * Default: env AQUAN_PROVIDER or "zai".
   */
  provider?: string

  /**
   * Model id under that provider (e.g. "glm-4.5-air", "MiniMax-M2.7").
   * Default: env AQUAN_MODEL or "glm-4.5-air".
   */
  model?: string

  /**
   * API key for the provider. If omitted, the SDK falls back to the
   * provider's env var (ZAI_API_KEY for zai, MINIMAX_API_KEY for minimax, ...).
   * Default: env AQUAN_API_KEY.
   */
  apiKey?: string

  /**
   * Override the provider's default base URL. Useful when a proxy or a
   * custom endpoint is needed (e.g. opencode uses
   * `https://api.minimaxi.com/anthropic/v1` while the Pi SDK builtin is
   * `https://api.minimaxi.com/anthropic`). Default: env AQUAN_BASE_URL.
   */
  baseUrl?: string

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
  Pick<PiRuntimeOptions, "apiKey" | "baseUrl"> {
  return {
    provider: opts.provider ?? env.AQUAN_PROVIDER ?? DEFAULT_PROVIDER,
    model: opts.model ?? env.AQUAN_MODEL ?? DEFAULT_MODEL,
    apiKey: opts.apiKey ?? env.AQUAN_API_KEY,
    baseUrl: opts.baseUrl ?? env.AQUAN_BASE_URL,
    thinkingLevel: opts.thinkingLevel ?? "off",
    maxTurnsPerRun: opts.maxTurnsPerRun ?? 20,
    disableCliTools: opts.disableCliTools ?? false,
  }
}
