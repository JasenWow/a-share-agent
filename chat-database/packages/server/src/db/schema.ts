import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core"

export const users = sqliteTable("users", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  password: text("password").notNull(),
  isAdmin: integer("is_admin", { mode: "boolean" }).notNull().default(false),
  createdAt: text("created_at").$defaultFn(() => new Date().toISOString()),
  updatedAt: text("updated_at").$defaultFn(() => new Date().toISOString()),
})

export const externalDatabases = sqliteTable("external_databases", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  dbType: text("db_type").notNull().default("postgresql"),
  host: text("host").notNull().default("localhost"),
  port: integer("port").notNull().default(5432),
  database: text("database").notNull().default(""),
  username: text("username").notNull().default(""),
  password: text("password").notNull().default(""),
  sslEnabled: integer("ssl_enabled", { mode: "boolean" }).notNull().default(false),
  filePath: text("file_path"),
  createdBy: integer("created_by").references(() => users.id),
  createdAt: text("created_at").$defaultFn(() => new Date().toISOString()),
  updatedAt: text("updated_at").$defaultFn(() => new Date().toISOString()),
})

export const customCharts = sqliteTable("custom_charts", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  sql: text("sql").notNull(),
  chartConfig: text("chart_config").notNull(), // JSON string
  databaseId: integer("database_id").references(() => externalDatabases.id),
  createdBy: integer("created_by").references(() => users.id),
  createdAt: text("created_at").$defaultFn(() => new Date().toISOString()),
  updatedAt: text("updated_at").$defaultFn(() => new Date().toISOString()),
})

export const customDashboards = sqliteTable("custom_dashboards", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  renderConfig: text("render_config").notNull(), // JSON string
  createdBy: integer("created_by").references(() => users.id),
  createdAt: text("created_at").$defaultFn(() => new Date().toISOString()),
  updatedAt: text("updated_at").$defaultFn(() => new Date().toISOString()),
})
