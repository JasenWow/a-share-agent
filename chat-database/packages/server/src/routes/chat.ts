import { Hono } from "hono"
import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  streamText,
  convertToModelMessages,
  stepCountIs,
} from "ai"
import type { UIMessage } from "ai"
import type { ProviderId } from "@chat-database/shared"
import { createModel, getProviderOptions, getDefaultProvider } from "../ai/providers"
import { createQueryDatabaseTool } from "../ai/tools/database-query"
import { buildSystemPrompt } from "../lib/agent-prompt"
import { poolManager } from "../adapters/pool-manager"
import { getSystemSchema } from "../lib/system-schema"
import type { TableSchema } from "@chat-database/shared"

export const chatRoutes = new Hono()

// POST /chat
chatRoutes.post("/", async (c) => {
  const {
    messages,
    model: modelId,
    provider: providerId,
    thinking = true,
    databaseId,
  }: {
    messages: UIMessage[]
    model?: string
    provider?: ProviderId
    thinking?: boolean
    databaseId?: string | null
  } = await c.req.json()

  // Resolve provider and model
  const defaults = getDefaultProvider()
  const resolvedProvider = providerId || defaults.provider
  const resolvedModel = modelId || defaults.model

  // Get schema for the selected database
  let schema: TableSchema[]
  if (databaseId) {
    const adapter = await poolManager.getAdapter(databaseId)
    schema = await adapter.getSchema()
  } else {
    schema = getSystemSchema()
  }

  // Build system prompt with dynamic schema
  const systemPrompt = buildSystemPrompt(schema)

  // Create query tool bound to the selected database
  const queryDatabase = createQueryDatabaseTool(databaseId || null)

  // Create the AI model
  const aiModel = createModel(resolvedProvider, resolvedModel)

  // Provider-specific options
  const providerOptions = getProviderOptions(resolvedProvider, thinking)

  // Stream the response
  const stream = createUIMessageStream({
    originalMessages: messages,
    execute: async ({ writer }) => {
      const result = streamText({
        model: aiModel,
        system: systemPrompt,
        messages: convertToModelMessages(messages),
        tools: { queryDatabase },
        stopWhen: stepCountIs(20),
        providerOptions,
      })

      writer.merge(result.toUIMessageStream({ originalMessages: messages }))
    },
  })

  return createUIMessageStreamResponse({ stream })
})
