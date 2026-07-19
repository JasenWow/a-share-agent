/**
 * E2E Test Suite for chat-database
 * Usage: bun run packages/server/src/__tests__/e2e-test.ts
 *
 * Tests all backend API endpoints + frontend page rendering
 */

const BASE = "http://localhost:3001"
const WEB = "http://localhost:3000"
let passed = 0
let failed = 0
let cookies = ""

function assert(condition: boolean, name: string, detail?: string) {
  if (condition) {
    console.log(`  ✅ ${name}`)
    passed++
  } else {
    console.log(`  ❌ ${name}${detail ? ` — ${detail}` : ""}`)
    failed++
  }
}

async function api(
  method: string,
  path: string,
  body?: unknown
): Promise<{ status: number; data: any }> {
  const opts: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  }
  if (body) opts.body = JSON.stringify(body)

  // Build cookie header manually for bun fetch
  if (cookies) opts.headers = { ...opts.headers, Cookie: cookies }

  const res = await fetch(`${BASE}${path}`, opts)
  const setCookie = res.headers.getSetCookie()
  if (setCookie && setCookie.length > 0) {
    const raw = setCookie[0] ?? ""
    const isCleared = /max-age\s*=\s*0/i.test(raw) || raw.includes("auth_session=;")
    if (isCleared) {
      cookies = ""
    } else {
      const match = raw.match(/auth_session=[^;]+/)
      if (match) cookies = match[0]
    }
  }
  const data = await res.json().catch(() => null)
  return { status: res.status, data }
}

async function pageStatus(path: string): Promise<number> {
  const opts: RequestInit = { redirect: "manual" }
  if (cookies) opts.headers = { Cookie: cookies }
  try {
    const res = await fetch(`${WEB}${path}`, opts)
    return res.status
  } catch {
    return 0
  }
}

// ========================================
// Run Tests
// ========================================

async function main() {
  console.log("\n🧪 E2E Test Suite\n")

  // --- Backend Health ---
  console.log("📦 Backend API Tests")

  const health = await api("GET", "/health")
  assert(health.status === 200, "GET /health returns 200")
  assert(health.data?.status === "ok", "GET /health returns status ok")

  // --- Auth ---
  console.log("\n🔐 Auth Tests")

  const badLogin = await api("POST", "/auth/login", {
    email: "admin@example.com",
    password: "wrong",
  })
  assert(badLogin.status === 401, "Bad login returns 401")

  const login = await api("POST", "/auth/login", {
    email: "admin@example.com",
    password: "123456",
  })
  assert(login.status === 200, "Good login returns 200")
  assert(login.data?.success === true, "Login returns success=true")
  assert(login.data?.user?.email === "admin@example.com", "Login returns user email")
  assert(login.data?.user?.isAdmin === true, "Admin user has isAdmin=true")

  const me = await api("GET", "/auth/me")
  assert(me.status === 200, "GET /auth/me returns 200")
  assert(me.data?.authenticated === true, "Me returns authenticated=true")

  const logout = await api("POST", "/auth/logout")
  assert(logout.status === 200, "Logout returns 200")

  const meAfter = await api("GET", "/auth/me")
  assert(meAfter.data?.authenticated === false, "Me after logout returns authenticated=false")

  // Re-login
  await api("POST", "/auth/login", { email: "admin@example.com", password: "123456" })

  // --- Unauthenticated Access ---
  console.log("\n🔒 Auth Protection Tests")

  const savedCookies = cookies
  cookies = ""
  const unauth = await api("GET", "/databases")
  assert(unauth.status === 401, "Unauthenticated /databases returns 401")
  cookies = savedCookies

  // --- Databases CRUD ---
  console.log("\n💾 Database CRUD Tests")

  const dbList = await api("GET", "/databases")
  assert(dbList.status === 200, "GET /databases returns 200")
  assert(Array.isArray(dbList.data?.databases), "Databases list is array")

  const dbCreate = await api("POST", "/databases", {
    name: "Test DB",
    dbType: "postgresql",
    host: "localhost",
    port: 5432,
    database: "testdb",
    username: "user",
    password: "pass",
    sslEnabled: false,
  })
  assert(dbCreate.status === 200, "POST /databases returns 200")
  assert(dbCreate.data?.database?.name === "Test DB", "Created database has correct name")
  assert(dbCreate.data?.database?.dbType === "postgresql", "Created database has correct dbType")
  const dbId = dbCreate.data?.database?.id
  assert(!!dbId, "Created database has an id")

  const dbGet = await api("GET", `/databases/${dbId}`)
  assert(dbGet.status === 200, "GET /databases/:id returns 200")
  assert(dbGet.data?.database?.id === dbId, "Got correct database id")

  const dbTest = await api("POST", `/databases/${dbId}/test`)
  assert(dbTest.status === 200 || dbTest.status === 400, "Test connection returns 200 or 400 (no real DB)")

  const dbDelete = await api("DELETE", `/databases/${dbId}`)
  assert(dbDelete.status === 200, "DELETE /databases/:id returns 200")

  // --- Custom Charts CRUD ---
  console.log("\n📊 Chart CRUD Tests")

  const chartList = await api("GET", "/custom-charts")
  assert(chartList.status === 200, "GET /custom-charts returns 200")
  assert(Array.isArray(chartList.data?.charts), "Charts list is array")

  const chartCreate = await api("POST", "/custom-charts", {
    name: "Test Chart",
    sql: "SELECT 1 as val",
    chartConfig: { type: "bar", xAxis: { field: "x" }, series: [{ field: "val" }] },
    databaseId: null,
  })
  assert(chartCreate.status === 200, "POST /custom-charts returns 200")
  assert(chartCreate.data?.chart?.name === "Test Chart", "Created chart has correct name")
  const chartId = chartCreate.data?.chart?.id

  const chartGet = await api("GET", `/custom-charts/${chartId}`)
  assert(chartGet.status === 200, "GET /custom-charts/:id returns 200")
  assert(chartGet.data?.chart?.chartConfig?.type === "bar", "Chart config is parsed correctly")

  const chartUpdate = await api("PUT", `/custom-charts/${chartId}`, {
    name: "Updated Chart",
    sql: "SELECT 2 as val",
    chartConfig: { type: "line", xAxis: { field: "x" }, series: [{ field: "val" }] },
    databaseId: null,
  })
  assert(chartUpdate.status === 200, "PUT /custom-charts/:id returns 200")
  assert(chartUpdate.data?.chart?.name === "Updated Chart", "Updated chart has correct name")

  const chartDelete = await api("DELETE", `/custom-charts/${chartId}`)
  assert(chartDelete.status === 200, "DELETE /custom-charts/:id returns 200")

  // --- Dashboards CRUD ---
  console.log("\n📋 Dashboard CRUD Tests")

  const dashList = await api("GET", "/dashboards")
  assert(dashList.status === 200, "GET /dashboards returns 200")
  assert(Array.isArray(dashList.data?.dashboards), "Dashboards list is array")

  const dashCreate = await api("POST", "/dashboards", {
    name: "Test Dashboard",
    renderConfig: { charts: [] },
  })
  assert(dashCreate.status === 200, "POST /dashboards returns 200")
  const dashId = dashCreate.data?.dashboard?.id

  const dashGet = await api("GET", `/dashboards/${dashId}`)
  assert(dashGet.status === 200, "GET /dashboards/:id returns 200")
  assert(Array.isArray(dashGet.data?.dashboard?.charts), "Dashboard has charts array")
  assert(dashGet.data?.dashboard?.renderConfig?.charts?.length === 0, "Empty dashboard has 0 charts")

  const dashUpdate = await api("PUT", `/dashboards/${dashId}`, {
    name: "Updated Dashboard",
    renderConfig: { charts: [] },
  })
  assert(dashUpdate.status === 200, "PUT /dashboards/:id returns 200")

  const dashDelete = await api("DELETE", `/dashboards/${dashId}`)
  assert(dashDelete.status === 200, "DELETE /dashboards/:id returns 200")

  // --- Database Query & Schema ---
  console.log("\n🔍 Database Query Tests")

  const schema = await api("GET", "/database/schema")
  assert(schema.status === 200, "GET /database/schema returns 200")
  assert(Array.isArray(schema.data?.schema), "Schema is array")
  assert(schema.data.schema.length > 0, "System schema has tables")

  const query = await api("POST", "/database/query", {
    sql: "SELECT COUNT(*) as cnt FROM users",
  })
  assert(query.status === 200, "POST /database/query returns 200")
  assert(query.data?.rowCount >= 1, "Query returns rows")
  assert(query.data?.columns?.includes("cnt"), "Query has cnt column")

  const badQuery = await api("POST", "/database/query", {
    sql: "SELECT * FROM nonexistent_table",
  })
  assert(badQuery.status === 500, "Bad SQL returns 500")

  // --- Admin Users ---
  console.log("\n👤 Admin User Tests")

  const users = await api("GET", "/admin/users")
  assert(users.status === 200, "GET /admin/users returns 200")
  assert(Array.isArray(users.data?.users), "Users list is array")
  assert(users.data.users.length >= 1, "Has at least one user")

  // --- AI Models ---
  console.log("\n🤖 AI Provider Tests")

  const models = await api("GET", "/ai/models")
  assert(models.status === 200, "GET /ai/models returns 200")
  assert(Array.isArray(models.data?.providers), "Providers list is array")
  assert(models.data.providers.length >= 3, "Has at least 3 providers")
  const providerIds = models.data.providers.map((p: any) => p.id)
  assert(
    providerIds.includes("google") && providerIds.includes("openai") && providerIds.includes("anthropic"),
    "Has google, openai, anthropic providers"
  )

  // --- Frontend Pages ---
  console.log("\n🖥️  Frontend Page Tests")

  const loginPage = await pageStatus("/login")
  assert(loginPage === 200, "GET /login returns 200")

  const rootPage = await pageStatus("/")
  assert(rootPage === 200 || rootPage === 307, "GET / returns 200 or 307")

  const agentPage = await pageStatus("/agent")
  assert(agentPage === 200, "GET /agent returns 200")

  const studioPage = await pageStatus("/data-studio")
  assert(studioPage === 200, "GET /data-studio returns 200")

  const chartsPage = await pageStatus("/custom-charts")
  assert(chartsPage === 200, "GET /custom-charts returns 200")

  const dbPage = await pageStatus("/databases")
  assert(dbPage === 200, "GET /databases returns 200")

  const adminPage = await pageStatus("/admin/users")
  assert(adminPage === 200, "GET /admin/users returns 200")

  // --- Summary ---
  console.log("\n" + "=".repeat(40))
  console.log(`Results: ${passed} passed, ${failed} failed, ${passed + failed} total`)
  if (failed > 0) {
    console.log("\n❌ SOME TESTS FAILED")
    process.exit(1)
  } else {
    console.log("\n✅ ALL TESTS PASSED")
  }
}

main().catch((e) => {
  console.error("Test runner error:", e)
  process.exit(1)
})
