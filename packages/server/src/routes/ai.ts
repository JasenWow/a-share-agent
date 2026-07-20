import { Hono } from "hono"
import { getAvailableProviders } from "../ai/providers"

export const aiRoutes = new Hono()

// GET /ai/models
aiRoutes.get("/models", async (c) => {
  const providers = getAvailableProviders()
  return c.json({ providers })
})
