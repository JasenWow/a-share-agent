import { describe, expect, test } from "bun:test"
import { buildArgv } from "./cli-runner"

describe("buildArgv", () => {
  test("starts with aquan <domain> <action>", () => {
    const argv = buildArgv("stock", "hist", {})
    expect(argv).toEqual(["aquan", "stock", "hist"])
  })

  test("converts camelCase keys to kebab-case flags", () => {
    const argv = buildArgv("experiment", "record", {
      stepIndex: 3,
      stepType: "explore",
      finalNav: 1000,
    })
    expect(argv).toContain("--step-index")
    expect(argv).toContain("3")
    expect(argv).toContain("--step-type")
    expect(argv).toContain("explore")
    expect(argv).toContain("--final-nav")
    expect(argv).toContain("1000")
  })

  test("skips null and undefined values", () => {
    const argv = buildArgv("stock", "hist", {
      code: "600519",
      start: null,
      end: undefined,
      period: "daily",
    })
    expect(argv).toContain("--code")
    expect(argv).not.toContain("--start")
    expect(argv).not.toContain("--end")
    expect(argv).toContain("--period")
  })

  test("renders booleans as bare flags (true) or skips (false)", () => {
    const argv = buildArgv("stock", "hist", {
      json: true,
      verbose: false,
    })
    expect(argv).toContain("--json")
    // false → no flag at all
    expect(argv).not.toContain("--verbose")
  })

  test("stringifies non-string non-boolean values", () => {
    const argv = buildArgv("factor", "register", {
      ic: 0.08,
      limit: 50,
    })
    expect(argv).toContain("--ic")
    expect(argv).toContain("0.08")
    expect(argv).toContain("--limit")
    expect(argv).toContain("50")
  })

  test("action is passed through untouched (not converted to flag)", () => {
    const argv = buildArgv("stock", "northbound", {})
    expect(argv[2]).toBe("northbound")
    expect(argv).toHaveLength(3)
  })

  test("preserves ALLCAPS → kebab boundaries (URLFoo → url-foo)", () => {
    const argv = buildArgv("stock", "hist", { URLFoo: "x" })
    expect(argv.some((a) => a === "--url-foo" || a === "--u-r-l-foo")).toBe(true)
  })
})
