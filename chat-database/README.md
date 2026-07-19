# Chat Database

> **Archived (2026-07-19)**: 本目录原为独立仓库 [JasenWow/chat-database](https://github.com/JasenWow/chat-database)（commit `ae26512`），已整合到 a-share-agents monorepo 作为 UI/BI 层。后续演化在 a-share-agents 仓库进行，原仓库归档不再同步。
>
> Integration spec: `../docs/superpowers/specs/2026-07-19-chat-database-integration-design.md`

AI-powered database query agent with natural language interface, interactive dashboards, and data studio.

## Architecture

```
chat-database/
├── packages/
│   ├── shared/     # Shared types, constants (workspace: @chat-database/shared)
│   ├── server/     # Hono API server + SQLite (workspace: @chat-database/server)
│   └── web/        # Next.js frontend (workspace: @chat-database/web)
```

**Tech Stack:**
- **Backend:** Hono (Bun), Drizzle ORM, SQLite (system DB)
- **Frontend:** Next.js 15, React 19, shadcn/ui, Tailwind CSS v4, Vercel AI SDK
- **AI:** Multi-provider support (Google, OpenAI, Anthropic, custom OpenAI-compatible)
- **Database Adapters:** PostgreSQL, SQLite (extensible)

## Quick Start

### Prerequisites

- [Bun](https://bun.sh/) >= 1.0

### Setup

```bash
# 1. Install dependencies
bun install

# 2. Copy environment config
cp .env.example .env
# Edit .env to add your AI provider API key

# 3. Run database migration
bun run db:migrate

# 4. Seed initial data (creates admin user: admin@example.com / 123456)
bun run db:seed

# 5. Start dev servers (backend + frontend)
bun run dev
```

The backend runs on `http://localhost:3001` and the frontend on `http://localhost:3000`.

## AI Provider Configuration

Edit `.env` to configure one or more AI providers:

| Provider | Env Variable | Example Model |
|---|---|---|
| Google | `GOOGLE_GENERATIVE_AI_API_KEY` | `gemini-2.5-flash` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| Custom | `AI_API_KEY` + `AI_BASE_URL` | Any OpenAI-compatible model |

Set `AI_PROVIDER` and `AI_MODEL` to configure the default provider.

## Scripts

| Command | Description |
|---|---|
| `bun run dev` | Start both server and web in dev mode |
| `bun run dev:server` | Start only the backend server |
| `bun run dev:web` | Start only the frontend |
| `bun run build` | Build all packages |
| `bun run db:migrate` | Run database migrations |
| `bun run db:seed` | Seed the database with initial data |
| `bun run db:generate` | Generate a new migration from schema changes |

## Connecting External Databases

The app supports connecting to external databases for querying:

- **PostgreSQL** — via host/port/credentials
- **SQLite** — via file path

Add connections through the Databases page in the UI.

## Creating Users

```bash
cd packages/server
bun run create-user <name> <email> <password> [--admin]
```

## Project Structure

```
packages/server/src/
├── adapters/      # Database adapter pattern (PostgreSQL, SQLite)
├── ai/            # AI provider factory + tools
├── config/        # Environment config
├── db/            # Drizzle schema, connection, migrations, seed
├── lib/           # Auth, agent prompt, URL parser
├── middleware/     # Auth, CORS, error handling
└── routes/        # API routes (auth, chat, databases, charts, dashboards, admin)

packages/web/
├── app/           # Next.js App Router pages
├── api-clients/   # Frontend API client functions
├── components/    # React components (shadcn/ui + custom)
├── stores/        # Zustand state management
└── hooks/         # React hooks
```

## License

Private
