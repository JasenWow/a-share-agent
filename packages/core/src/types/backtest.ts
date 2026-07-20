/**
 * Backtest result shapes — produced by the trading-strategy skill and
 * consumed by the dashboard / orchestrator.
 *
 * Phase 5 placeholder — exact fields will be filled in when the
 * trading-strategy skill migrates to @aquan/* types.
 */

import type { TradingDate } from "./market"

export interface EquityCurvePoint {
  date: TradingDate
  value: number
}

export interface BacktestMetrics {
  totalReturn: number
  annualizedReturn: number
  sharpe: number
  maxDrawdown: number
  ic?: number
  ir?: number
}

export interface BacktestResult {
  id: string
  strategyName: string
  startDate: TradingDate
  endDate: TradingDate
  equityCurve: EquityCurvePoint[]
  metrics: BacktestMetrics
}
