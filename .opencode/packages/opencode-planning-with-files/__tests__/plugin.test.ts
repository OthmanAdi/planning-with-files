import * as crypto from "node:crypto"
import * as fs from "node:fs"
import * as os from "node:os"
import * as path from "node:path"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { PlanningWithFiles } from "../src/index.js"
import { BANNER, MULTIPLE_PLANS_NOTICE, REMINDER } from "../src/core.js"

type Hooks = Awaited<ReturnType<typeof PlanningWithFiles>>

const PLAN = "### Phase 1: A\n- **Status:** complete\n\n### Phase 2: B\n- **Status:** in_progress\n"

let root: string
let prompts: unknown[]
let sessions: Record<string, { directory: string; parentID?: string }>
let lookupFails: boolean
const savedEnv: Record<string, string | undefined> = {}

function sha(file: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex")
}

async function load(): Promise<Hooks> {
  const client = {
    session: {
      get: async ({ path: { id } }: { path: { id: string } }) => {
        if (lookupFails) throw new Error("offline")
        return { data: sessions[id] ? { id, ...sessions[id] } : undefined }
      },
      promptAsync: async (opts: unknown) => {
        prompts.push(opts)
        return {}
      },
    },
  }
  return PlanningWithFiles({ client, directory: root, worktree: root, project: {}, $: {} } as never)
}

function gatedRoot(): void {
  fs.writeFileSync(path.join(root, "task_plan.md"), PLAN)
  fs.writeFileSync(path.join(root, "progress.md"), "- started\n")
  fs.writeFileSync(path.join(root, ".mode"), "autonomous gate\n")
  fs.writeFileSync(path.join(root, ".plan-attestation"), `${sha(path.join(root, "task_plan.md"))}\n`)
}

function message(sessionID = "ses_main") {
  return {
    input: { sessionID },
    output: { message: { id: "msg_1", sessionID, role: "user" as const, time: { created: 1 } }, parts: [] as Array<{ type: string; text?: string; synthetic?: boolean }> },
  }
}

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-oc-plugin-")))
  prompts = []
  lookupFails = false
  sessions = { ses_main: { directory: root }, ses_child: { directory: root, parentID: "ses_main" } }
  for (const key of ["PLANNING_DISABLED", "PWF_PLAN_ROOT", "PLAN_ID", "PWF_GATE_CAP"]) {
    savedEnv[key] = process.env[key]
    delete process.env[key]
  }
})

afterEach(() => {
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
  fs.rmSync(root, { recursive: true, force: true })
})

describe("chat.message", () => {
  it("appends the framed plan as a synthetic part, once per message", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const hooks = await load()
    const { input, output } = message()
    await hooks["chat.message"]!(input as never, output as never)
    expect(output.parts).toHaveLength(1)
    expect(output.parts[0].type).toBe("text")
    expect(output.parts[0].synthetic).toBe(true)
    expect(output.parts[0].text!.startsWith(BANNER)).toBe(true)
  })

  it("refuses two named plans without PLAN_ID with the multiple-plans notice, and PLAN_ID selects (#240)", async () => {
    for (const slug of ["2026-09-02-a", "2026-09-02-b"]) {
      fs.mkdirSync(path.join(root, ".planning", slug), { recursive: true })
      fs.writeFileSync(path.join(root, ".planning", slug, "task_plan.md"), `# ${slug}\n`)
    }
    fs.writeFileSync(path.join(root, ".planning", ".active_plan"), "2026-09-02-a\n")
    const hooks = await load()
    const ambiguous = message()
    await hooks["chat.message"]!(ambiguous.input as never, ambiguous.output as never)
    expect(ambiguous.output.parts).toHaveLength(1)
    expect(ambiguous.output.parts[0].text).toBe(MULTIPLE_PLANS_NOTICE)

    process.env.PLAN_ID = "2026-09-02-b"
    const selected = message()
    await hooks["chat.message"]!(selected.input as never, selected.output as never)
    expect(selected.output.parts[0].text).toContain("# 2026-09-02-b")
    delete process.env.PLAN_ID
  })

  it("injects nothing without a plan, when disabled, or for a broken pin; announces ambiguity", async () => {
    const hooks = await load()
    const none = message()
    await hooks["chat.message"]!(none.input as never, none.output as never)
    expect(none.output.parts).toHaveLength(0)

    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    process.env.PLANNING_DISABLED = "1"
    const disabled = message()
    await hooks["chat.message"]!(disabled.input as never, disabled.output as never)
    expect(disabled.output.parts).toHaveLength(0)
    delete process.env.PLANNING_DISABLED

    process.env.PWF_PLAN_ROOT = path.join(root, "missing")
    const broken = message()
    await hooks["chat.message"]!(broken.input as never, broken.output as never)
    expect(broken.output.parts).toHaveLength(0)
    delete process.env.PWF_PLAN_ROOT

    fs.mkdirSync(path.join(root, "svc", ".planning", "2026-09-02-child"), { recursive: true })
    fs.writeFileSync(path.join(root, "svc", ".planning", "2026-09-02-child", "task_plan.md"), "# CHILD\n")
    const ambiguous = message()
    await hooks["chat.message"]!(ambiguous.input as never, ambiguous.output as never)
    expect(ambiguous.output.parts[0].text).toContain("Ambiguous plan")
    expect(ambiguous.output.parts[0].text).not.toContain("# Plan")

    process.env.PWF_PLAN_ROOT = root
    const pinned = message()
    await hooks["chat.message"]!(pinned.input as never, pinned.output as never)
    expect(pinned.output.parts[0].text!.startsWith(BANNER)).toBe(true)
  })

  it("resolves the plan from the session's own directory, not the server directory", async () => {
    const other = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-oc-other-")))
    try {
      fs.writeFileSync(path.join(other, "task_plan.md"), "# OTHER PROJECT\n")
      sessions.ses_other = { directory: other }
      const hooks = await load()
      const { input, output } = message("ses_other")
      await hooks["chat.message"]!(input as never, output as never)
      expect(output.parts[0].text).toContain("OTHER PROJECT")
    } finally {
      fs.rmSync(other, { recursive: true, force: true })
    }
  })
})

describe("tool.execute.after and compaction", () => {
  it("appends the reminder to write-like tool output only when a plan exists", async () => {
    const hooks = await load()
    const before = { title: "t", output: "ok", metadata: {} }
    await hooks["tool.execute.after"]!({ tool: "write", sessionID: "ses_main", callID: "c", args: {} } as never, before as never)
    expect(before.output).toBe("ok")
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const write = { title: "t", output: "ok", metadata: {} }
    await hooks["tool.execute.after"]!({ tool: "write", sessionID: "ses_main", callID: "c", args: {} } as never, write as never)
    expect(write.output).toBe(`ok\n\n${REMINDER}`)
    const read = { title: "t", output: "ok", metadata: {} }
    await hooks["tool.execute.after"]!({ tool: "read", sessionID: "ses_main", callID: "c", args: {} } as never, read as never)
    expect(read.output).toBe("ok")
  })

  it("keeps the plan pointer and attestation in the compaction context", async () => {
    gatedRoot()
    const hooks = await load()
    const output = { context: [] as string[] }
    await hooks["experimental.session.compacting"]!({ sessionID: "ses_main" } as never, output as never)
    expect(output.context).toHaveLength(1)
    expect(output.context[0]).toContain("task_plan.md in the project root")
    expect(output.context[0]).toContain(`Plan-SHA256: ${sha(path.join(root, "task_plan.md"))}`)
  })
})

describe("session.idle gate", () => {
  it("re-prompts a gated session with the gate reason, then stalls, and never touches child sessions or legacy plans", async () => {
    gatedRoot()
    const hooks = await load()
    const idle = (sessionID: string) => hooks.event!({ event: { type: "session.idle", properties: { sessionID } } } as never)
    await idle("ses_main")
    expect(prompts).toHaveLength(1)
    const body = (prompts[0] as { body: { parts: Array<{ text: string }> }; path: { id: string } })
    expect(body.path.id).toBe("ses_main")
    expect(body.body.parts[0].text).toContain("phase 'Phase 2: B' is in_progress (1/2 complete, gate block 1/20)")
    // a second idle while the re-prompt is in flight is ignored; after the next
    // message the stall rule (no ledger progress) releases the stop
    await idle("ses_main")
    expect(prompts).toHaveLength(1)
    const { input, output } = message()
    await hooks["chat.message"]!(input as never, output as never)
    await idle("ses_main")
    expect(prompts).toHaveLength(1)
    await idle("ses_child")
    expect(prompts).toHaveLength(1)
    fs.unlinkSync(path.join(root, ".mode"))
    await idle("ses_main")
    expect(prompts).toHaveLength(1)
  })
})

describe("review fixes", () => {
  it("does not cache a failed session lookup and never gates an unknown session", async () => {
    const other = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-oc-other-")))
    try {
      fs.writeFileSync(path.join(other, "task_plan.md"), "# OTHER PROJECT\n")
      fs.writeFileSync(path.join(other, ".mode"), "autonomous gate\n")
      fs.writeFileSync(path.join(other, ".plan-attestation"), `${sha(path.join(other, "task_plan.md"))}\n`)
      fs.writeFileSync(path.join(root, "task_plan.md"), "# SERVER ROOT PLAN\n")
      sessions.ses_other = { directory: other }
      const hooks = await load()
      lookupFails = true
      const first = message("ses_other")
      await hooks["chat.message"]!(first.input as never, first.output as never)
      expect(first.output.parts[0]?.text).toContain("SERVER ROOT PLAN")
      await hooks.event!({ event: { type: "session.idle", properties: { sessionID: "ses_other" } } } as never)
      expect(prompts).toHaveLength(0)
      lookupFails = false
      const second = message("ses_other")
      await hooks["chat.message"]!(second.input as never, second.output as never)
      expect(second.output.parts[0]?.text).toContain("OTHER PROJECT")
    } finally {
      fs.rmSync(other, { recursive: true, force: true })
    }
  })

  it("injects at most once per message", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const hooks = await load()
    const { input, output } = message()
    await hooks["chat.message"]!(input as never, output as never)
    await hooks["chat.message"]!(input as never, output as never)
    expect(output.parts).toHaveLength(1)
  })

  it("tools follow the pin and refuse when planning is disabled or the pin is broken", async () => {
    const pinned = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-oc-pin-")))
    try {
      const hooks = await load()
      const context = { sessionID: "ses_main", messageID: "m", agent: "build", directory: root, worktree: root, abort: new AbortController().signal, metadata() {}, async ask() {} }
      process.env.PWF_PLAN_ROOT = pinned
      const init = JSON.parse(String(await hooks.tool!.pwf_init.execute({} as never, context as never)))
      expect(init.ok).toBe(true)
      expect(fs.existsSync(path.join(pinned, "task_plan.md"))).toBe(true)
      expect(fs.existsSync(path.join(root, "task_plan.md"))).toBe(false)
      const status = JSON.parse(String(await hooks.tool!.pwf_status.execute({} as never, context as never)))
      expect(status.project_dir).toBe(pinned)
      process.env.PWF_PLAN_ROOT = path.join(root, "missing")
      const broken = JSON.parse(String(await hooks.tool!.pwf_status.execute({} as never, context as never)))
      expect(broken.ok).toBe(false)
      delete process.env.PWF_PLAN_ROOT
      process.env.PLANNING_DISABLED = "1"
      const disabled = JSON.parse(String(await hooks.tool!.pwf_check.execute({} as never, context as never)))
      expect(disabled.ok).toBe(false)
    } finally {
      fs.rmSync(pinned, { recursive: true, force: true })
    }
  })
})

describe("tools", () => {
  it("pwf_init, pwf_status and pwf_check operate on the tool context directory", async () => {
    const hooks = await load()
    const context = { sessionID: "ses_main", messageID: "m", agent: "build", directory: root, worktree: root, abort: new AbortController().signal, metadata() {}, async ask() {} }
    const init = JSON.parse(String(await hooks.tool!.pwf_init.execute({ name: "Night run", mode: "gated" } as never, context as never)))
    expect(init.ok).toBe(true)
    expect(init.plan_id).toMatch(/-night-run$/)
    expect(init.attestation).toMatch(/^[0-9a-f]{64}$/)
    const status = JSON.parse(String(await hooks.tool!.pwf_status.execute({} as never, context as never)))
    expect(status.plan_id).toBe(init.plan_id)
    expect(status.mode).toBe("autonomous gate")
    const check = JSON.parse(String(await hooks.tool!.pwf_check.execute({} as never, context as never)))
    expect(check.complete).toBe(false)
    expect(check.message).toContain("Plan incomplete")
  })
})
