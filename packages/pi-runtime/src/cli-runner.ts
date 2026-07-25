/**
 * cli-runner — spawn the `aquan` Python CLI as a subprocess and return
 * its stdout (or a friendly error message) for the agent.
 *
 * Why subprocess and not in-process Python:
 *   the Pi SDK and aquan Python are different language runtimes. Spawning
 *   is the simplest, most isolated bridge — and the agent calls tools
 *   infrequently enough that ~1s of process startup is acceptable.
 *
 * Safety:
 *   runCli() only ever invokes `aquan <domain> <action> --flag value ...`.
 *   It does NOT expose a generic shell. Domain and action are NOT passed
 *   through shell interpolation — they go as separate argv elements to
 *   Bun.spawn (which does not invoke /bin/sh). This honours hardening
 *   iron rule 3: never give the agent arbitrary command execution.
 */

/** Default per-call timeout (MCP servers should respond well within this). */
const DEFAULT_TIMEOUT_MS = 30_000

export interface RunCliOptions {
  /** Working directory for the subprocess. Default: repo root. */
  cwd?: string
  /** Per-call timeout in milliseconds. Default 30000. */
  timeoutMs?: number
  /**
   * Override the spawn function (for tests). Production uses Bun.spawn.
   * The function receives argv[0] as argv0 and argv[1..] as args.
   */
  spawn?: (args: string[], opts: { cwd: string; env: NodeJS.ProcessEnv; stdout: "pipe"; stderr: "pipe" }) => {
    stdout: { text: () => Promise<string> }
    stderr: { text: () => Promise<string> }
    exited: Promise<number>
    kill?: (signal?: string) => void
  }
}

export interface RunCliResult {
  /** stdout from the CLI (table or JSON). */
  stdout: string
  /** stderr (usually empty on success). */
  stderr: string
  /** exit code (0 = success). */
  exitCode: number
  /** true when exitCode === 0. */
  ok: boolean
}

/**
 * Run `aquan <domain> <action> --key value --key value ...`.
 *
 * camelCase keys in `args` are converted to --kebab-case flags. Nullish
 * values are skipped. Booleans become --flag (true) / omitted (false).
 *
 * @returns the captured stdout / stderr. The caller decides what to do
 *          with non-zero exit codes (typically: still feed the stderr
 *          text to the agent so it can react).
 */
export async function runCli(
  domain: string,
  action: string,
  args: Record<string, unknown> = {},
  opts: RunCliOptions = {},
): Promise<RunCliResult> {
  const argv = buildArgv(domain, action, args)
  const cwd = opts.cwd ?? findRepoRoot()
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const spawn = opts.spawn ?? defaultSpawn

  const proc = spawn(argv, {
    cwd,
    env: process.env,
    stdout: "pipe",
    stderr: "pipe",
  })

  // Race the process against the timeout.
  let timer: ReturnType<typeof setTimeout> | undefined
  const timeoutPromise = new Promise<{ kind: "timeout" }>((resolve) => {
    timer = setTimeout(() => resolve({ kind: "timeout" }), timeoutMs)
  })
  const exitPromise = proc.exited.then((code) => ({ kind: "exit" as const, code }))

  const winner = await Promise.race([exitPromise, timeoutPromise])
  if (timer) clearTimeout(timer)

  if (winner.kind === "timeout") {
    proc.kill?.("SIGKILL")
    return {
      stdout: "",
      stderr: `[pi-runtime] aquan ${domain} ${action} timed out after ${timeoutMs}ms`,
      exitCode: 124, // 124 is the conventional timeout exit code
      ok: false,
    }
  }

  const [stdout, stderr] = await Promise.all([proc.stdout.text(), proc.stderr.text()])
  return {
    stdout,
    stderr,
    exitCode: winner.code,
    ok: winner.code === 0,
  }
}

/**
 * Build the argv for Bun.spawn. camelCase → kebab-case conversion.
 * Exported for unit testing.
 */
export function buildArgv(domain: string, action: string, args: Record<string, unknown>): string[] {
  const argv = ["aquan", domain, action]
  for (const [key, value] of Object.entries(args)) {
    if (value == null) continue
    const flag = `--${camelToKebab(key)}`
    if (typeof value === "boolean") {
      if (value) argv.push(flag)
      continue
    }
    argv.push(flag, String(value))
  }
  return argv
}

/** Convert camelCase → kebab-case. */
function camelToKebab(s: string): string {
  return s
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1-$2")
    .toLowerCase()
}

/**
 * Locate the repo root by walking up from the current file looking for
 * package.json + python/. The pi-runtime package lives at
 * <repo>/packages/pi-runtime/, so repo root is three parents up from
 * this source file at runtime.
 */
function findRepoRoot(): string {
  // Prefer an explicit env override (tests, custom deployments).
  const fromEnv = process.env.AQUAN_REPO_ROOT
  if (fromEnv) return fromEnv
  // Walk up from cwd. Falls back to cwd if nothing matches.
  // (Bun's import.meta.dir is available at runtime; in tests we'll pass cwd explicitly.)
  return process.cwd()
}

/** Default spawn implementation: Bun.spawn. */
function defaultSpawn(
  args: string[],
  opts: { cwd: string; env: NodeJS.ProcessEnv; stdout: "pipe"; stderr: "pipe" },
) {
  const [command, ...rest] = args
  const proc = Bun.spawn({
    cmd: [command, ...rest],
    cwd: opts.cwd,
    env: opts.env,
    stdout: "pipe",
    stderr: "pipe",
  })
  return {
    stdout: streamToTextGetter(proc.stdout),
    stderr: streamToTextGetter(proc.stderr),
    exited: proc.exited,
    kill: (signal?: string) => proc.kill(signal as 0 | 3 | 15 | 9),
  }
}

/** Wrap a ReadableStream so it exposes an awaitable text() method. */
function streamToTextGetter(stream: ReadableStream<Uint8Array> | null): { text: () => Promise<string> } {
  return {
    async text(): Promise<string> {
      if (!stream) return ""
      const reader = stream.getReader()
      const decoder = new TextDecoder()
      let result = ""
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        result += decoder.decode(value, { stream: true })
      }
      result += decoder.decode()
      return result
    },
  }
}
