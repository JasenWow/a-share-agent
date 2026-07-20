export const env = {
  serverPort: Number(process.env.SERVER_PORT) || 3001,
  serverHost: process.env.SERVER_HOST || "localhost",
  databasePath: process.env.DATABASE_PATH || "",
  // AI Provider
  aiProvider: (process.env.AI_PROVIDER || "google") as "google" | "openai" | "anthropic" | "custom",
  aiModel: process.env.AI_MODEL || "gemini-2.5-flash",
  // Google
  googleApiKey: process.env.GOOGLE_GENERATIVE_AI_API_KEY || "",
  // OpenAI
  openaiApiKey: process.env.OPENAI_API_KEY || "",
  openaiBaseUrl: process.env.OPENAI_BASE_URL || "",
  // Anthropic
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
  // Custom
  customApiKey: process.env.AI_API_KEY || "",
  customBaseUrl: process.env.AI_BASE_URL || "",
  // CORS
  corsOrigin: process.env.CORS_ORIGIN || process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000",
}
