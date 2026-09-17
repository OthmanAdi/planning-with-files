import * as crypto from "node:crypto"
import * as fs from "node:fs"
import * as os from "node:os"
import * as path from "node:path"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { PreStepDecision } from "@deepseek-ai/dsh-agent"
import type { CommandDefinition, CommandResult } from "@deepseek-ai/dsh-commands"
import { createUserMessage } from "@deepseek-ai/dsh-llm"
import type { UserMessage } from "@deepseek-ai/dsh-session"
import type { PostToolDecision, ToolDefinition } from "@deepseek-ai/dsh-tools"
import { Config, apply, inject, name } from "../src/index.js"
import { BANNER, MULTIPLE_PLANS_NOTICE, REMINDER, VERSION } from "../src/core.js"

type Listener = (...args: never[]) => unknown
type Loaded = {
  listeners: Map<string, Listener[]>
  commands: Map<string, CommandDefinition>
  tools: Map<string, ToolDefinition>
  warn: ReturnType<typeof vi.fn>
}
type Header = { id: string; cwd?: string; origin?: "subagent"; delegationDepth?: number }
type FakeAgent = { id: string; session: { id: string; header: Header }; inject: ReturnType<typeof vi.fn>; steer: ReturnType<typeof vi.fn> }

const PLAN = "### Phase 1: A\n- **Status:** complete\n\n### Phase 2: B\n- **Status:** in_progress\n"
const DONE = "### Phase 1: A\n- **Status:** complete\n\n### Phase 2: B\n- **Status:** complete\n"
const SIGNAL = new AbortController().signal

let root: string
const savedEnv: Record<string, string | undefined> = {}

function sha(file: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex")
}

/** Drive apply() against a fake Cordis context that records listeners, commands and tools. */
function load(config: Partial<Config> = {}): Loaded {
  const listeners = new Map<string, Listener[]>()
  const commands = new Map<string, CommandDefinition>()
  const tools = new Map<string, ToolDefinition>()
  const warn = vi.fn()
  const ctx = {
    on(event: string, listener: Listener) {
      listeners.set(event, [...(listeners.get(event) ?? []), listener])
      return () => true
    },
    inject(_deps: string[], callback: (scoped: unknown) => void) {
      callback(ctx)
    },
    commands: {
      register(definition: CommandDefinition) {
        commands.set(definition.name, definition)
        return () => {}
      },
    },
    tools: {
      register(definition: ToolDefinition) {
        tools.set(definition.name, definition)
        return () => {}
      },
    },
    logger: { warn },
  }
  apply(ctx as never, { enabled: true, gate: true, ...config })
  return { listeners, commands, tools, warn }
}

function fire(loaded: Loaded, event: string, ...args: unknown[]): unknown {
  const registered = loaded.listeners.get(event) ?? []
  expect(registered).toHaveLength(1)
  return registered[0](...(args as never[]))
}

function agentFor(cwd: string | undefined, header: Partial<Header> = {}, id = "ses_main"): FakeAgent {
  return { id, session: { id, header: { id, cwd, ...header } }, inject: vi.fn(), steer: vi.fn() }
}

function userPrompt(text = "hi"): UserMessage {
  return createUserMessage({ content: [{ type: "text", text }], source: { kind: "user" } })
}

function pluginMessage(text: string, plugin = name): UserMessage {
  return createUserMessage({ content: [{ type: "text", text }], source: { kind: "plugin", plugin } })
}

function textOf(message: UserMessage, index = 0): string {
  const block = message.content[index]
  return block?.type === "text" ? block.text : ""
}

async function preStep(loaded: Loaded, agent: FakeAgent, messages: UserMessage[]): Promise<PreStepDecision> {
  const downstream: PreStepDecision = { kind: "enter", messages }
  return (await fire(loaded, "agent/pre-step", { agent, messages, turn: 1, step: 1, signal: SIGNAL }, async () => downstream)) as PreStepDecision
}

function entered(decision: PreStepDecision): UserMessage[] {
  expect(decision.kind).toBe("enter")
  return decision.kind === "enter" ? decision.messages : []
}

function injected(decision: PreStepDecision): UserMessage {
  const messages = entered(decision)
  expect(messages).toHaveLength(2)
  expect(messages[1].source).toEqual({ kind: "plugin", plugin: name })
  return messages[1]
}

async function postExecute(
  loaded: Loaded,
  agent: FakeAgent | undefined,
  tool: string,
  args: unknown = {},
  opts: { isError?: boolean; downstream?: PostToolDecision } = {},
): Promise<PostToolDecision> {
  const exec = { callId: "c1", rootCallId: "c1", name: tool, arguments: args, agent, signal: SIGNAL, token: Symbol("t") }
  const result = opts.isError
    ? { isError: true, error: { code: "TOOL_ERROR", message: "boom" }, content: [{ type: "text", text: "boom" }] }
    : { isError: false, value: "ok", content: [{ type: "text", text: "ok" }] }
  const downstream = opts.downstream ?? { kind: "accept" }
  return (await fire(loaded, "tools/post-execute", exec, result, async () => downstream)) as PostToolDecision
}

function contexts(decision: PostToolDecision): UserMessage[] {
  return decision.additionalContexts ?? []
}

function stop(loaded: Loaded, agent: FakeAgent): unknown {
  return fire(loaded, "agent/turn-stopping", { agent, turn: 1, signal: SIGNAL })
}

/** The durable compaction/end event of an agent's session, as the session log emits it. */
function compacted(loaded: Loaded, agent: FakeAgent, error?: string): unknown {
  const event = { type: "compaction/end", seq: 40, time: Date.now(), data: { compactionId: "cmp_1", turn: null, ...(error === undefined ? {} : { error }) } }
  return fire(loaded, "session/event", agent.session, event)
}

function disposed(loaded: Loaded, agent: FakeAgent): unknown {
  return fire(loaded, "session/disposed", agent.session)
}

function command(loaded: Loaded, commandName: string, agent: FakeAgent, rawInput = ""): Promise<CommandResult> {
  const definition = loaded.commands.get(commandName)
  expect(definition).toBeDefined()
  return Promise.resolve(definition!.handler({ commandId: "cmd_1" as never, agent: agent as never, rawInput, attachments: [], signal: SIGNAL }))
}

async function tool(loaded: Loaded, toolName: string, args: unknown, agent: FakeAgent | undefined): Promise<Record<string, unknown>> {
  const definition = loaded.tools.get(toolName)
  expect(definition).toBeDefined()
  return JSON.parse(String(await definition!.execute(args, { agent } as never))) as Record<string, unknown>
}

function gatedRoot(dir = root, plan = PLAN): void {
  fs.writeFileSync(path.join(dir, "task_plan.md"), plan)
  fs.writeFileSync(path.join(dir, "progress.md"), "- started\n")
  fs.writeFileSync(path.join(dir, ".mode"), "autonomous gate\n")
  fs.writeFileSync(path.join(dir, ".plan-attestation"), `${sha(path.join(dir, "task_plan.md"))}\n`)
}

function namedPlan(slug: string, text: string, pointer = true): void {
  const dir = path.join(root, ".planning", slug)
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(path.join(dir, "task_plan.md"), text)
  if (pointer) fs.writeFileSync(path.join(root, ".planning", ".active_plan"), `${slug}\n`)
}

function ledgerAdvance(dir = root): void {
  fs.appendFileSync(path.join(dir, "ledger-1.jsonl"), `{"t":${Date.now()}}\n`)
}

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-dsh-plugin-")))
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

describe("plugin shape", () => {
  it("exports the Cordis plugin contract, defaults both switches on, and registers nothing when disabled", () => {
    expect(name).toBe("planning-with-files")
    expect([...inject]).toEqual([])
    const validated = Config["~standard"].validate(undefined) as { value?: unknown }
    expect(validated.value).toEqual({ enabled: true, gate: true })

    const off = load({ enabled: false })
    expect(off.listeners.size).toBe(0)
    expect(off.commands.size).toBe(0)
    expect(off.tools.size).toBe(0)

    const on = load()
    expect([...on.listeners.keys()].sort()).toEqual(["agent/pre-step", "agent/turn-stopping", "session/disposed", "session/event", "tools/post-execute"])
    expect([...on.commands.keys()].sort()).toEqual(["pwf", "pwf-status"])
    expect(on.commands.has("plan")).toBe(false)
    expect([...on.tools.keys()].sort()).toEqual(["pwf_check", "pwf_init", "pwf_status"])
  })
})

describe("agent/pre-step", () => {
  it("appends the framed plan as one plugin-sourced message for a root plan and for the .active_plan named plan", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const loaded = load()
    const prompt = userPrompt()
    const rootDecision = await preStep(loaded, agentFor(root), [prompt])
    expect(entered(rootDecision)[0]).toBe(prompt)
    const rootText = textOf(injected(rootDecision))
    expect(rootText.startsWith(BANNER)).toBe(true)
    expect(rootText).toContain("# Plan")
    expect(rootText).not.toContain("[planning-with-files] plan:")

    namedPlan("2026-09-02-night-run", "# NIGHT\n")
    const namedText = textOf(injected(await preStep(loaded, agentFor(root), [userPrompt()])))
    expect(namedText).toContain("[planning-with-files] plan: 2026-09-02-night-run")
    expect(namedText).toContain("# NIGHT")
    expect(namedText).not.toContain("# Plan")
  })

  it("injects nothing without a plan, when disabled, for a broken pin, or for a PLAN_ID that names no plan", async () => {
    const loaded = load()
    expect(entered(await preStep(loaded, agentFor(root), [userPrompt()]))).toHaveLength(1)

    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    namedPlan("2026-09-02-night-run", "# NIGHT\n")
    process.env.PLANNING_DISABLED = "1"
    expect(entered(await preStep(loaded, agentFor(root), [userPrompt()]))).toHaveLength(1)
    delete process.env.PLANNING_DISABLED

    process.env.PWF_PLAN_ROOT = path.join(root, "missing")
    expect(entered(await preStep(loaded, agentFor(root), [userPrompt()]))).toHaveLength(1)
    delete process.env.PWF_PLAN_ROOT

    // a stale selector ends resolution: neither the pointer nor the root plan is injected instead (#237)
    process.env.PLAN_ID = "2026-09-02-does-not-exist"
    expect(entered(await preStep(loaded, agentFor(root), [userPrompt()]))).toHaveLength(1)
    delete process.env.PLAN_ID
    expect(entered(await preStep(loaded, agentFor(root), [userPrompt()]))).toHaveLength(2)
  })

  it("does not inject again on a step that carries its own message, nor on a step without a user prompt", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const loaded = load()
    const afterInjection = [pluginMessage(`${BANNER}\n\n# Plan`), userPrompt()]
    expect(entered(await preStep(loaded, agentFor(root), afterInjection))).toEqual(afterInjection)
    const gateSteer = [pluginMessage("[planning-with-files] Gated plan incomplete: finish or update the plan, then stop.")]
    expect(entered(await preStep(loaded, agentFor(root), gateSteer))).toEqual(gateSteer)
    const otherPlugin = [pluginMessage("SessionStart context", "hooks-claude-code")]
    expect(entered(await preStep(loaded, agentFor(root), otherPlugin))).toEqual(otherPlugin)
    expect(entered(await preStep(loaded, agentFor(root), []))).toEqual([])
  })

  it("announces an ambiguous cwd once per prompt instead of a plan, and injects the plan once the root is pinned", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    fs.mkdirSync(path.join(root, "svc", ".planning", "2026-09-02-child"), { recursive: true })
    fs.writeFileSync(path.join(root, "svc", ".planning", "2026-09-02-child", "task_plan.md"), "# CHILD\n")
    const loaded = load()
    const notice = textOf(injected(await preStep(loaded, agentFor(root), [userPrompt()])))
    expect(notice).toContain("Ambiguous plan")
    expect(notice).toContain("svc")
    expect(notice).not.toContain("# Plan")
    const continuation = [pluginMessage("tool context", "some-tool")]
    expect(entered(await preStep(loaded, agentFor(root), continuation))).toEqual(continuation)

    process.env.PWF_PLAN_ROOT = root
    expect(textOf(injected(await preStep(loaded, agentFor(root), [userPrompt()]))).startsWith(BANNER)).toBe(true)
  })

  it("refuses two named plans without PLAN_ID with the multiple-plans notice, and PLAN_ID selects (#240)", async () => {
    namedPlan("2026-09-02-a", "# PLAN-A\n")
    namedPlan("2026-09-02-b", "# PLAN-B\n", false)
    const loaded = load()
    const notice = textOf(injected(await preStep(loaded, agentFor(root), [userPrompt()])))
    expect(notice).toBe(MULTIPLE_PLANS_NOTICE)
    expect(notice).not.toContain("# PLAN-A")

    process.env.PLAN_ID = "2026-09-02-b"
    const selected = textOf(injected(await preStep(loaded, agentFor(root), [userPrompt()])))
    expect(selected).toContain("# PLAN-B")
    expect(selected).not.toContain("# PLAN-A")
  })

  it("resolves the plan from the agent's own workspace and injects nothing for a session without one", async () => {
    const other = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-dsh-other-")))
    try {
      fs.writeFileSync(path.join(root, "task_plan.md"), "# SERVER ROOT PLAN\n")
      fs.writeFileSync(path.join(other, "task_plan.md"), "# OTHER PROJECT\n")
      const loaded = load()
      expect(textOf(injected(await preStep(loaded, agentFor(other), [userPrompt()])))).toContain("OTHER PROJECT")
      expect(entered(await preStep(loaded, agentFor(undefined), [userPrompt()]))).toHaveLength(1)
    } finally {
      fs.rmSync(other, { recursive: true, force: true })
    }
  })

  it("hands the downstream decision back and logs a warning when planning throws", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const loaded = load()
    const broken = {
      id: "ses_main",
      get session(): never {
        throw new Error("header exploded")
      },
      inject: vi.fn(),
      steer: vi.fn(),
    }
    const messages = [userPrompt()]
    const downstream: PreStepDecision = { kind: "enter", messages }
    const decision = await fire(loaded, "agent/pre-step", { agent: broken, messages, turn: 1, step: 1, signal: SIGNAL }, async () => downstream)
    expect(decision).toBe(downstream)
    expect(loaded.warn).toHaveBeenCalledTimes(1)
    expect(String(loaded.warn.mock.calls[0][0])).toContain("planning-with-files: agent/pre-step")
    expect(String(loaded.warn.mock.calls[0][0])).toContain("header exploded")
  })
})

describe("tools/post-execute", () => {
  it("attaches the reminder to write, edit and str_replace_editor mutations while a plan exists", async () => {
    const loaded = load()
    const agent = agentFor(root)
    expect(contexts(await postExecute(loaded, agent, "write"))).toHaveLength(0)

    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    for (const [toolName, args] of [
      ["write", { path: "a.ts", content: "" }],
      ["edit", { path: "a.ts" }],
      ["str_replace_editor", { command: "create", path: "a.ts" }],
      ["str_replace_editor", { command: "str_replace", path: "a.ts" }],
      ["str_replace_editor", { command: "insert", path: "a.ts" }],
    ] as const) {
      const attached = contexts(await postExecute(loaded, agent, toolName, args))
      expect(attached).toHaveLength(1)
      expect(textOf(attached[0])).toBe(REMINDER)
      expect(attached[0].source).toEqual({ kind: "plugin", plugin: name })
    }
    for (const [toolName, args] of [
      ["str_replace_editor", { command: "view", path: "a.ts" }],
      ["read", { path: "a.ts" }],
      ["bash", { command: "ls" }],
      ["todo_write", {}],
    ] as const) {
      expect(contexts(await postExecute(loaded, agent, toolName, args))).toHaveLength(0)
    }
    expect(contexts(await postExecute(loaded, agent, "write", {}, { isError: true }))).toHaveLength(0)
    expect(contexts(await postExecute(loaded, undefined, "write"))).toHaveLength(0)
    process.env.PLANNING_DISABLED = "1"
    expect(contexts(await postExecute(loaded, agent, "write"))).toHaveLength(0)
  })

  it("keeps a downstream context first and carries the reminder on a downstream block", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const loaded = load()
    const agent = agentFor(root)
    const other = pluginMessage("PostToolUse context", "hooks-claude-code")
    const accepted = await postExecute(loaded, agent, "write", {}, { downstream: { kind: "accept", additionalContexts: [other] } })
    expect(accepted.kind).toBe("accept")
    expect(contexts(accepted).map((message) => textOf(message))).toEqual(["PostToolUse context", REMINDER])

    const blocked = await postExecute(loaded, agent, "edit", {}, { downstream: { kind: "block", feedback: [{ type: "text", text: "no" }] } })
    expect(blocked.kind).toBe("block")
    expect(contexts(blocked).map((message) => textOf(message))).toEqual([REMINDER])
  })

  it("hands the downstream decision back and logs a warning when planning throws", async () => {
    fs.writeFileSync(path.join(root, "task_plan.md"), "# Plan\n")
    const loaded = load()
    const broken = { id: "ses_main", get session(): never { throw new Error("header exploded") }, inject: vi.fn(), steer: vi.fn() }
    const downstream: PostToolDecision = { kind: "accept" }
    const decision = await postExecute(loaded, broken as never, "write", {}, { downstream })
    expect(decision).toBe(downstream)
    expect(loaded.warn).toHaveBeenCalledTimes(1)
    expect(String(loaded.warn.mock.calls[0][0])).toContain("tools/post-execute")
  })
})

describe("compaction", () => {
  it("carries the compaction note and the plan on the next step after a successful compaction, once, and never on startup or resume", async () => {
    gatedRoot()
    const loaded = load()
    const agent = agentFor(root)
    // automatic pressure compaction runs inside the compacted turn: the continuation step gets note + plan
    await compacted(loaded, agent)
    const continuation = [pluginMessage("tool context", "some-tool")]
    const entered1 = entered(await preStep(loaded, agent, continuation))
    expect(entered1).toHaveLength(2)
    expect(entered1[0]).toBe(continuation[0])
    const message = entered1[1]
    expect(message.source).toEqual({ kind: "plugin", plugin: name })
    expect(message.content).toHaveLength(2)
    expect(textOf(message, 0)).toContain("Compaction in progress")
    expect(textOf(message, 0)).toContain("task_plan.md in the project root")
    expect(textOf(message, 0)).toContain(`Plan-SHA256: ${sha(path.join(root, "task_plan.md"))}`)
    expect(textOf(message, 1).startsWith(BANNER)).toBe(true)
    // the mark is consumed: the following continuation step gets nothing, the next prompt the plain plan
    expect(entered(await preStep(loaded, agent, continuation))).toEqual(continuation)
    const prompt = injected(await preStep(loaded, agent, [userPrompt()]))
    expect(prompt.content).toHaveLength(1)
    expect(textOf(prompt)).not.toContain("Compaction in progress")

    // a manual /compact runs idle: the next prompt carries note + plan as one message, no second plan copy
    await compacted(loaded, agent)
    const afterManual = injected(await preStep(loaded, agent, [userPrompt()]))
    expect(afterManual.content).toHaveLength(2)
    expect(textOf(afterManual, 0)).toContain("Compaction in progress")
    expect(textOf(afterManual, 1).startsWith(BANNER)).toBe(true)
    expect(agent.inject).not.toHaveBeenCalled()
  })

  it("keeps the mark across a rejected step and drops it for a step that already carries a queued plan", async () => {
    gatedRoot()
    const loaded = load()
    const agent = agentFor(root)
    await compacted(loaded, agent)
    const rejected = await fire(loaded, "agent/pre-step", { agent, messages: [], turn: 1, step: 1, signal: SIGNAL }, async () => ({ kind: "reject" }))
    expect(rejected).toEqual({ kind: "reject" })
    const held = entered(await preStep(loaded, agent, []))
    expect(held).toHaveLength(1)
    expect(textOf(held[0], 0)).toContain("Compaction in progress")

    await compacted(loaded, agent)
    const queued = [pluginMessage(`${BANNER}\n\n# Plan`), userPrompt()]
    expect(entered(await preStep(loaded, agent, queued))).toEqual(queued)
    expect(entered(await preStep(loaded, agent, []))).toEqual([])
  })

  it("re-injects nothing for a failed compaction, another session, a disposed session, an ambiguous root or a project without a plan", async () => {
    gatedRoot()
    const loaded = load()
    const agent = agentFor(root)
    await compacted(loaded, agent, "summary failed")
    expect(entered(await preStep(loaded, agent, []))).toEqual([])
    await compacted(loaded, agentFor(root, {}, "ses_other"))
    expect(entered(await preStep(loaded, agent, []))).toEqual([])
    await compacted(loaded, agent)
    await disposed(loaded, agent)
    expect(entered(await preStep(loaded, agent, []))).toEqual([])

    fs.mkdirSync(path.join(root, "svc", ".planning", "2026-09-02-child"), { recursive: true })
    fs.writeFileSync(path.join(root, "svc", ".planning", "2026-09-02-child", "task_plan.md"), "# CHILD\n")
    await compacted(loaded, agent)
    expect(entered(await preStep(loaded, agent, []))).toEqual([])
    expect(textOf(injected(await preStep(loaded, agent, [userPrompt()])))).toContain("Ambiguous plan")

    const empty = agentFor(fs.mkdtempSync(path.join(root, "empty-")), {}, "ses_empty")
    await compacted(loaded, empty)
    expect(entered(await preStep(loaded, empty, []))).toEqual([])
    expect(loaded.warn).not.toHaveBeenCalled()
  })
})

describe("agent/turn-stopping", () => {
  it("steers a gated agent with the gate reason, stalls without ledger progress, and honours the cap", async () => {
    gatedRoot()
    const loaded = load()
    const agent = agentFor(root)
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(1)
    const first = agent.steer.mock.calls[0][0] as UserMessage
    expect(first.source).toEqual({ kind: "plugin", plugin: name })
    expect(textOf(first)).toContain("phase 'Phase 2: B' is in_progress (1/2 complete, gate block 1/20)")
    expect(fs.readFileSync(path.join(root, ".stop_blocks"), "utf8")).toBe("1\n")

    // no ledger progress since the last block releases the stop
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(1)

    ledgerAdvance()
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(2)
    expect(textOf(agent.steer.mock.calls[1][0] as UserMessage)).toContain("gate block 2/20")

    fs.writeFileSync(path.join(root, ".stop_blocks"), "20\n")
    ledgerAdvance()
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(2)

    process.env.PWF_GATE_CAP = "3"
    fs.writeFileSync(path.join(root, ".stop_blocks"), "2\n")
    ledgerAdvance()
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(3)
    expect(textOf(agent.steer.mock.calls[2][0] as UserMessage)).toContain("gate block 3/3")
    ledgerAdvance()
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(3)

    gatedRoot(root, DONE)
    fs.writeFileSync(path.join(root, ".stop_blocks"), "0\n")
    await stop(loaded, agent)
    expect(agent.steer).toHaveBeenCalledTimes(3)
  })

  it("never holds subagent children, autonomous, legacy or disabled plans, and can be switched off", async () => {
    gatedRoot()
    const loaded = load()
    const child = agentFor(root, { origin: "subagent" })
    await stop(loaded, child)
    const nested = agentFor(root, { delegationDepth: 1 })
    await stop(loaded, nested)
    expect(child.steer).not.toHaveBeenCalled()
    expect(nested.steer).not.toHaveBeenCalled()

    const agent = agentFor(root)
    process.env.PLANNING_DISABLED = "1"
    await stop(loaded, agent)
    delete process.env.PLANNING_DISABLED
    fs.writeFileSync(path.join(root, ".mode"), "autonomous\n")
    await stop(loaded, agent)
    fs.unlinkSync(path.join(root, ".mode"))
    await stop(loaded, agent)
    expect(agent.steer).not.toHaveBeenCalled()

    fs.writeFileSync(path.join(root, ".mode"), "autonomous gate\n")
    const ungated = load({ gate: false })
    expect(ungated.listeners.has("agent/turn-stopping")).toBe(false)
    expect(ungated.listeners.has("agent/pre-step")).toBe(true)
  })

  it("logs a warning and lets the turn close when planning throws", async () => {
    gatedRoot()
    const loaded = load()
    const broken = { id: "ses_main", get session(): never { throw new Error("header exploded") }, inject: vi.fn(), steer: vi.fn() }
    await stop(loaded, broken as never)
    expect(broken.steer).not.toHaveBeenCalled()
    expect(loaded.warn).toHaveBeenCalledTimes(1)
    expect(String(loaded.warn.mock.calls[0][0])).toContain("agent/turn-stopping")
  })
})

describe("commands", () => {
  it("/pwf --gated creates a named plan, activates it and injects it; /pwf-status reports it", async () => {
    const loaded = load()
    const agent = agentFor(root)
    const result = await command(loaded, "pwf", agent, " My Task --gated")
    expect(result.kind).toBe("success")
    const text = result.kind === "success" ? result.text ?? "" : ""
    const id = /plan (\d{4}-\d{2}-\d{2}-my-task)/.exec(text)?.[1]
    expect(id).toBeDefined()
    expect(text).toContain("created task_plan.md, findings.md, progress.md")
    expect(text).toContain("mode gated")

    const planDir = path.join(root, ".planning", id!)
    for (const file of ["task_plan.md", "findings.md", "progress.md"]) expect(fs.existsSync(path.join(planDir, file))).toBe(true)
    expect(fs.readFileSync(path.join(planDir, ".mode"), "utf8")).toBe("autonomous gate\n")
    expect(fs.readFileSync(path.join(root, ".planning", ".active_plan"), "utf8")).toBe(`${id}\n`)
    expect(fs.readFileSync(path.join(planDir, ".attestation"), "utf8").trim()).toBe(sha(path.join(planDir, "task_plan.md")))

    expect(agent.inject).toHaveBeenCalledTimes(1)
    const message = agent.inject.mock.calls[0][0] as UserMessage
    expect(message.source).toEqual({ kind: "plugin", plugin: name })
    expect(textOf(message).startsWith(BANNER)).toBe(true)
    expect(textOf(message)).toContain(`[planning-with-files] plan: ${id}`)
    const batch = [message, userPrompt()]
    expect(entered(await preStep(loaded, agent, batch))).toEqual(batch)

    const status = await command(loaded, "pwf-status", agent)
    expect(status.kind).toBe("success")
    const report = status.kind === "success" ? status.text ?? "" : ""
    expect(report).toContain(`plan ${id} (autonomous gate, attested)`)
    expect(report).toContain("current phase: Phase 1")
    expect(report).toContain("phases: 0 complete, 1 in_progress, 4 pending of 5")
  })

  it("keeps existing files, reports errors instead of throwing, and names the missing plan", async () => {
    const loaded = load()
    const agent = agentFor(root)
    const missing = await command(loaded, "pwf-status", agent)
    expect(missing.kind).toBe("success")
    expect(missing.kind === "success" ? missing.text : "").toContain("no plan in")

    fs.writeFileSync(path.join(root, "task_plan.md"), "# Mine\n")
    const kept = await command(loaded, "pwf", agent, "")
    expect(kept.kind).toBe("success")
    expect(kept.kind === "success" ? kept.text : "").toContain("created findings.md, progress.md")
    expect(fs.readFileSync(path.join(root, "task_plan.md"), "utf8")).toBe("# Mine\n")
    const again = await command(loaded, "pwf", agent, "")
    expect(again.kind === "success" ? again.text : "").toContain("kept the existing planning files")

    const unknown = await command(loaded, "pwf", agent, "--bogus Night run")
    expect(unknown.kind).toBe("error")
    expect(unknown.kind === "error" ? unknown.text : "").toContain("unknown option --bogus")
    expect(fs.existsSync(path.join(root, ".planning"))).toBe(false)

    const noWorkspace = await command(loaded, "pwf", agentFor(undefined), "Night run")
    expect(noWorkspace.kind).toBe("error")
    expect(noWorkspace.kind === "error" ? noWorkspace.text : "").toContain("no working directory")

    process.env.PLANNING_DISABLED = "1"
    const disabled = await command(loaded, "pwf-status", agent)
    expect(disabled.kind).toBe("error")
    expect(disabled.kind === "error" ? disabled.text : "").toContain("PLANNING_DISABLED")
  })
})

describe("tools", () => {
  it("pwf_init, pwf_status and pwf_check operate on the calling agent's workspace", async () => {
    const loaded = load()
    const agent = agentFor(root)
    const init = await tool(loaded, "pwf_init", { name: "Night run", mode: "gated" }, agent)
    expect(init.ok).toBe(true)
    expect(init.plan_id).toMatch(/-night-run$/)
    expect(init.attestation).toMatch(/^[0-9a-f]{64}$/)
    const status = await tool(loaded, "pwf_status", {}, agent)
    expect(status.plan_id).toBe(init.plan_id)
    expect(status.mode).toBe("autonomous gate")
    const check = await tool(loaded, "pwf_check", {}, agent)
    expect(check.plugin).toBe(VERSION)
    expect(check.complete).toBe(false)
    expect(check.message).toContain("Plan incomplete")
    expect(loaded.tools.get("pwf_check")!.output.render({}, "text")).toEqual([{ type: "text", text: "text" }])
  })

  it("follows the pin and refuses when planning is disabled, the pin is broken, or the call has no agent", async () => {
    const pinned = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pwf-dsh-pin-")))
    try {
      const loaded = load()
      const agent = agentFor(root)
      process.env.PWF_PLAN_ROOT = pinned
      const init = await tool(loaded, "pwf_init", {}, agent)
      expect(init.ok).toBe(true)
      expect(fs.existsSync(path.join(pinned, "task_plan.md"))).toBe(true)
      expect(fs.existsSync(path.join(root, "task_plan.md"))).toBe(false)
      const status = await tool(loaded, "pwf_status", {}, agent)
      expect(status.project_dir).toBe(pinned)
      process.env.PWF_PLAN_ROOT = path.join(root, "missing")
      expect((await tool(loaded, "pwf_status", {}, agent)).ok).toBe(false)
      delete process.env.PWF_PLAN_ROOT
      const orphan = await tool(loaded, "pwf_check", {}, undefined)
      expect(orphan.ok).toBe(false)
      expect(String(orphan.error)).toContain("working directory")
      process.env.PLANNING_DISABLED = "1"
      expect((await tool(loaded, "pwf_check", {}, agent)).ok).toBe(false)
    } finally {
      fs.rmSync(pinned, { recursive: true, force: true })
    }
  })
})
