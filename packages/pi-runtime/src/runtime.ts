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
 * streamFn:
 *   - We import streamSimple from @earendil-works/pi-ai/api/openai-completions.
 *   - ZAI/OpenAI/Anthropic-compatible providers all use openai-completions API.
 *   - For providers with other APIs (google-generative-ai, bedrock, ...),
 *     future versions will need a per-API streamFn resolver. Out of scope
 *     for Stage 1 (default is ZAI).
 */

import type { AgentRuntime, AgentSession } from "@aquan/orchestrator"
import { Agent } from "@earendil-works/pi-agent-core"
import { InMemoryCredentialStore } from "@earendil-works/pi-ai"
import { builtinModels, getBuiltinModel } from "@earendil-works/pi-ai/providers/all"
import type { Model } from "@earendil-works/pi-ai"
import { streamSimple } from "@earendil-works/pi-ai/api/openai-completions"
import { resolvePiRuntimeOptions, type PiRuntimeOptions } from "./config"
import { PiSession } from "./session"
import { NullToolRegistration } from "./tools"

export type { PiRuntimeOptions } from "./config"

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
    const credentialStore = this.buildCredentialStore()
    const providerId = this.resolved.provider

    // The "prompt" arg from the orchestrator is the user-slot text.
    // systemPrompt, when provided (orchestrator's buildInitialPromptParts),
    // goes into the Agent state as the trusted system prompt.
    const systemPrompt =
      args.systemPrompt ??
      "You are an A-share quant agent running inside the aquan orchestrator."

    const agent = new Agent({
      streamFn: streamSimple,
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
        tools: [],
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
    const { provider, model } = this.resolved
    const found = getBuiltinModel(provider, model)
    if (!found) {
      const available = listAvailableModelIds(provider)
      throw new Error(
        `PiRuntime: model "${model}" not found under provider "${provider}". ` +
          `Available: ${available.length > 0 ? available.join(", ") : "(none — check provider id)"}`,
      )
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
