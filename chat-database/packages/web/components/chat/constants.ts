import type { ModelDefinition, ProviderId } from "@chat-database/shared"

export type { ModelDefinition, ProviderId }

// Default fallback models (used before API response arrives)
export const models: ModelDefinition[] = [
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", provider: "google", supportsThinking: true },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", provider: "google", supportsThinking: true },
]
