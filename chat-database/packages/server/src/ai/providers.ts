import { google } from "@ai-sdk/google"
import { openai } from "@ai-sdk/openai"
import { anthropic } from "@ai-sdk/anthropic"
import type { ProviderId, ModelDefinition, ProviderInfo } from "@chat-database/shared"
import { DEFAULT_MODELS, PROVIDER_NAMES } from "@chat-database/shared"
import { env } from "../config/env"

export function createModel(providerId: ProviderId, modelId: string) {
  switch (providerId) {
    case "google":
      return google(modelId)
    case "openai":
      return openai(modelId, env.openaiBaseUrl ? { baseURL: env.openaiBaseUrl } : undefined)
    case "anthropic":
      return anthropic(modelId)
    case "custom":
      return openai(modelId, {
        apiKey: env.customApiKey,
        baseURL: env.customBaseUrl,
      })
    default:
      throw new Error(`Unsupported provider: ${providerId}`)
  }
}

export function getProviderOptions(providerId: ProviderId, thinking: boolean): Record<string, unknown> {
  if (providerId === "google" && thinking) {
    return {
      google: {
        thinkingConfig: {
          thinkingBudget: 4096,
          includeThoughts: true,
        },
      },
    }
  }
  return {}
}

export function getAvailableProviders(): ProviderInfo[] {
  const providers: ProviderInfo[] = []

  // Google
  providers.push({
    id: "google",
    name: PROVIDER_NAMES.google,
    models: DEFAULT_MODELS.google,
    configured: !!env.googleApiKey,
  })

  // OpenAI
  providers.push({
    id: "openai",
    name: PROVIDER_NAMES.openai,
    models: DEFAULT_MODELS.openai,
    configured: !!env.openaiApiKey,
  })

  // Anthropic
  providers.push({
    id: "anthropic",
    name: PROVIDER_NAMES.anthropic,
    models: DEFAULT_MODELS.anthropic,
    configured: !!env.anthropicApiKey,
  })

  // Custom (OpenAI-compatible)
  providers.push({
    id: "custom",
    name: PROVIDER_NAMES.custom,
    models: DEFAULT_MODELS.custom,
    configured: !!env.customApiKey && !!env.customBaseUrl,
  })

  return providers
}

export function getDefaultProvider(): { provider: ProviderId; model: string } {
  const providerId = env.aiProvider as ProviderId
  const modelId = env.aiModel
  return { provider: providerId, model: modelId }
}
