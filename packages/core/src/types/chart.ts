// Base chart configuration
export interface BaseChartConfig {
  type: "line" | "area" | "bar" | "pie"
  title?: string
  description?: string
}

// Series configuration for cartesian charts
export interface SeriesConfig {
  field: string
  label?: string
  color?: string
}

// Cartesian chart configuration (line, area, bar charts)
export interface CartesianChartConfig extends BaseChartConfig {
  type: "line" | "area" | "bar"
  xAxis: {
    field: string
    label?: string
  }
  series: SeriesConfig[]
  groupBy?: {
    field: string
    valueField: string
  }
}

// Pie chart color configuration
export interface PieColorConfig {
  color: string
  name?: string
}

// Pie chart configuration
export interface PieChartConfig extends BaseChartConfig {
  type: "pie"
  label: {
    field: string
  }
  value: {
    field: string
  }
  colors?: PieColorConfig[]
}

// Union type for all chart configurations
export type CustomChartConfig = CartesianChartConfig | PieChartConfig

// Table data type
export type TableData = Record<string, unknown>

// Type guards
export function isCartesianConfig(
  config: CustomChartConfig
): config is CartesianChartConfig {
  return ["line", "area", "bar"].includes(config.type)
}

export function isPieConfig(
  config: CustomChartConfig
): config is PieChartConfig {
  return config.type === "pie"
}

export function isGroupByConfig(
  config: CustomChartConfig
): config is CartesianChartConfig & {
  groupBy: NonNullable<CartesianChartConfig["groupBy"]>
} {
  return (
    isCartesianConfig(config) &&
    !!config.groupBy?.field &&
    !!config.groupBy?.valueField
  )
}
