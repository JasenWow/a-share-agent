import { describe, expect, test, mock } from "bun:test"
import { ALL_CLI_TOOLS, stockTool, factorTool, experimentTool, qlibTool } from "./cli-tools"
import * as cliRunner from "./cli-runner"

const runCliMock = mock(cliRunner.runCli)
mock.module("./cli-runner", () => ({
  runCli: runCliMock,
  buildArgv: cliRunner.buildArgv,
}))

describe("ALL_CLI_TOOLS", () => {
  test("exposes exactly four domain tools", () => {
    const names = ALL_CLI_TOOLS.map((t) => t.name).sort()
    expect(names).toEqual(["experiment", "factor", "qlib", "stock"])
  })

  test("every tool has label + description + parameters + execute", () => {
    for (const tool of ALL_CLI_TOOLS) {
      expect(typeof tool.name).toBe("string")
      expect(tool.name.length).toBeGreaterThan(0)
      expect(typeof tool.label).toBe("string")
      expect(typeof tool.description).toBe("string")
      expect(tool.description.length).toBeGreaterThan(20)
      expect(tool.parameters).toBeDefined()
      expect(typeof tool.execute).toBe("function")
    }
  })
})

describe("stockTool", () => {
  test("description lists the key actions", () => {
    const d = stockTool.description
    for (const action of ["spot", "hist", "daily", "income", "northbound", "health"]) {
      expect(d).toContain(action)
    }
  })

  test("execute spawns aquan stock with the action + flags", async () => {
    runCliMock.mockReset()
    runCliMock.mockResolvedValue({ ok: true, stdout: "code\nclose\n600519 1685.5", stderr: "", exitCode: 0 })
    const result = await stockTool.execute("tc1", { action: "hist", code: "600519", start: "20240101" })
    expect(runCliMock).toHaveBeenCalledTimes(1)
    const args = runCliMock.mock.calls[0]
    expect(args[0]).toBe("stock")
    expect(args[1]).toBe("hist")
    expect(args[2]).toMatchObject({ code: "600519", start: "20240101" })
    expect(result.content[0].type).toBe("text")
    expect((result.content[0] as { text: string }).text).toContain("600519")
  })

  test("execute rejects missing action", async () => {
    runCliMock.mockReset()
    const result = await stockTool.execute("tc1", { code: "600519" })
    expect(runCliMock).not.toHaveBeenCalled()
    const text = (result.content[0] as { text: string }).text
    expect(text).toMatch(/action.*required/i)
  })

  test("execute surfaces CLI failure as text", async () => {
    runCliMock.mockReset()
    runCliMock.mockResolvedValue({
      ok: false,
      stdout: "",
      stderr: "MCP server akshare unreachable",
      exitCode: 1,
    })
    const result = await stockTool.execute("tc1", { action: "health" })
    const text = (result.content[0] as { text: string }).text
    expect(text).toContain("failed")
    expect(text).toContain("unreachable")
  })
})

describe("factorTool / experimentTool / qlibTool", () => {
  test("factorTool describes register + transitions", () => {
    const d = factorTool.description
    expect(d).toContain("register")
    expect(d).toContain("promote")
    expect(d).toContain("deprecate")
  })

  test("experimentTool describes list + best + steps", () => {
    const d = experimentTool.description
    expect(d).toContain("list")
    expect(d).toContain("best")
    expect(d).toContain("steps")
  })

  test("qlibTool describes eval + operators + universe", () => {
    const d = qlibTool.description
    expect(d).toContain("eval")
    expect(d).toContain("operators")
    expect(d).toContain("universe")
  })
})
