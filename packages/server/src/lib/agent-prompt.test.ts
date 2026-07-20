import { describe, test, expect } from "bun:test"
import { formatSchemaAsMarkdown, buildSystemPrompt } from "./agent-prompt"
import type { TableSchema } from "@aquan/core"

describe("formatSchemaAsMarkdown", () => {
  test("returns message for empty schema", () => {
    expect(formatSchemaAsMarkdown([])).toBe("No tables found in the database.")
  })

  test("formats a single table with columns", () => {
    const schema: TableSchema[] = [
      {
        name: "users",
        columns: [
          { name: "id", type: "INTEGER", nullable: false },
          { name: "email", type: "TEXT", nullable: false },
          { name: "name", type: "TEXT", nullable: true },
        ],
      },
    ]

    const result = formatSchemaAsMarkdown(schema)

    expect(result).toContain("### users")
    expect(result).toContain("| id | INTEGER | No |")
    expect(result).toContain("| email | TEXT | No |")
    expect(result).toContain("| name | TEXT | Yes |")
    expect(result).toContain("| Column | Type | Nullable |")
  })

  test("formats multiple tables", () => {
    const schema: TableSchema[] = [
      {
        name: "users",
        columns: [{ name: "id", type: "INTEGER", nullable: false }],
      },
      {
        name: "orders",
        columns: [{ name: "id", type: "INTEGER", nullable: false }],
      },
    ]

    const result = formatSchemaAsMarkdown(schema)

    expect(result).toContain("### users")
    expect(result).toContain("### orders")
  })
})

describe("buildSystemPrompt", () => {
  test("includes base prompt content", () => {
    const prompt = buildSystemPrompt([])
    expect(prompt).toContain("Database Report Agent")
    expect(prompt).toContain("queryDatabase")
    expect(prompt).toContain("<sql>")
  })

  test("includes schema markdown when tables exist", () => {
    const schema: TableSchema[] = [
      {
        name: "products",
        columns: [{ name: "id", type: "INTEGER", nullable: false }],
      },
    ]

    const prompt = buildSystemPrompt(schema)
    expect(prompt).toContain("### products")
    expect(prompt).toContain("| id | INTEGER | No |")
  })

  test("includes 'No tables found' when schema is empty", () => {
    const prompt = buildSystemPrompt([])
    expect(prompt).toContain("No tables found in the database.")
  })
})
