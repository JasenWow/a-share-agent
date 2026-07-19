import { Hono } from "hono"
import { cors } from "hono/cors"
import { logger } from "hono/logger"
import { env } from "./config/env"
import { authMiddleware } from "./middleware/auth"
import { errorHandler } from "./middleware/error-handler"
import { authRoutes } from "./routes/auth"
import { chatRoutes } from "./routes/chat"
import { databaseRoutes } from "./routes/databases"
import { databaseQueryRoutes } from "./routes/database-query"
import { chartRoutes } from "./routes/charts"
import { dashboardRoutes } from "./routes/dashboards"
import { adminUserRoutes } from "./routes/admin-users"
import { aiRoutes } from "./routes/ai"

const app = new Hono()

// Global middleware
app.use("*", logger())
app.use(
  "*",
  cors({
    origin: env.corsOrigin,
    credentials: true,
  })
)

// Error handler
app.onError(errorHandler)

// Health check
app.get("/health", (c) => c.json({ status: "ok" }))

// Public routes (no auth required)
app.route("/auth", authRoutes)

// Protected routes (auth required)
app.use("/chat/*", authMiddleware)
app.use("/databases/*", authMiddleware)
app.use("/database/*", authMiddleware)
app.use("/custom-charts/*", authMiddleware)
app.use("/dashboards/*", authMiddleware)
app.use("/admin/*", authMiddleware)
app.use("/ai/*", authMiddleware)

app.route("/chat", chatRoutes)
app.route("/databases", databaseRoutes)
app.route("/database", databaseQueryRoutes)
app.route("/custom-charts", chartRoutes)
app.route("/dashboards", dashboardRoutes)
app.route("/admin", adminUserRoutes)
app.route("/ai", aiRoutes)

export { app }
