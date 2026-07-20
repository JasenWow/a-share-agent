# AI Integration

## Providers (`ai/providers.ts`)

`google` (@ai-sdk/google), `openai` (@ai-sdk/openai, optional baseURL), `anthropic` (@ai-sdk/anthropic), `custom` (@ai-sdk/openai compatible). Default via `AI_PROVIDER`/`AI_MODEL` env vars. Models defined in `shared/constants/ai-providers.ts`.

Adding a provider: install SDK → `createModel()` case → `getAvailableProviders()` entry → `shared/types/ai.ts` ProviderId → `DEFAULT_MODELS` + `PROVIDER_NAMES`.

## Chat Flow (`routes/chat.ts`)

Parse {messages, model?, provider?, thinking?, databaseId?} → resolve provider/model → fetch schema (external via poolManager or system via `getSystemSchema()`) → build prompt → create `queryDatabase` tool → stream via `createUIMessageStream` + `streamText` (AI SDK v5). Max 20 tool steps per request (`stepCountIs(20)`).

## Agent Prompt (`lib/agent-prompt.ts`)

System prompt: "Database Report Agent". Validates via tool, presents SQL in `<sql>` tags. Chart viz: `<sql config='{"type":"bar",...}'>` supports bar/line/area/pie.

## Tools

`ai/tools/database-query.ts` — `createQueryDatabaseTool(databaseId)`. External DB: full SQL via adapter. System DB: SELECT/PRAGMA only. Returns `{success, columns, rows, rowCount}` or `{success: false, error}`.

Add new tools in `chat.ts` tools object.

## Web

`app/(main)/agent/page.tsx` → `components/chat/ChatWindow`. AI SDK `useChat` for streaming. `components/ai-elements/` for message rendering.
