"use client"

import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorLogo,
  ModelSelectorLogoGroup,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector"
import { PromptInputButton } from "@/components/ai-elements/prompt-input"
import { CheckIcon } from "lucide-react"
import type { ModelDefinition } from "./constants"

const PROVIDER_LOGO_MAP: Record<string, string> = {
  google: "google",
  openai: "openai",
  anthropic: "anthropic",
  custom: "custom",
}

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  google: "Google",
  openai: "OpenAI",
  anthropic: "Anthropic",
  custom: "Custom",
}

type ChatModelSelectorProps = {
  model: string
  onModelChange: (modelId: string) => void
  open: boolean
  onOpenChange: (open: boolean) => void
  models: ModelDefinition[]
}

export function ChatModelSelector({
  model,
  onModelChange,
  open,
  onOpenChange,
  models,
}: ChatModelSelectorProps) {
  const selectedModelData = models.find((m) => m.id === model)

  // Group models by provider
  const providerGroups = new Map<string, ModelDefinition[]>()
  for (const m of models) {
    const group = providerGroups.get(m.provider) || []
    group.push(m)
    providerGroups.set(m.provider, group)
  }

  return (
    <ModelSelector onOpenChange={onOpenChange} open={open}>
      <ModelSelectorTrigger asChild>
        <PromptInputButton>
          {selectedModelData && (
            <ModelSelectorLogo provider={PROVIDER_LOGO_MAP[selectedModelData.provider] || "custom"} />
          )}
          {selectedModelData && (
            <ModelSelectorName>{selectedModelData.name}</ModelSelectorName>
          )}
        </PromptInputButton>
      </ModelSelectorTrigger>
      <ModelSelectorContent>
        <ModelSelectorInput placeholder="Search models..." />
        <ModelSelectorList>
          <ModelSelectorEmpty>No models found.</ModelSelectorEmpty>
          {Array.from(providerGroups.entries()).map(([provider, providerModels]) => (
            <ModelSelectorGroup key={provider} heading={PROVIDER_DISPLAY_NAMES[provider] || provider}>
              {providerModels.map((m) => (
                <ModelSelectorItem
                  key={m.id}
                  onSelect={() => {
                    onModelChange(m.id)
                    onOpenChange(false)
                  }}
                  value={m.id}
                >
                  <ModelSelectorLogo provider={PROVIDER_LOGO_MAP[m.provider] || "custom"} />
                  <ModelSelectorName>{m.name}</ModelSelectorName>
                  <ModelSelectorLogoGroup>
                    <ModelSelectorLogo provider={PROVIDER_LOGO_MAP[m.provider] || "custom"} />
                  </ModelSelectorLogoGroup>
                  {model === m.id ? (
                    <CheckIcon className="ml-auto size-4" />
                  ) : (
                    <div className="ml-auto size-4" />
                  )}
                </ModelSelectorItem>
              ))}
            </ModelSelectorGroup>
          ))}
        </ModelSelectorList>
      </ModelSelectorContent>
    </ModelSelector>
  )
}
