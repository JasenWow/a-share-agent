import { describe, test, expect } from "bun:test"
import { isCartesianConfig, isPieConfig, isGroupByConfig } from "./chart"
import type { CustomChartConfig } from "./chart"

function cartesianConfig(
  overrides: Partial<CustomChartConfig> = {}
): CustomChartConfig {
  return {
    type: "bar",
    xAxis: { field: "category" },
    series: [{ field: "count", label: "Count" }],
    ...overrides,
  } as CustomChartConfig
}

function pieConfig(): CustomChartConfig {
  return {
    type: "pie",
    label: { field: "name" },
    value: { field: "amount" },
  }
}

describe("isCartesianConfig", () => {
  test("returns true for line chart", () => {
    expect(isCartesianConfig(cartesianConfig({ type: "line" }))).toBe(true)
  })

  test("returns true for area chart", () => {
    expect(isCartesianConfig(cartesianConfig({ type: "area" }))).toBe(true)
  })

  test("returns true for bar chart", () => {
    expect(isCartesianConfig(cartesianConfig({ type: "bar" }))).toBe(true)
  })

  test("returns false for pie chart", () => {
    expect(isCartesianConfig(pieConfig())).toBe(false)
  })
})

describe("isPieConfig", () => {
  test("returns true for pie chart", () => {
    expect(isPieConfig(pieConfig())).toBe(true)
  })

  test("returns false for line chart", () => {
    expect(isPieConfig(cartesianConfig({ type: "line" }))).toBe(false)
  })

  test("returns false for bar chart", () => {
    expect(isPieConfig(cartesianConfig({ type: "bar" }))).toBe(false)
  })
})

describe("isGroupByConfig", () => {
  test("returns true when groupBy has field and valueField", () => {
    const config = cartesianConfig({
      type: "bar",
    }) as CustomChartConfig & { groupBy: { field: string; valueField: string } }
    // Cast to add groupBy
    const withGroupBy = {
      ...config,
      groupBy: { field: "status", valueField: "amount" },
    } as CustomChartConfig
    expect(isGroupByConfig(withGroupBy)).toBe(true)
  })

  test("returns false when groupBy is missing", () => {
    expect(isGroupByConfig(cartesianConfig())).toBe(false)
  })

  test("returns false when groupBy has no valueField", () => {
    const config = cartesianConfig()
    const withPartialGroupBy = {
      ...config,
      groupBy: { field: "status" },
    } as CustomChartConfig
    expect(isGroupByConfig(withPartialGroupBy)).toBe(false)
  })

  test("returns false for pie chart", () => {
    expect(isGroupByConfig(pieConfig())).toBe(false)
  })
})
