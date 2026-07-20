import type { ModelDefinition, ProviderId } from "../types/ai"

export const DEFAULT_MODELS: Record<ProviderId, ModelDefinition[]> = {
  google: [
    { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", provider: "google", supportsThinking: true },
    { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", provider: "google", supportsThinking: true },
  ],
  openai: [
    { id: "gpt-4o", name: "GPT-4o", provider: "openai" },
    { id: "gpt-4o-mini", name: "GPT-4o Mini", provider: "openai" },
    { id: "gpt-4.1", name: "GPT-4.1", provider: "openai" },
    { id: "o3", name: "o3", provider: "openai" },
    { id: "o4-mini", name: "o4-mini", provider: "openai" },
  ],
  anthropic: [
    { id: "claude-sonnet-4-20250514", name: "Claude Sonnet 4", provider: "anthropic" },
    { id: "claude-haiku-4-20250514", name: "Claude Haiku 4", provider: "anthropic" },
  ],
  custom: [
    // Custom provider models are defined by the user via API
  ],
}

export const PROVIDER_NAMES: Record<ProviderId, string> = {
  google: "Google",
  openai: "OpenAI",
  anthropic: "Anthropic",
  custom: "Custom (OpenAI-compatible)",
}
