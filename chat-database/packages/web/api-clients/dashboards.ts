import { API_BASE_URL } from "./config"
import type { CustomChartConfig } from "@/components/chart/types"

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
  creator: { id: string; name: string; email: string } | null
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

export interface DashboardsListResponse { dashboards: Dashboard[]; error?: string }
export interface DashboardGetResponse { dashboard: DashboardDetail; error?: string }
export interface DashboardCreateResponse { success: boolean; dashboard: Dashboard; error?: string }
export interface DashboardUpdateResponse { success: boolean; dashboard: Dashboard; error?: string }
export interface DashboardDeleteResponse { success: boolean; error?: string }

async function fetchApi(url: string, options?: RequestInit) {
  return fetch(url, { ...options, credentials: "include" })
}

export async function getDashboards(): Promise<DashboardsListResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/dashboards`)
    const data = await response.json()
    if (!response.ok) return { dashboards: [], error: data.error || "Failed to fetch dashboards" }
    return data
  } catch (error) {
    return { dashboards: [], error: error instanceof Error ? error.message : "Failed to fetch dashboards" }
  }
}

export async function getDashboard(id: string): Promise<DashboardGetResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/dashboards/${id}`)
    const data = await response.json()
    if (!response.ok) return { dashboard: {} as DashboardDetail, error: data.error || "Failed to fetch dashboard" }
    return data
  } catch (error) {
    return { dashboard: {} as DashboardDetail, error: error instanceof Error ? error.message : "Failed to fetch dashboard" }
  }
}

export async function createDashboard(name: string, renderConfig: DashboardRenderConfig): Promise<DashboardCreateResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/dashboards`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, renderConfig }),
    })
    const data = await response.json()
    if (!response.ok) return { success: false, dashboard: {} as Dashboard, error: data.error || "Failed to create dashboard" }
    return data
  } catch (error) {
    return { success: false, dashboard: {} as Dashboard, error: error instanceof Error ? error.message : "Failed to create dashboard" }
  }
}

export async function updateDashboard(id: string, name: string, renderConfig: DashboardRenderConfig): Promise<DashboardUpdateResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/dashboards/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, renderConfig }),
    })
    const data = await response.json()
    if (!response.ok) return { success: false, dashboard: {} as Dashboard, error: data.error || "Failed to update dashboard" }
    return data
  } catch (error) {
    return { success: false, dashboard: {} as Dashboard, error: error instanceof Error ? error.message : "Failed to update dashboard" }
  }
}

export async function deleteDashboard(id: string): Promise<DashboardDeleteResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/dashboards/${id}`, { method: "DELETE" })
    const data = await response.json()
    if (!response.ok) return { success: false, error: data.error || "Failed to delete dashboard" }
    return data
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to delete dashboard" }
  }
}
