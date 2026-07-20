"use client"

import { useState, useEffect } from "react"
import { Loader2, TrendingUp, AlertCircle, Activity, Percent, Gauge } from "lucide-react"
import { listFactors, getAShareDbId, type FactorRow } from "@/api-clients/a-share"
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
 * Factor Comparison page (A-share dashboard MVP — sub-project ❺).
 *
 * Shows all factors from the latest warehouse snapshot, sortable by ICIR.
 * Highlights: name, expression, IC, ICIR, turnover, sharpe, max_drawdown.
 */
export default function FactorsPage() {
  const [factors, setFactors] = useState<FactorRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState("")

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      setError(null)
      const { factors, error } = await listFactors()
      if (error) setError(error)
      else setFactors(factors)
      setIsLoading(false)
    }
    load()
  }, [])

  const filtered = factors.filter(
    (f) =>
      f.name.toLowerCase().includes(filter.toLowerCase()) ||
      f.universe.toLowerCase().includes(filter.toLowerCase())
  )

  // Aggregate stats
  const avgIcir =
    filtered.length > 0
      ? filtered.reduce((s, f) => s + (f.icir ?? 0), 0) / filtered.length
      : 0
  const avgSharpe =
    filtered.length > 0
      ? filtered.reduce((s, f) => s + (f.sharpe ?? 0), 0) / filtered.length
      : 0
  const activeCount = filtered.filter((f) => f.status === "active").length

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
          (type=duckdb, filePath from <code>WAREHOUSE_DUCKDB_PATH</code>), then select it as the
          active warehouse below.
        </p>
        <DbSelector />
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-4 p-4 md:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Factor Comparison</h2>
          <p className="text-sm text-muted-foreground">
            All factors from the latest warehouse snapshot, ranked by ICIR
          </p>
        </div>
        <DbSelector />
      </div>

      {/* Aggregate stat cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          icon={<Activity className="h-4 w-4" />}
          label="Total Factors"
          value={String(filtered.length)}
        />
        <StatCard
          icon={<Gauge className="h-4 w-4" />}
          label="Avg ICIR"
          value={avgIcir.toFixed(3)}
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4" />}
          label="Avg Sharpe"
          value={avgSharpe.toFixed(3)}
        />
        <StatCard
          icon={<Percent className="h-4 w-4" />}
          label="Active"
          value={`${activeCount}/${filtered.length}`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Factors</CardTitle>
          <CardDescription>Filter by name or universe</CardDescription>
          <Input
            placeholder="Filter (e.g., momentum, csi300)..."
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
            No factors yet. Run{" "}
            <code className="bg-muted px-1 py-0.5 rounded">
              uv run python -m scripts.etl.runner factor_experiments
            </code>{" "}
            to ingest from internal-store.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Expression</TableHead>
                <TableHead className="text-right">IC</TableHead>
                <TableHead className="text-right">ICIR</TableHead>
                <TableHead className="text-right">Turnover</TableHead>
                <TableHead className="text-right">Sharpe</TableHead>
                <TableHead className="text-right">MaxDD</TableHead>
                <TableHead>Universe</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((f) => (
                <TableRow key={f.name}>
                  <TableCell className="font-medium">{f.name}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground max-w-xs truncate">
                    {f.expression}
                  </TableCell>
                  <TableCell className="text-right">{fmtPct(f.ic, 3)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {f.icir !== null ? f.icir.toFixed(3) : "—"}
                  </TableCell>
                  <TableCell className="text-right">{fmtPct(f.turnover, 1)}</TableCell>
                  <TableCell className="text-right">
                    {f.sharpe !== null ? f.sharpe.toFixed(2) : "—"}
                  </TableCell>
                  <TableCell className="text-right text-destructive">
                    {f.max_drawdown !== null ? (f.max_drawdown * 100).toFixed(1) + "%" : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{f.universe || "—"}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={f.status === "active" ? "default" : "secondary"}
                    >
                      {f.status}
                    </Badge>
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

function fmtPct(v: number | null, digits = 2): string {
  if (v === null) return "—"
  return (v * 100).toFixed(digits) + "%"
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
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  )
}

/**
 * Inline DB selector — lets the user pick which registered DuckDB database
 * is the A-share warehouse. Persists to localStorage.
 */
function DbSelector() {
  return (
    <a
      href="/databases"
      className="text-xs text-muted-foreground underline hover:text-foreground"
    >
      Change warehouse
    </a>
  )
}
