"use client"

import { useState, useEffect } from "react"
import {
  Loader2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Activity,
  Calendar,
} from "lucide-react"
import { listBacktests, getAShareDbId, type BacktestRow } from "@/api-clients/a-share"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * Backtest History page (A-share dashboard MVP — sub-project ❺).
 *
 * Shows all backtest runs from the latest warehouse snapshot, ranked by Sharpe.
 * MVP scope: tabular view with key metrics. Full version (M6) will add
 * nav-curve comparison and Sharpe/MaxDD scatter.
 */
export default function BacktestsPage() {
  const [backtests, setBacktests] = useState<BacktestRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState("")

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      setError(null)
      const { backtests, error } = await listBacktests()
      if (error) setError(error)
      else setBacktests(backtests)
      setIsLoading(false)
    }
    load()
  }, [])

  const filtered = backtests.filter(
    (b) =>
      b.name.toLowerCase().includes(filter.toLowerCase()) ||
      b.strategy.toLowerCase().includes(filter.toLowerCase())
  )

  const avgSharpe =
    filtered.length > 0
      ? filtered.reduce((s, b) => s + (b.sharpe ?? 0), 0) / filtered.length
      : 0
  const avgMaxDD =
    filtered.length > 0
      ? filtered.reduce((s, b) => s + (b.max_drawdown ?? 0), 0) / filtered.length
      : 0
  const avgAnnRet =
    filtered.length > 0
      ? filtered.reduce((s, b) => s + (b.annual_return ?? 0), 0) / filtered.length
      : 0
  const bestSharpe = filtered.reduce(
    (best, b) => ((b.sharpe ?? -Infinity) > (best?.sharpe ?? -Infinity) ? b : best),
    null as BacktestRow | null
  )

  const hasDb = getAShareDbId() !== null

  if (!hasDb && !isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-3">
        <AlertCircle className="h-10 w-10 text-amber-500" />
        <h2 className="text-lg font-semibold">No A-Share warehouse connected</h2>
        <p className="text-sm text-muted-foreground max-w-md text-center">
          Register the DuckDB warehouse in{" "}
          <a href="/databases" className="underline">
            Databases
          </a>{" "}
          (type=duckdb), then revisit this page.
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-4 p-4 md:p-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Backtest History</h2>
        <p className="text-sm text-muted-foreground">
          All backtest runs from the latest warehouse snapshot, ranked by Sharpe
        </p>
      </div>

      {/* Aggregate stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          icon={<Activity className="h-4 w-4" />}
          label="Total Runs"
          value={String(filtered.length)}
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4" />}
          label="Avg Sharpe"
          value={avgSharpe.toFixed(2)}
        />
        <StatCard
          icon={<TrendingDown className="h-4 w-4" />}
          label="Avg MaxDD"
          value={(avgMaxDD * 100).toFixed(1) + "%"}
        />
        <StatCard
          icon={<Calendar className="h-4 w-4" />}
          label="Avg Ann.Return"
          value={(avgAnnRet * 100).toFixed(1) + "%"}
        />
      </div>

      {bestSharpe && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-500" />
              Best Performer
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-4">
              <span className="text-lg font-medium">{bestSharpe.name}</span>
              <Badge variant="outline">Sharpe {bestSharpe.sharpe?.toFixed(2)}</Badge>
              <Badge variant="outline">
                Ann.Ret {((bestSharpe.annual_return ?? 0) * 100).toFixed(1)}%
              </Badge>
              <Badge variant="outline">
                MaxDD {((bestSharpe.max_drawdown ?? 0) * 100).toFixed(1)}%
              </Badge>
              <span className="text-xs text-muted-foreground font-mono truncate">
                {bestSharpe.strategy}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Backtest Runs</CardTitle>
          <CardDescription>Filter by name or strategy</CardDescription>
          <Input
            placeholder="Filter (e.g., momentum, TopK)..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="max-w-sm"
          />
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 py-8 text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm">{error}</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No backtests yet. Run{" "}
              <code className="bg-muted px-1 py-0.5 rounded">
                uv run python -m scripts.etl.runner backtest_runs
              </code>{" "}
              to ingest from internal-store.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead className="text-right">Sharpe</TableHead>
                  <TableHead className="text-right">MaxDD</TableHead>
                  <TableHead className="text-right">Ann.Return</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((b) => (
                  <TableRow key={b.run_id}>
                    <TableCell className="font-medium">{b.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground max-w-xs truncate">
                      {b.strategy}
                    </TableCell>
                    <TableCell className="text-xs">
                      {b.start_date} → {b.end_date}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {b.sharpe !== null ? b.sharpe.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell className="text-right text-destructive">
                      {b.max_drawdown !== null
                        ? (b.max_drawdown * 100).toFixed(1) + "%"
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {b.annual_return !== null
                        ? (b.annual_return * 100).toFixed(1) + "%"
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {b.created_at?.slice(0, 10)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  )
}
