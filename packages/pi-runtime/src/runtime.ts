/**
 * PiRuntime — AgentRuntime backed by a real in-process Pi SDK Agent.
 *
 * One Agent is constructed per startSession() call (per WorkItem).
 * This is intentional: the Pi SDK Agent carries per-session transcript
 * state, and the orchestrator's ConcurrencyPolicy defaults to 1 (serial),
 * so we never have multiple concurrent Agents.
 *
 * Auth flow:
 *   - If opts.apiKey is provided, install it via an InMemoryCredentialStore.
 *   - Otherwise, fall back to the provider's env var (e.g. ZAI_API_KEY).
 *
 * streamFn resolution:
 *   - The Pi SDK ships one streamSimple per LLM API dialect. We pick the
 *     right one based on the resolved model's `api` field:
 *       openai-completions  → openai-completions/streamSimple  (ZAI, OpenAI, ...)
 *       anthropic-messages  → anthropic-messages/streamSimple  (MiniMax, Anthropic, ...)
 *     Other dialects (google-generative-ai, bedrock-converse-stream, ...) will
 *     throw a clear "unsupported api" error; add them here as needed.
 */

import type { AgentRuntime, AgentSession } from "@aquan/orchestrator"
import { Agent } from "@earendil-works/pi-agent-core"
import { InMemoryCredentialStore } from "@earendil-works/pi-ai"
import { builtinModels, getBuiltinModel } from "@earendil-works/pi-ai/providers/all"
import type { Model } from "@earendil-works/pi-ai"
import { streamSimple as openaiStreamSimple } from "@earendil-works/pi-ai/api/openai-completions"
import { streamSimple as anthropicStreamSimple } from "@earendil-works/pi-ai/api/anthropic-messages"
import { resolvePiRuntimeOptions, type PiRuntimeOptions } from "./config"
import { ALL_CLI_TOOLS } from "./cli-tools"
import { PiSession } from "./session"
import { NullToolRegistration } from "./tools"

export type { PiRuntimeOptions } from "./config"

/** Map a Pi SDK model's `api` field to its streamSimple function. */
function resolveStreamFn(model: Model<unknown>): (model: Model<unknown>, context: unknown, options?: unknown) => unknown {
  const api = (model as { api?: string }).api
  switch (api) {
    case "openai-completions":
      return openaiStreamSimple as never
    case "anthropic-messages":
      return anthropicStreamSimple as never
    default:
      throw new Error(
        `PiRuntime: unsupported model api "${api}". Supported: openai-completions, anthropic-messages. ` +
          `Add the corresponding streamSimple import in runtime.ts to enable it.`,
      )
  }
}

export class PiRuntime implements AgentRuntime {
  private readonly resolved: ReturnType<typeof resolvePiRuntimeOptions>

  constructor(opts: PiRuntimeOptions = {}) {
    this.resolved = resolvePiRuntimeOptions(opts)
  }

  async startSession(args: {
    workspacePath: string
    workId: string
    prompt: string
    systemPrompt?: string
  }): Promise<AgentSession> {
    const model = this.resolveModel()
    const streamFn = resolveStreamFn(model)
    const credentialStore = this.buildCredentialStore()
    const providerId = this.resolved.provider

    // The "prompt" arg from the orchestrator is the user-slot text.
    // systemPrompt, when provided (orchestrator's buildInitialPromptParts),
    // goes into the Agent state as the trusted system prompt.
    const systemPrompt =
      args.systemPrompt ??
      "You are an A-share quant agent running inside the aquan orchestrator."

    const agent = new Agent({
      streamFn,
      getApiKey: async (provider) => {
        if (provider !== providerId) return undefined
        const cred = await credentialStore.read(provider)
        // If no explicit apiKey was set, fall through to env vars
        // (the openai-completions streamSimple reads ZAI_API_KEY etc. itself).
        if (cred?.type === "api_key") return cred.key
        return undefined
      },
      initialState: {
        systemPrompt,
        model,
        thinkingLevel: this.resolved.thinkingLevel,
        // The four domain tools (stock / factor / experiment / qlib) are
        // spawned via `aquan <domain> <action> ...`. Pass disableCliTools:true
        // to opt out (e.g. for tests that want a tool-less agent).
        tools: this.resolved.disableCliTools ? [] : [...ALL_CLI_TOOLS],
        messages: [],
      },
    })

    return new PiSession({
      agent,
      sessionId: `pi-${args.workId}`,
      workspacePath: args.workspacePath,
      maxTurnsPerRun: this.resolved.maxTurnsPerRun,
    })
  }

  async stopSession(session: AgentSession): Promise<void> {
    // PiSession owns its Agent; nothing to release here (no transport to close).
    // Abort is owned by runTurn via AbortController; if a session is abandoned
    // mid-run, the GC will reclaim it. Future: explicit agent.reset() if needed.
    void session
  }

  private resolveModel(): Model<unknown> {
    const { provider, model, baseUrl } = this.resolved
    const found = getBuiltinModel(provider, model)
    if (!found) {
      const available = listAvailableModelIds(provider)
      throw new Error(
        `PiRuntime: model "${model}" not found under provider "${provider}". ` +
          `Available: ${available.length > 0 ? available.join(", ") : "(none — check provider id)"}`,
      )
    }
    // Apply baseUrl override if the caller (or AQUAN_BASE_URL env) supplied one.
    // We clone so we don't mutate the SDK's cached model registry.
    if (baseUrl && baseUrl.trim() !== "") {
      return { ...(found as Model<unknown>), baseUrl } as Model<unknown>
    }
    return found as Model<unknown>
  }

  private buildCredentialStore(): InMemoryCredentialStore {
    const store = new InMemoryCredentialStore()
    if (this.resolved.apiKey) {
      // modify() is the only way to set; give it the api_key shape.
      store
        .modify(this.resolved.provider, async () => ({
          type: "api_key" as const,
          key: this.resolved.apiKey,
        }))
        .catch(() => {
          // best-effort; env-var fallback will handle auth
        })
    }
    // If no explicit apiKey, the SDK falls back to env vars (ZAI_API_KEY, ...).
    return store
  }
}

/** List model ids for a provider, for error messages. */
function listAvailableModelIds(provider: string): string[] {
  try {
    const registry = builtinModels()
    const models = registry.getModels(provider)
    return models.map((m) => m.id).filter((id): id is string => typeof id === "string")
  } catch {
    return []
  }
}
