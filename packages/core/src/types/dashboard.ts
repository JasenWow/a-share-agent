import type { CustomChartConfig } from "./chart"

export type ChartWidth = "half" | "full"

export interface DashboardChartItem {
  chartId: string
  width: ChartWidth
}

export interface DashboardRenderConfig {
  charts: DashboardChartItem[]
}

export interface Dashboard {
  id: string
  name: string
  createdAt: string | null
  updatedAt: string | null
  creator: {
    id: string
    name: string
    email: string
  } | null
}

export interface DashboardChart {
  id: string
  name: string
  sql: string
  chartConfig: CustomChartConfig
  databaseId: string | null
  width: ChartWidth
}

export interface DashboardDetail extends Dashboard {
  renderConfig: DashboardRenderConfig
  charts: DashboardChart[]
}
