import * as crypto from "node:crypto"
import * as fs from "node:fs"
import * as os from "node:os"
import * as path from "node:path"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import * as entry from "../src/index.js"
import { BANNER, MULTIPLE_PLANS_NOTICE, REMINDER } from "../src/core.js"

// The host is the boundary under test. Its v2 callbacks receive mutable events,
// not the v1 (input, output) pair. Fixtures follow @opencode/plugin 2.0.21.
type Callback = (event: any) => Promise<void>
type Definition = { id: string; server: unknown; setup(context: any): Promise<() => Promise<void>> }
const definition = (entry as unknown as { default: Definition }).default
const PLAN = "### Phase 1: A\n- **Status:** in_progress\n"
const envKeys = ["PLANNING_DISABLED", "PWF_PLAN_ROOT", "PLAN_ID", "PWF_GATE_CAP"]
let root: string
let sessions: Record<string, { location: { directory: string }; parentID?: string; subpath?: string }>
let savedEnv: Record<string, string | undefined>
let cleanup: (() => Promise<void>) | undefined

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-v2-")))
  sessions = { main: { location: { directory: root } }, child: { location: { directory: root }, parentID: "main" } }
  savedEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]))
  for (const key of envKeys) delete process.env[key]
})

afterEach(async () => {
  await cleanup?.()
  cleanup = undefined
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
  fs.rmSync(root, { recursive: true, force: true })
})

function plan(base = root, gated = false) {
  fs.writeFileSync(path.join(base, "task_plan.md"), PLAN)
  fs.writeFileSync(path.join(base, "progress.md"), "- started\n")
  if (gated) {
    fs.writeFileSync(path.join(base, ".mode"), "autonomous gate\n")
    fs.writeFileSync(path.join(base, ".plan-attestation"), crypto.createHash("sha256").update(PLAN).digest("hex"))
  }
}

function request(sessionID = "main") {
  return { sessionID, system: [] as Array<{ type: string; text: string }>, messages: [], tools: {}, options: {} }
}

async function load() {
  expect(definition, "the v2 loader requires a default definition").toBeDefined()
  const hooks: Record<string, Callback> = {}
  const tools: Record<string, any> = {}
  const prompts: any[] = []
  const disposed: string[] = []
  const queue: any[] = []
  let wake: (() => void) | undefined
  let streamClosed = false
  let failLookup = false
  const registration = (name: string) => ({ dispose: async () => { disposed.push(name) } })
  cleanup = await definition.setup({
    location: { directory: root },
    session: {
      get: async ({ sessionID }: { sessionID: string }) => {
        if (failLookup || !sessions[sessionID]) throw new Error("session unavailable")
        return sessions[sessionID]
      },
      prompt: async (input: any) => { prompts.push(input); return {} },
      hook: async (name: string, callback: Callback) => {
        hooks[name] = callback
        return registration(name)
      },
    },
    tool: {
      hook: async (name: string, callback: Callback) => {
        hooks[name] = callback
        return registration(name)
      },
      transform: async (callback: (editor: any) => void) => {
        callback({ add: (tool: any) => { tools[tool.name] = tool } })
        return registration("tools")
      },
    },
    event: {
      async *subscribe({ signal }: { signal: AbortSignal }) {
        const abort = () => wake?.()
        signal.addEventListener("abort", abort)
        try {
          while (!signal.aborted) {
            if (!queue.length) await new Promise<void>((resolve) => { wake = resolve })
            if (signal.aborted) return
            while (queue.length) {
              const item = queue.shift()
              yield item.event
              item.resolve()
            }
          }
        } finally {
          signal.removeEventListener("abort", abort)
          streamClosed = true
        }
      },
    },
  })
  return {
    hooks, tools, prompts, disposed,
    lookupFails: (value: boolean) => { failLookup = value },
    closed: () => streamClosed,
    emit: (event: any) => new Promise<void>((resolve) => { queue.push({ event, resolve }); wake?.() }),
    idle: (sessionID = "main") => new Promise<void>((resolve) => {
      queue.push({ event: { type: "session.status", data: { sessionID, status: { type: "idle" } } }, resolve })
      wake?.()
    }),
  }
}

describe("OpenCode v2", () => {
  it("exports one definition accepted by v2 and the v1 server-module loader", async () => {
    expect(definition).toMatchObject({ id: "opencode-planning-with-files", server: entry.PlanningWithFiles, setup: expect.any(Function) })
    const dogfood = await import("../../../plugins/planning-with-files.js")
    expect((dogfood as unknown as { default: unknown }).default).toBe(definition)
  })

  it("injects current planning context once without altering the user's messages", async () => {
    plan()
    const { hooks } = await load()
    const event = request()
    event.messages.push({ role: "user", content: "hello" } as never)
    await hooks.context(event)
    await hooks.context(event)
    expect(event.system).toHaveLength(1)
    expect(event.system[0]).toMatchObject({ type: "text", text: expect.stringContaining(BANNER) })
    expect(event.system[0].text).toContain(PLAN.trim())
    expect(event.messages).toEqual([{ role: "user", content: "hello" }])
  })

  it("respects session locations, subpaths and explicit project pins", async () => {
    const other = path.join(root, "other")
    const nested = path.join(other, "nested")
    fs.mkdirSync(nested, { recursive: true })
    plan(nested)
    sessions.main = { location: { directory: other }, subpath: "nested" }
    const { hooks, tools } = await load()
    const event = request()
    await hooks.context(event)
    expect(event.system[0].text).toContain(PLAN.trim())
    const result = JSON.parse((await tools.pwf_status.execute({}, { sessionID: "main" })).content)
    expect(result.plan_dir).toBe(nested)
    process.env.PWF_PLAN_ROOT = root
    const pinned = request()
    await hooks.context(pinned)
    expect(pinned.system).toHaveLength(0)
  })

  it("respects opt-out, invalid pins and multiple named plans", async () => {
    plan()
    const { hooks, tools } = await load()
    process.env.PLANNING_DISABLED = "1"
    const disabled = request()
    await hooks.context(disabled)
    expect(disabled.system).toHaveLength(0)
    expect(JSON.parse((await tools.pwf_init.execute({}, { sessionID: "main" })).content).ok).toBe(false)
    delete process.env.PLANNING_DISABLED
    process.env.PWF_PLAN_ROOT = path.join(root, "missing")
    const broken = request()
    await hooks.context(broken)
    expect(broken.system).toHaveLength(0)
    delete process.env.PWF_PLAN_ROOT
    for (const id of ["a", "b"]) {
      const dir = path.join(root, ".planning", id)
      fs.mkdirSync(dir, { recursive: true })
      plan(dir)
    }
    const ambiguous = request()
    await hooks.context(ambiguous)
    expect(ambiguous.system[0].text).toBe(MULTIPLE_PLANS_NOTICE)
  })

  it("follows a moved session instead of reusing its previous project", async () => {
    plan()
    const moved = path.join(root, "moved")
    fs.mkdirSync(moved)
    const host = await load()
    await host.hooks.context(request())
    plan(moved)
    fs.appendFileSync(path.join(moved, "task_plan.md"), "\nMOVED SESSION PLAN\n")
    sessions.main = { location: { directory: moved } }
    const event = request()
    await host.hooks.context(event)
    expect(event.system[0].text).toContain("MOVED SESSION PLAN")
    const status = JSON.parse((await host.tools.pwf_status.execute({}, { sessionID: "main" })).content)
    expect(status.plan_dir).toBe(moved)
  })

  it("preserves text, structured output and attachments when adding write reminders", async () => {
    plan()
    const { hooks } = await load()
    const text = { tool: "write", sessionID: "main", status: "completed", result: { content: "saved", output: { ok: true } } }
    await hooks["execute.after"](text)
    expect(text.result.content).toBe(`saved\n\n${REMINDER}`)
    expect(text.result.output).toEqual({ ok: true })
    const attachment = { type: "file", uri: "file:///tmp/example.png", mime: "image/png" }
    const rich = { tool: "edit", sessionID: "main", status: "completed", result: { content: [attachment], metadata: { title: "saved" } } }
    await hooks["execute.after"](rich)
    expect(rich.result.content).toEqual([attachment, { type: "text", text: REMINDER }])
    expect(rich.result.metadata).toEqual({ title: "saved" })
    const failed = { tool: "write", sessionID: "main", status: "error", error: { message: "denied" } }
    await hooks["execute.after"](failed)
    expect(failed).not.toHaveProperty("result")
    const read = { tool: "read", sessionID: "main", status: "completed", result: { content: "read" } }
    await hooks["execute.after"](read)
    expect(read.result.content).toBe("read")
  })

  it("carries the plan pointer and attestation through compaction", async () => {
    plan(root, true)
    const { hooks } = await load()
    const event = request()
    await hooks.compaction(event)
    expect(event.system[0].text).toContain("task_plan.md")
    expect(event.system[0].text).toContain(`Plan-SHA256: ${crypto.createHash("sha256").update(PLAN).digest("hex")}`)
  })

  it("registers working planning tools using the v2 result format", async () => {
    const { tools } = await load()
    expect(Object.keys(tools).sort()).toEqual(["pwf_check", "pwf_init", "pwf_status"])
    const result = JSON.parse((await tools.pwf_init.execute({ name: "v2 plan" }, { sessionID: "main" })).content)
    expect(result.ok).toBe(true)
    expect(fs.existsSync(path.join(result.plan_dir, "task_plan.md"))).toBe(true)
    const status = JSON.parse((await tools.pwf_status.execute({}, { sessionID: "main" })).content)
    expect(status.plan_id).toBe(result.plan_id)
    const checked = JSON.parse((await tools.pwf_check.execute({}, { sessionID: "main" })).content)
    expect(checked.complete).toBe(false)
  })

  it("re-prompts once on v2 idle and releases the gate when progress stalls", async () => {
    plan(root, true)
    const host = await load()
    await host.idle()
    expect(host.prompts).toHaveLength(1)
    expect(host.prompts[0]).toMatchObject({ sessionID: "main", text: expect.stringContaining("[planning-with-files]") })
    await host.idle()
    expect(host.prompts).toHaveLength(1)
    await host.hooks.context(request())
    await host.idle()
    expect(fs.readFileSync(path.join(root, ".gate_last_progress"), "utf8")).toBeTruthy()
    expect(host.prompts).toHaveLength(1)
  })

  it("never gates child or unknown sessions and retries a failed session lookup", async () => {
    plan(root, true)
    const host = await load()
    await host.idle("child")
    await host.idle("missing")
    host.lookupFails(true)
    await host.idle()
    await host.hooks.context(request())
    expect(host.prompts).toHaveLength(0)
    host.lookupFails(false)
    await host.idle()
    expect(host.prompts).toHaveLength(1)
  })

  it("stops the event stream and disposes all registrations on unload", async () => {
    const host = await load()
    await cleanup!()
    cleanup = undefined
    expect(host.closed()).toBe(true)
    expect(host.disposed.sort()).toEqual(["compaction", "context", "execute.after", "tools"])
  })

  it("disposes earlier registrations when a later registration fails", async () => {
    let disposed = false
    await expect(definition.setup({
      location: { directory: root },
      session: { hook: async () => ({ dispose: async () => { disposed = true } }) },
      tool: { hook: async () => { throw new Error("registration failed") } },
    })).rejects.toThrow("registration failed")
    expect(disposed).toBe(true)
  })
})
