import { mock } from "bun:test"
import type { DatabaseAdapter } from "./adapters/types"

/**
 * Create a mock DatabaseAdapter for testing.
 * Override any method by passing a partial implementation.
 */
export function createMockAdapter(
  overrides?: Partial<DatabaseAdapter>
): DatabaseAdapter {
  return {
    executeQuery: mock(async () => ({
      columns: [],
      rows: [],
      rowCount: 0,
    })),
    getSchema: mock(async () => []),
    testConnection: mock(async () => true),
    close: mock(async () => {}),
    ...overrides,
  }
}
