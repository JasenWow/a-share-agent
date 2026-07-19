export type ProviderId = "google" | "openai" | "anthropic" | "custom"

export interface ModelDefinition {
  id: string
  name: string
  provider: ProviderId
  supportsThinking?: boolean
}

export interface ProviderConfig {
  id: ProviderId
  name: string
  apiKey: string
  baseURL?: string
  models: ModelDefinition[]
}

export interface ProviderInfo {
  id: ProviderId
  name: string
  models: ModelDefinition[]
  configured: boolean
}

// Old type for backwards compatibility with chat components
export type ModelType = {
  id: string
  name: string
  chef: string
  chefSlug: string
  providers: string[]
}
