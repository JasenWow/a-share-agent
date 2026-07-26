# Data Operations Context

This context covers the operation of the quantitative data platform: dataset quality, scheduled work, run history, and the metrics exposed to monitoring consumers.

## Language

**Dataset**:
A logically managed collection of records with a defined grain, update cadence, and expected availability. A dataset is the object being monitored; a single file or a single query result is not a dataset.
_Avoid_: table, file, data source (when referring to the monitored business object)

**Equity daily dataset**:
The daily A-share market dataset at security-and-trading-date grain. Its expected availability follows the exchange trading calendar, not ordinary weekdays; it is the first dataset in the monitoring scope.
_Avoid_: daily file, quote snapshot

**Quality check**:
An evaluation of a loaded dataset against an expected property, producing a pass/fail or warning outcome with a severity.
_Avoid_: health check (too broad), validation (use only for pre-write checks)

**Completeness**:
Whether the expected business-date partition and expected population of records are present for a dataset.
_Avoid_: freshness

**Uniqueness**:
Whether records are unique at the dataset's declared business grain.
_Avoid_: deduplication (which describes an operation, not the property)

**Validity**:
Whether present values obey the dataset's declared domain and cross-field invariants.
_Avoid_: correctness (too broad)

**Missing value**:
An absent or null source value that remains distinguishable from a legitimate numeric zero through transformation and quality evaluation.
_Avoid_: default zero

**OHLC invariant**:
The structural relationship required within one daily price record: positive finite OHLC values, high no lower than open/close, and low no higher than open/close or high.
_Avoid_: fixed daily-return limit

**Grain violation**:
More than one record exists for the declared `(trade_date, code)` business grain. It is a blocking quality failure, not an invitation for silent deduplication.
_Avoid_: harmless duplicate

**Instrument identity validity**:
A record has a six-digit security code and an allowed exchange identity (`SH`, `SZ`, or `BJ`); unknown prefixes or exchange suffixes are invalid rather than defaulted.
_Avoid_: default exchange classification

**Freshness**:
How current a dataset is relative to the latest expected business date or session.
_Avoid_: job timeliness

**Pre-write guard**:
A check on extracted data that prevents obviously invalid data from being persisted. It is a safety barrier, not the authoritative historical quality record.
_Avoid_: final quality result

**Schedule definition**:
The intended cadence and target of recurring operational work. It describes what should happen and when, not whether it actually happened.
_Avoid_: job run, execution

**Data pipeline schedule**:
A schedule whose target is a deterministic data pipeline, including extraction, persistence, and post-write quality evaluation.
_Avoid_: agent schedule

**Trading-calendar schedule**:
A data pipeline schedule evaluated against exchange sessions. Holidays, weekends, and non-session weekdays are excluded, and the session date is the pipeline's business date.
_Avoid_: weekday cron

**Trigger SLA**:
The expected time by which the scheduler should begin an attempt for an expected session.
_Avoid_: completion deadline

**Completion SLA**:
The deadline by which the pipeline and its required quality evaluation should finish successfully for an expected session.
_Avoid_: trigger time

**SLA profile**:
The agreed trigger, completion, timezone, retry, and catch-up policy for a recurring data pipeline.
_Avoid_: cron expression (which is only one scheduling mechanism)

**Late run**:
A scheduled pipeline attempt that has not completed successfully by its completion SLA.
_Avoid_: stale dataset

**Retryable failure**:
A failure whose cause may disappear without changing code or data, such as a timeout, unavailable dependency, or source-not-ready response. It is eligible for bounded automatic retry.
_Avoid_: retry every failure

**Quality failure**:
A deterministic failure of a declared data or model invariant. It is recorded as a quality outcome and is not blindly retried merely because an attempt remains.
_Avoid_: infrastructure failure

**Rebuildable dataset**:
A dataset whose historical partitions can be re-fetched from its upstream source, making in-place refresh acceptable during the current operating phase. A rebuildable dataset still retains pipeline-run and quality outcomes.
_Avoid_: versioned dataset (unless historical revisions are explicitly retained)

**Dataset concurrency**:
The maximum number of active PipelineRuns allowed for one dataset. The first `equity_daily` policy is one; queued runs do not overlap a daily run.
_Avoid_: global process concurrency (which may have different semantics)

**Queue priority**:
The ordering policy for queued PipelineRuns. The first data-pipeline queue prioritizes the current scheduled session, then retries, then explicit manual runs, then backfill children; ties are FIFO.
_Avoid_: assuming creation order alone defines urgency

**Stale dataset**:
A dataset whose latest available business date is behind the latest expected trading session, regardless of whether a job technically ran.
_Avoid_: late run

**Agent schedule**:
A schedule whose target is an agent work item or session. It belongs to the Agent orchestration context and is not managed by the first data-pipeline control plane.
_Avoid_: data pipeline schedule

**Schedule control**:
An explicit operation on a persisted data-pipeline schedule, such as enable, pause, resume, or inspect. It changes future scheduling behavior without rewriting historical runs.
_Avoid_: changing a timer in memory

**Run now**:
An explicit request to create a pipeline run for a named business date, independent of whether the normal schedule is currently due.
_Avoid_: run today (ambiguous)

**Rerun**:
A new pipeline execution requested after a previous run reached a terminal outcome. It preserves the previous run as history rather than mutating it.
_Avoid_: overwrite the old run

**Backfill request**:
An explicit request over a bounded start and end session. The trading calendar expands it into one child PipelineRun per expected session; it is not an implicit scan of all missing data.
_Avoid_: unbounded backfill

**Non-interruptible backfill**:
A backfill execution that runs to a terminal outcome once started. It cannot be paused, resumed, or cancelled through the first control plane.
_Avoid_: resumable backfill

**Backfill admission**:
The pre-start decision that checks a backfill's scope and timing against reserved daily pipeline windows. A rejected request has not started and does not create active child runs.
_Avoid_: preemption after start

**Backfill scope limit**:
The maximum number of trading-session child runs allowed in one BackfillRequest. The first limit is 20 sessions; larger historical work is split into multiple requests.
_Avoid_: unbounded range

**Partial backfill failure**:
A BackfillRequest outcome in which some child PipelineRuns reached success while others reached a terminal failure. Remaining sessions are not discarded because one session failed.
_Avoid_: treating the whole request as atomically successful

**Runner**:
An execution component that performs a run requested by the scheduler. A runner may be implemented in another runtime, but it does not own scheduling policy or schedule definitions.
_Avoid_: scheduler

**Single control plane**:
One scheduler/control process that manages schedule definitions and dispatches multiple runner types through explicit interfaces. Separate runner contexts and databases do not require separate scheduler services.
_Avoid_: one scheduler service per domain

**Runner contract**:
The machine-readable input and outcome contract between the control plane and an execution runner, including business date, run identity, stage status, timing, and failure classification.
_Avoid_: parsing human log text as an API

**Attempt**:
One execution try within the same PipelineRun. A retryable failure increments the attempt; an explicit rerun creates a new PipelineRun instead.
_Avoid_: treating every retry as a new business run

**Job run**:
One concrete execution instance of scheduled work, with its lifecycle, timing, attempts, and outcome.
_Avoid_: schedule, task definition

**Pipeline run**:
A JobRun for a deterministic data pipeline that includes extraction/persistence and its required post-write quality stage. Its overall outcome is distinct from each stage outcome.
_Avoid_: treating ETL and quality as unrelated runs

**Quality observation**:
The recorded outcome of running one or more quality checks against a dataset at a point in time. It is historical evidence, not a live calculation only.
_Avoid_: log line, dashboard status

**Quality check result**:
One persisted observation for one named check on one dataset and business date within one PipelineRun. It includes outcome, severity, measured value, and expectation where available.
_Avoid_: one boolean health flag

**Quarantined partition**:
A physically retained dataset partition whose quality status prevents it from being treated as an accepted analytical input. Quarantine is a metadata/state decision in the first phase, not deletion.
_Avoid_: silently valid raw data

**Accepted partition**:
A dataset partition whose required quality stage passed and which is eligible for downstream models, semantic metrics, and ordinary analysis.
_Avoid_: merely landed partition

**Refresh failure**:
A refresh of an existing partition whose replacement fails quality. In the current rebuildable-data phase, the replacement is quarantined and the prior accepted content is not restored.
_Avoid_: implicit rollback

**Semantic metric**:
A named operational measurement with one agreed definition, such as freshness lag, quality pass rate, or consecutive failures, that can be queried by approved dimensions.
_Avoid_: ad hoc dashboard calculation

**Operational metric family**:
A cohesive set of semantic metrics about one operational concern: dataset state, quality results, or pipeline scheduling. A dashboard may combine families without redefining their formulas.
_Avoid_: widget-specific metric

**Semantic query**:
A typed request for a named semantic metric, approved dimensions, and approved filters. It is resolved by the semantic layer and is not raw SQL supplied by a dashboard.
_Avoid_: dashboard SQL

**Semantic metrics API**:
The read boundary that validates and executes semantic queries against the warehouse, returning a stable result shape to consumers such as dashboards or agents. In the first version it is hosted by the single orchestrator control plane.
_Avoid_: generic SQL endpoint (for metric consumption)

**Control-plane API**:
The HTTP boundary of the single control plane for schedule controls, pipeline runs, quality observations, and semantic metric queries.
_Avoid_: separate API per runner

**Control-plane endpoint**:
A named HTTP operation under the control-plane API. Dashboard, CLI, and agent consumers share the same endpoint set; there is no client-specific surface.
_Avoid_: dashboard-only API

**Minimum control-plane endpoint set**:
The agreed first-version set of HTTP operations covering schedule control, run creation and history, backfill, quality history, dataset status, semantic metrics catalog, and metric queries. The set is shared by all consumers.
_Avoid_: client-specific endpoints

**Local control plane**:
A control-plane API intentionally reachable only from the same machine during the single-user phase. It is not an authorization model for remote callers.
_Avoid_: assuming localhost means remotely safe

**Data operations dashboard**:
A dedicated monitoring view for dataset quality and data-pipeline scheduling. It is distinct from the Agent orchestration dashboard, which describes agent work lifecycles.
_Avoid_: mixing agent state with dataset health

**Alerting**:
A future delivery of semantic metric conditions to an external notification channel. It is distinct from displaying a critical or warning status in the data-operations dashboard.
_Avoid_: treating a red dashboard card as a notification

**Operational history**:
The durable PipelineRun, schedule-occurrence, and QualityCheckResult facts used for semantic trends. The first phase retains these facts without an automatic time-based purge; dashboard queries default to the latest 30 trading sessions.
_Avoid_: equating artifact retention with fact retention

**Status axes**:
The separate dimensions used to describe schedule state, pipeline-run state, quality state, and dataset freshness. They are not interchangeable and are not reduced to one boolean as the primary fact.
_Avoid_: one health flag

**Deterministic control-chain test**:
A test of scheduling, runner, quality, persistence, or semantic behavior using fixed fixtures and controlled collaborators, without depending on live MCP or market-data availability.
_Avoid_: production smoke test

**Live smoke**:
An explicit environment check against real MCP/data-source infrastructure, kept separate from the deterministic CI gate.
_Avoid_: unit test with network access

**Metric catalog**:
The single authoritative collection of metric names, formulas, units, dimensions, and filter permissions used by every semantic consumer.
_Avoid_: page-local metric definition

**Source profile**:
The explicit upstream and transformation policy used by a pipeline run. A source profile is not silently substituted when its dependency fails.
_Avoid_: invisible fallback

**Source snapshot**:
The set of records actually returned by the declared upstream source for one business session. In the first equity-daily phase, completeness describes this response's presence and scale; it does not claim coverage against an independent instrument master.
_Avoid_: full universe coverage

**Population anomaly**:
A warning that a source snapshot's row count deviates materially from its rolling historical baseline. It is distinct from the fixed minimum-row blocking rule and is not proof of universe coverage.
_Avoid_: missing-security proof

**Operational fact**:
A persisted observation about a dataset pipeline or its quality at a specific point in time, retained so it can be queried historically through the semantic layer.
_Avoid_: transient log output

**Quantitative domain store**:
The durable operational store for quantitative domain results such as factors, experiments, backtests, and portfolio state. It may contain cache records, but it is not synonymous with a cache.
_Avoid_: cache database (when referring to durable domain results)

**Agent orchestration state store**:
The store of an agent work item's execution lifecycle, events, retries, and spend. It records how work ran, not the quantitative result produced by that work.
_Avoid_: quantitative result store

**Control plane**:
The management and query boundary for schedule definitions, job runs, quality observations, and their semantic metrics. It is separate from the data-plane work that retrieves and transforms market data.
_Avoid_: ETL worker

**Quality boundary**:
The warehouse quality authority has two stages. A pre-write guard blocks malformed extraction before persistence; the post-write quality engine validates the actual warehouse data and models. Both stages produce distinguishable evidence, while the semantic layer presents their combined operational meaning.
_Avoid_: treating pre-write validation and post-write quality as interchangeable
