"use client"

import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { useMemo, useState, useEffect } from "react"
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input"
import { ChatInput } from "./chat-input"
import { ChatMessageList } from "./chat-message-list"
import { toast } from "sonner"
import { useDatabaseStore } from "@/stores/database-store"
import { API_BASE_URL } from "@/api-clients/config"
import type { ProviderInfo, ModelDefinition } from "@aquan/core"

const APPROVAL = {
  YES: "Yes, confirmed.",
  NO: "No, denied.",
} as const

const toolsRequiringConfirmation: string[] = []

export function ChatWindow() {
  const [isThinkingEnabled, setIsThinkingEnabled] = useState(false)
  const [models, setModels] = useState<ModelDefinition[]>([])
  const [model, setModel] = useState<string>("")
  const { selectedDatabaseId } = useDatabaseStore()

  // Fetch available models on mount
  useEffect(() => {
    async function fetchModels() {
      try {
        const res = await fetch(`${API_BASE_URL}/ai/models`, { credentials: "include" })
        const data = (await res.json()) as { providers: ProviderInfo[] }
        const configured: ModelDefinition[] = (data.providers || [])
          .filter((p: ProviderInfo) => p.configured)
          .flatMap((p: ProviderInfo) => p.models)
        if (configured.length > 0) {
          setModels(configured)
          setModel(configured[0].id)
        }
      } catch {
        // Silently fail — models will be empty
      }
    }
    fetchModels()
  }, [])

  const { messages, sendMessage, status, addToolOutput, setMessages } = useChat({
    transport: new DefaultChatTransport({
      api: `${API_BASE_URL}/chat`,
      credentials: "include",
    }),
    onError: (error) => {
      toast.error(error.message)
    },
  })

  const isWaitingForResponse = useMemo(() => {
    if (status !== "streaming" && status !== "submitted") return false
    const lastMessage = messages[messages.length - 1]
    if (!lastMessage) return false
    if (lastMessage.role === "user") return true
    if (lastMessage.role === "assistant" && (!lastMessage.parts || lastMessage.parts.length === 0)) return true
    return false
  }, [messages, status])

  const handleSubmit = (message: PromptInputMessage) => {
    const hasText = Boolean(message.text)
    const hasAttachments = Boolean(message.files?.length)
    if (!(hasText || hasAttachments)) return

    // Find the provider for the selected model
    const selectedModel = models.find((m) => m.id === model)
    const provider = selectedModel?.provider || "google"

    sendMessage(
      { text: message.text || "Sent with attachments" },
      {
        body: {
          model,
          provider,
          thinking: isThinkingEnabled,
          databaseId: selectedDatabaseId,
        },
      }
    )
  }

  const handleToolApproval = async (toolCallId: string, toolName: string, approved: boolean) => {
    await addToolOutput({
      toolCallId,
      tool: toolName,
      output: approved ? APPROVAL.YES : APPROVAL.NO,
    })
    const selectedModel = models.find((m) => m.id === model)
    sendMessage(undefined, {
      body: {
        model,
        provider: selectedModel?.provider || "google",
        thinking: isThinkingEnabled,
        databaseId: selectedDatabaseId,
      },
    })
  }

  const handleClearSession = () => setMessages([])

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-secondary">
      <ChatMessageList
        messages={messages}
        onToolApproval={handleToolApproval}
        toolsRequiringConfirmation={toolsRequiringConfirmation}
        isWaitingForResponse={isWaitingForResponse}
        databaseId={selectedDatabaseId}
      />
      <ChatInput
        onSubmit={handleSubmit}
        disabled={status === "streaming"}
        isThinkingEnabled={isThinkingEnabled}
        onThinkingToggle={setIsThinkingEnabled}
        model={model}
        onModelChange={setModel}
        onClearSession={handleClearSession}
        models={models}
      />
    </div>
  )
}
