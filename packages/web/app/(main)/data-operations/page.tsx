"use client"

import { useState } from "react"
import useSWR from "swr"
import {
  getDatasetStatusKey,
  getDatasetStatus,
  getPipelineRunsKey,
  getPipelineRuns,
  getQualityResultsKey,
  getQualityResults,
  getSchedulesKey,
  getSchedules,
  getBackfillsKey,
  getBackfills,
  getMetricsCatalogKey,
  getMetricsCatalog,
  createPipelineRun,
  pauseSchedule,
  resumeSchedule,
  createBackfill,
  queryMetric,
  type PipelineRun,
  type QualityResult,
  type ScheduleDef,
  type BackfillRequest,
  type DatasetStatus,
} from "@/api-clients/data-operations"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "sonner"
import {
  Activity,
  CheckCircle2,
  XCircle,
  Pause,
  Play,
  Zap,
  CalendarPlus,
  AlertTriangle,
  Clock,
} from "lucide-react"

const DATASET = "equity_daily"

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-500/15 text-green-700 dark:text-green-400",
  failed: "bg-red-500/15 text-red-700 dark:text-red-400",
  quality_failed: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  running: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  queued: "bg-gray-500/15 text-gray-700 dark:text-gray-400",
  cancelled: "bg-gray-500/15 text-gray-700 dark:text-gray-400",
  partially_failed: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  admission_rejected: "bg-red-500/15 text-red-700 dark:text-red-400",
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="outline" className={STATUS_COLORS[status] ?? ""}>
      {status}
    </Badge>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <Card className="border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-300">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
        <span className="font-medium">Control plane unreachable</span>
      </div>
      <div className="mt-1 text-xs">{message}</div>
    </Card>
  )
}

function SpinnerBlock() {
  return (
    <div className="flex h-32 items-center justify-center">
      <Spinner className="h-6 w-6" />
    </div>
  )
}

// --- Dataset Status Card ---

function DatasetStatusCard() {
  const { data, error, isLoading } = useSWR<DatasetStatus>(
    getDatasetStatusKey(DATASET),
    () => getDatasetStatus(DATASET),
    { refreshInterval: 5000 },
  )

  if (error) return <ErrorBanner message={error.message} />
  if (isLoading || !data) return <SpinnerBlock />

  const status = data.latest_run?.status ?? "unknown"
  const freshness = data.last_accepted?.session_date ?? "never"
  const qualityOk = data.last_quality_check?.passed ?? false

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5" /> Latest Run
          </CardDescription>
          <CardTitle className="text-lg">{status}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5" /> Last Accepted
          </CardDescription>
          <CardTitle className="text-lg">{freshness}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            {qualityOk ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {" "}Quality
          </CardDescription>
          <CardTitle className="text-lg">{qualityOk ? "passing" : "failing"}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" /> Check
          </CardDescription>
          <CardTitle className="text-sm font-mono">
            {data.last_quality_check?.dimension ?? "—"} / {data.last_quality_check?.check ?? "—"}
          </CardTitle>
        </CardHeader>
      </Card>
    </div>
  )
}

// --- Run-Now Card ---

function RunNowCard() {
  const [sessionDate, setSessionDate] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const { mutate } = useSWR(getPipelineRunsKey(DATASET), () => getPipelineRuns(DATASET))

  async function onRun() {
    if (!sessionDate) return
    setSubmitting(true)
    try {
      const run = await createPipelineRun({ dataset: DATASET, session_date: sessionDate })
      toast.success(`Pipeline run created: ${run.id} (${run.status})`)
      mutate()
    } catch (e) {
      toast.error(`Failed: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Zap className="h-4 w-4" /> Run Now
        </CardTitle>
        <CardDescription>Trigger a pipeline run for a specific session.</CardDescription>
      </CardHeader>
      <CardContent className="flex gap-2">
        <Input
          type="date"
          value={sessionDate}
          onChange={(e) => setSessionDate(e.target.value)}
          className="max-w-[200px]"
        />
        <Button size="sm" onClick={onRun} disabled={submitting || !sessionDate}>
          {submitting ? "Running..." : "Run"}
        </Button>
      </CardContent>
    </Card>
  )
}

// --- Schedule Controls ---

function ScheduleControls() {
  const { data, error, isLoading, mutate } = useSWR(
    getSchedulesKey(),
    getSchedules,
    { refreshInterval: 10000 },
  )

  if (error) return <ErrorBanner message={error.message} />
  if (isLoading || !data) return <SpinnerBlock />

  if (data.schedules.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Schedules</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No schedules registered.</p>
        </CardContent>
      </Card>
    )
  }

  async function onToggle(name: string, paused: boolean) {
    try {
      if (paused) {
        await resumeSchedule(name)
        toast.success(`Schedule ${name} resumed`)
      } else {
        await pauseSchedule(name)
        toast.success(`Schedule ${name} paused`)
      }
      mutate()
    } catch (e) {
      toast.error(`Failed: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Schedules</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.schedules.map((s: ScheduleDef) => (
          <div key={s.name} className="flex items-center justify-between rounded-md border p-2">
            <div className="flex items-center gap-2">
              <Badge variant={s.paused ? "secondary" : "default"}>
                {s.paused ? "paused" : "active"}
              </Badge>
              <span className="text-sm font-medium">{s.name}</span>
              <code className="text-xs text-muted-foreground">{s.cron}</code>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {s.fire_count} fires
                {s.last_fire_at ? ` · last ${new Date(s.last_fire_at).toLocaleString()}` : ""}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onToggle(s.name, s.paused)}
              >
                {s.paused ? (
                  <><Play className="mr-1 h-3 w-3" /> Resume</>
                ) : (
                  <><Pause className="mr-1 h-3 w-3" /> Pause</>
                )}
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

// --- Pipeline Runs Table ---

function PipelineRunsTable() {
  const { data, error, isLoading } = useSWR(
    getPipelineRunsKey(DATASET),
    () => getPipelineRuns(DATASET),
    { refreshInterval: 5000 },
  )

  if (error) return <ErrorBanner message={error.message} />
  if (isLoading || !data) return <SpinnerBlock />

  const runs = data.runs.slice(0, 20)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Pipeline Runs</CardTitle>
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-3">Session</th>
                  <th className="pb-2 pr-3">Status</th>
                  <th className="pb-2 pr-3">Trigger</th>
                  <th className="pb-2 pr-3">Finished</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r: PipelineRun) => (
                  <tr key={r.id} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-mono text-xs">{r.session_date}</td>
                    <td className="py-2 pr-3"><StatusBadge status={r.status} /></td>
                    <td className="py-2 pr-3 text-xs">{r.trigger}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">
                      {r.finished_at ? new Date(r.finished_at).toLocaleTimeString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- Quality Results ---

function QualityResultsCard() {
  const { data, error, isLoading } = useSWR(
    getQualityResultsKey(DATASET),
    () => getQualityResults(DATASET),
    { refreshInterval: 10000 },
  )

  if (error) return <ErrorBanner message={error.message} />
  if (isLoading || !data) return <SpinnerBlock />

  const results = data.results.slice(-20).reverse()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Quality Checks</CardTitle>
      </CardHeader>
      <CardContent>
        {results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No quality checks yet.</p>
        ) : (
          <div className="space-y-1">
            {results.map((q: QualityResult, i: number) => (
              <div key={i} className="flex items-center justify-between rounded border p-1.5 text-xs">
                <div className="flex items-center gap-2">
                  {q.passed ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                  <span className="font-mono">{q.dimension}.{q.check}</span>
                  <Badge variant="outline" className="text-[10px]">{q.stage}</Badge>
                  {q.blocking && <Badge variant="destructive" className="text-[10px]">blocking</Badge>}
                </div>
                <span className="text-muted-foreground">
                  {q.observed != null && q.threshold != null ? `${q.observed}/${q.threshold}` : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- Backfill Card ---

function BackfillCard() {
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const { data, error, isLoading, mutate } = useSWR(
    getBackfillsKey(DATASET),
    () => getBackfills(DATASET),
    { refreshInterval: 10000 },
  )

  async function onCreate() {
    if (!start || !end) return
    setSubmitting(true)
    try {
      const bf = await createBackfill({ dataset: DATASET, start_session: start, end_session: end })
      if (bf.status === "admission_rejected") {
        toast.error(`Admission rejected: ${bf.admission_reason}`)
      } else {
        toast.success(`Backfill created: ${bf.id} (${bf.session_count} sessions)`)
      }
      mutate()
    } catch (e) {
      toast.error(`Failed: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarPlus className="h-4 w-4" /> Backfill
        </CardTitle>
        <CardDescription>Request a bounded historical backfill (max 20 sessions).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="max-w-[160px]" placeholder="Start" />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="max-w-[160px]" placeholder="End" />
          <Button size="sm" onClick={onCreate} disabled={submitting || !start || !end}>
            {submitting ? "Creating..." : "Create"}
          </Button>
        </div>
        {error && <p className="text-xs text-red-500">{error.message}</p>}
        {isLoading ? (
          <Spinner className="h-4 w-4" />
        ) : data && data.backfills.length > 0 ? (
          <div className="space-y-1">
            {data.backfills.slice(0, 5).map((bf: BackfillRequest) => (
              <div key={bf.id} className="flex items-center justify-between rounded border p-1.5 text-xs">
                <span className="font-mono">{bf.start_session} → {bf.end_session}</span>
                <StatusBadge status={bf.status} />
                <span className="text-muted-foreground">{bf.session_count} sessions</span>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

// --- Quality Pass Rate Metric ---

function QualityPassRateCard() {
  const { data, error, isLoading } = useSWR(
    "quality_pass_rate",
    () => queryMetric({ metric: "quality_pass_rate", filters: { dataset: DATASET } }),
    { refreshInterval: 15000 },
  )

  if (error) return null
  if (isLoading || !data || data.rows.length === 0) return null

  const rate = Number(data.rows[0]?.quality_pass_rate ?? 0)
  const pct = (rate * 100).toFixed(1)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>Quality Pass Rate</CardDescription>
        <CardTitle className={`text-2xl ${rate >= 0.9 ? "text-green-600 dark:text-green-400" : rate >= 0.5 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400"}`}>
          {pct}%
        </CardTitle>
      </CardHeader>
    </Card>
  )
}

// --- Main Page ---

export default function DataOperationsPage() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Data Operations</h1>
        <p className="text-sm text-muted-foreground">
          Quality monitoring, schedule management, and pipeline runs for <code className="text-xs">{DATASET}</code>.
        </p>
      </header>

      <DatasetStatusCard />

      <div className="grid gap-4 lg:grid-cols-3">
        <QualityPassRateCard />
        <RunNowCard />
        <BackfillCard />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ScheduleControls />
        <QualityResultsCard />
      </div>

      <PipelineRunsTable />
    </div>
  )
}