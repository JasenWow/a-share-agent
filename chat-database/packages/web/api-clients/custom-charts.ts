import { API_BASE_URL } from "./config"
import type { CustomChartConfig } from "@/components/chart/types"

export interface CustomChart {
  id: string
  name: string
  databaseId: string | null
  createdAt: string | null
  updatedAt: string | null
  creator: { id: string; name: string; email: string } | null
}

export interface CustomChartDetail extends CustomChart {
  sql: string
  chartConfig: CustomChartConfig
}

export interface CustomChartsListResponse { charts: CustomChart[]; error?: string }
export interface CustomChartGetResponse { chart: CustomChartDetail; error?: string }
export interface CustomChartCreateResponse { success: boolean; chart: CustomChartDetail; error?: string }
export interface CustomChartDeleteResponse { success: boolean; error?: string }
export interface CustomChartUpdateResponse { success: boolean; chart: CustomChartDetail; error?: string }

async function fetchApi(url: string, options?: RequestInit) {
  return fetch(url, { ...options, credentials: "include" })
}

export async function getCustomCharts(): Promise<CustomChartsListResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/custom-charts`)
    const data = await response.json()
    if (!response.ok) return { charts: [], error: data.error || "Failed to fetch charts" }
    return data
  } catch (error) {
    return { charts: [], error: error instanceof Error ? error.message : "Failed to fetch charts" }
  }
}

export async function getCustomChart(id: string): Promise<CustomChartGetResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/custom-charts/${id}`)
    const data = await response.json()
    if (!response.ok) return { chart: {} as CustomChartDetail, error: data.error || "Failed to fetch chart" }
    return data
  } catch (error) {
    return { chart: {} as CustomChartDetail, error: error instanceof Error ? error.message : "Failed to fetch chart" }
  }
}

export async function createCustomChart(
  name: string, sql: string, chartConfig: CustomChartConfig, databaseId: string | null
): Promise<CustomChartCreateResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/custom-charts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, sql, chartConfig, databaseId }),
    })
    const data = await response.json()
    if (!response.ok) return { success: false, chart: {} as CustomChartDetail, error: data.error || "Failed to create chart" }
    return data
  } catch (error) {
    return { success: false, chart: {} as CustomChartDetail, error: error instanceof Error ? error.message : "Failed to create chart" }
  }
}

export async function deleteCustomChart(id: string): Promise<CustomChartDeleteResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/custom-charts/${id}`, { method: "DELETE" })
    const data = await response.json()
    if (!response.ok) return { success: false, error: data.error || "Failed to delete chart" }
    return data
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to delete chart" }
  }
}

export async function updateCustomChart(
  id: string, name: string, sql: string, chartConfig: CustomChartConfig, databaseId: string | null
): Promise<CustomChartUpdateResponse> {
  try {
    const response = await fetchApi(`${API_BASE_URL}/custom-charts/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, sql, chartConfig, databaseId }),
    })
    const data = await response.json()
    if (!response.ok) return { success: false, chart: {} as CustomChartDetail, error: data.error || "Failed to update chart" }
    return data
  } catch (error) {
    return { success: false, chart: {} as CustomChartDetail, error: error instanceof Error ? error.message : "Failed to update chart" }
  }
}
