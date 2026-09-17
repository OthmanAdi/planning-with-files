/**
 * DeepSeek Harness (dsh) plugin entry for planning-with-files.
 *
 * A Cordis plugin: `name`, `Config`, `apply(ctx, config)`. The helpers live
 * in ./core.js, a byte-identical copy of the OpenCode core locked by
 * tests/test_dsh_plugin_core_parity.py. Listeners (all fail open: a planning
 * error is logged and the turn proceeds without planning context):
 *
 * - agent/pre-step: append the framed active plan (or the ambiguity notice)
 *   to the step that carries the user's prompt, never to a step that only
 *   carries tool context, steering or this plugin's own injected messages
 * - tools/post-execute: attach the progress reminder to the result of a
 *   write-like tool while a plan exists
 * - session/event with a successful compaction/end: mark the session, so the
 *   next step of that agent (a continuation of the compacted turn, or the next
 *   prompt) carries the compaction note and the plan and resumes at the
 *   current phase. The published dsh (0.1.5-rc.2) declares `compact` as an
 *   agent/session-start source but every dispatch site announces `startup` or
 *   `resume` only, and the 0.1.6 alpha line does the same on agent/created;
 *   the durable compaction/end event is what both lines actually write.
 * - agent/turn-stopping: the completion gate in gated mode, steering the
 *   agent into another step with the gate reason (Tier 2: follow-up inject)
 * - commands /pwf and /pwf-status, tools pwf_init, pwf_status, pwf_check
 *
 * The `commands` and `tools` services are consumed through ctx.inject so the
 * lifecycle listeners load in every profile, including one without them.
 */
import type { Context } from "@deepseek-ai/cordis"
import Schema from "@deepseek-ai/schemastery"
import type { Agent } from "@deepseek-ai/dsh-agent"
import type {} from "@deepseek-ai/dsh-commands"
import type {} from "@deepseek-ai/dsh-compaction"
import { createUserMessage } from "@deepseek-ai/dsh-llm"
import type { ContentBlock, MessageSource } from "@deepseek-ai/dsh-llm"
import type { UserMessage } from "@deepseek-ai/dsh-session"
import { defineTool } from "@deepseek-ai/dsh-tools"
import type { ToolExecution } from "@deepseek-ai/dsh-tools"
import {
  ambiguityNotice,
  buildContext,
  checkComplete,
  compactionNote,
  effectiveProjectRoot,
  evaluateGate,
  initPlan,
  planRootIsPinned,
  resolvePlan,
  summarizeStatus,
  MULTIPLE_PLANS_NOTICE,
  REMINDER,
  VERSION,
  WRITE_LIKE_TOOLS,
  type StatusResult,
} from "./core.js"

export const name = "planning-with-files"
/** Empty on purpose: the lifecycle listeners must never wait on an optional service. */
export const inject = [] as const

export interface Config {
  /** Register nothing when false; the row can stay in the profile. */
  enabled: boolean
  /** Register the turn-stopping completion gate. */
  gate: boolean
}

export const Config: Schema<Config> = Schema.object({
  enabled: Schema.boolean().default(true),
  gate: Schema.boolean().default(true),
})

type Located = { root: string | null; planDir: string | null; conflicts: string[]; multiple?: true }
type RootOrError = string | { ok: false; error: string }
type PwfInput = { ok: true; opts: { name?: string; mode?: string; template?: string } } | { ok: false; error: string }

const NOTHING: Located = { root: null, planDir: null, conflicts: [] }
/** The `{kind:'plugin'}` source stamped on every message this plugin injects. */
const PLUGIN_SOURCE: MessageSource = { kind: "plugin", plugin: name }
/** Every planning tool returns one JSON document as text, the OpenCode tool contract. */
const JSON_TEXT = {
  schema: { type: "string" },
  render: (_args: unknown, value: string): ContentBlock[] => [{ type: "text", text: value }],
} as const

/** The session workspace. A session without one selects no plan: process.cwd() would be another project's plan. */
function workspaceOf(agent: Agent | undefined): string | null {
  return agent?.session.header.cwd ?? null
}

/** Subagent children finish their delegated task; the gate holds only the delegating agent, as on OpenCode. */
function isSubagent(agent: Agent): boolean {
  const header = agent.session.header
  return header.origin === "subagent" || (header.delegationDepth ?? 0) > 0
}

function message(texts: string[]): UserMessage {
  const content: ContentBlock[] = texts.map((text) => ({ type: "text", text }))
  return createUserMessage({ content, source: PLUGIN_SOURCE })
}

function isOurs(candidate: UserMessage): boolean {
  return candidate.source.kind === "plugin" && candidate.source.plugin === name
}

/**
 * Whether a step batch carries the user's prompt. The loop claims pending
 * next-step items (tool contexts, steering, our own injections) together
 * with the queued turn message, so a batch without a user-sourced message is
 * a continuation step and gets the plan only right after a compaction; a
 * batch that already holds one of our messages (the plan queued by /pwf, a
 * pending reminder) is served either way.
 */
function opensTurn(messages: UserMessage[]): boolean {
  return messages.some((candidate) => candidate.source.kind === "user")
}

/** DSH's mutating file tools: write, edit, and str_replace_editor unless it only views. */
function isWriteLike(exec: ToolExecution): boolean {
  if (WRITE_LIKE_TOOLS.has(exec.name)) return true
  if (exec.name !== "str_replace_editor") return false
  const args = exec.arguments as { command?: unknown } | null | undefined
  return args?.command !== "view"
}

/** `/pwf [--autonomous|--gated] [--template analytics] [plan name]`, the OpenCode command grammar. */
function parsePwfInput(rawInput: string): PwfInput {
  const words: string[] = []
  let mode: string | undefined
  let template: string | undefined
  const tokens = rawInput.trim().split(/\s+/).filter(Boolean)
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]
    if (token === "--gated" || token === "--autonomous") mode = token.slice(2)
    else if (token === "--template" && index + 1 < tokens.length) {
      index += 1
      template = tokens[index]
    }
    else if (token.startsWith("--template=")) template = token.slice("--template=".length)
    else if (token.startsWith("--")) return { ok: false, error: `planning-with-files: unknown option ${token}. Usage: /pwf [--autonomous|--gated] [--template analytics] [plan name]` }
    else words.push(token)
  }
  return { ok: true, opts: { name: words.join(" ") || undefined, mode, template } }
}

function statusText(status: StatusResult): string {
  const nested = status.conflicts?.length ? `\nnested plans below this root: ${status.conflicts.join(", ")}` : ""
  if (!status.exists || !status.counts) return `planning-with-files: no plan in ${status.project_dir}. Run /pwf [plan name] to create one.${nested}`
  const counts = status.counts
  return [
    `planning-with-files: plan ${status.plan_id} (${status.mode}${status.attested ? ", attested" : ""}) at ${status.plan_dir}`,
    `current phase: ${status.current_phase}`,
    `phases: ${counts.complete} complete, ${counts.in_progress} in_progress, ${counts.pending} pending of ${counts.total}`,
  ].join("\n") + nested
}

export function apply(ctx: Context, config: Config): void {
  if (!config.enabled) return
  const env = process.env

  function warn(point: string, error: unknown): void {
    ctx.logger.warn(`planning-with-files: ${point} skipped after an error, the turn proceeds without planning context: ${String(error)}`)
  }

  function locate(project: string | null): Located {
    if (project === null || env.PLANNING_DISABLED === "1") return NOTHING
    const root = effectiveProjectRoot(project, env)
    if (!root) return NOTHING
    const resolved = resolvePlan(root, { explicit: planRootIsPinned(env) }, env)
    return { root, planDir: resolved.planDir, conflicts: resolved.conflicts, ...(resolved.multiple ? { multiple: true } : {}) }
  }

  /** Tools and commands resolve the same root as the listeners; a broken pin or the opt-out is an explicit error, never a silent fallback. */
  function toolRoot(project: string | null): RootOrError {
    if (env.PLANNING_DISABLED === "1") return { ok: false, error: "PLANNING_DISABLED=1 is set for this session; planning-with-files is switched off." }
    if (project === null) return { ok: false, error: "This session has no working directory; planning-with-files cannot select a plan." }
    const root = effectiveProjectRoot(project, env)
    if (!root) return { ok: false, error: `PWF_PLAN_ROOT=${env.PWF_PLAN_ROOT} does not resolve to an existing directory.` }
    return root
  }

  /**
   * Sessions compacted since their last admitted step. Automatic pressure
   * compaction runs inside the loop's own agent/pre-step listener ahead of
   * this one, so the step being admitted is the first request after the
   * summary; a manual /compact runs on an idle agent and the next prompt is.
   * Marking the session instead of queueing an inbox item keeps the plan
   * fresh at admission time and never leaves a stale copy for a later prompt.
   */
  const compacted = new Set<string>()

  ctx.on("session/event", (session, event) => {
    if (event.type !== "compaction/end" || event.data.error !== undefined) return
    compacted.add(session.id)
  })

  ctx.on("session/disposed", (session) => {
    compacted.delete(session.id)
  })

  ctx.on("agent/pre-step", async ({ agent, messages }, next) => {
    const downstream = await next()
    try {
      if (downstream.kind !== "enter") return downstream
      const afterCompaction = compacted.delete(agent.session.id)
      if (messages.some(isOurs)) return downstream
      if (!afterCompaction && !opensTurn(messages)) return downstream
      const located = locate(workspaceOf(agent))
      let texts: string[] | null = null
      if (located.root && located.planDir) {
        const plan = buildContext(located.root, located.planDir)
        texts = afterCompaction ? [compactionNote(located.root, located.planDir), plan] : [plan]
      } else if (opensTurn(messages)) {
        // the notices answer a prompt; a continuation step after compaction gets them with the next prompt
        if (located.multiple) texts = [MULTIPLE_PLANS_NOTICE]
        else if (located.conflicts.length) texts = [ambiguityNotice(located.conflicts)]
      }
      if (!texts) return downstream
      return { ...downstream, messages: [...downstream.messages, message(texts)] }
    } catch (error) {
      warn("agent/pre-step", error)
      return downstream
    }
  })

  ctx.on("tools/post-execute", async (exec, result, next) => {
    const downstream = await next()
    try {
      if (result.isError || !exec.agent || !isWriteLike(exec)) return downstream
      if (!locate(workspaceOf(exec.agent)).planDir) return downstream
      return { ...downstream, additionalContexts: [...(downstream.additionalContexts ?? []), message([REMINDER])] }
    } catch (error) {
      warn("tools/post-execute", error)
      return downstream
    }
  })

  if (config.gate) {
    ctx.on("agent/turn-stopping", ({ agent }) => {
      try {
        if (isSubagent(agent)) return
        const located = locate(workspaceOf(agent))
        if (!located.root || !located.planDir) return
        const reason = evaluateGate(located.root, located.planDir, env)
        if (reason) agent.steer(message([reason]))
      } catch (error) {
        warn("agent/turn-stopping", error)
      }
    })
  }

  ctx.inject(["commands"], (scoped) => {
    scoped.commands.register({
      name: "pwf",
      description:
        "planning-with-files: create task_plan.md, findings.md and progress.md (a name creates .planning/<date>-<slug>/; --autonomous or --gated attests the plan) and inject the plan.",
      input: { hint: "[--autonomous|--gated] [--template analytics] [plan name]" },
      handler: ({ agent, rawInput }) => {
        try {
          const root = toolRoot(workspaceOf(agent))
          if (typeof root !== "string") return { kind: "error", text: root.error }
          const input = parsePwfInput(rawInput)
          if (!input.ok) return { kind: "error", text: input.error }
          const result = initPlan(root, input.opts, env)
          if (!result.ok || !result.plan_dir) return { kind: "error", text: `planning-with-files: ${result.error ?? "init failed"}` }
          agent.inject(message([buildContext(root, result.plan_dir)]))
          const files = result.created?.length ? `created ${result.created.join(", ")}` : "kept the existing planning files"
          return {
            kind: "success",
            text: `planning-with-files: ${files} in ${result.plan_dir} (plan ${result.plan_id}, mode ${result.mode}). The plan is queued for the next model request.`,
          }
        } catch (error) {
          return { kind: "error", text: `planning-with-files: ${String(error)}` }
        }
      },
    })
    scoped.commands.register({
      name: "pwf-status",
      description: "planning-with-files: show the active plan (id, mode, attestation, current phase, phase counts).",
      handler: ({ agent }) => {
        try {
          const root = toolRoot(workspaceOf(agent))
          if (typeof root !== "string") return { kind: "error", text: root.error }
          return { kind: "success", text: statusText(summarizeStatus(root, env)) }
        } catch (error) {
          return { kind: "error", text: `planning-with-files: ${String(error)}` }
        }
      },
    })
  })

  ctx.inject(["tools"], (scoped) => {
    scoped.tools.register(defineTool({
      name: "pwf_init",
      description:
        "planning-with-files: create task_plan.md, findings.md and progress.md. A name creates an isolated .planning/YYYY-MM-DD-<slug>/ plan and makes it active; mode autonomous or gated writes the v3 markers and attests the plan.",
      parameters: {
        name: { type: "string", description: "Optional plan name (creates .planning/<date>-<slug>/)" },
        mode: { type: "string", description: "Optional v3 mode: autonomous or gated" },
        template: { type: "string", description: "default or analytics" },
      },
      output: JSON_TEXT,
      async execute(args, exec) {
        const root = toolRoot(workspaceOf(exec.agent))
        if (typeof root !== "string") return JSON.stringify(root)
        return JSON.stringify(initPlan(root, args, env))
      },
    }))
    scoped.tools.register(defineTool({
      name: "pwf_status",
      description: "planning-with-files: summarize the active plan (id, mode, attestation, current phase, phase counts).",
      parameters: {},
      output: JSON_TEXT,
      async execute(_args, exec) {
        const root = toolRoot(workspaceOf(exec.agent))
        if (typeof root !== "string") return JSON.stringify(root)
        return JSON.stringify(summarizeStatus(root, env))
      },
    }))
    scoped.tools.register(defineTool({
      name: "pwf_check",
      description: "planning-with-files: report whether every phase of the active plan is complete.",
      parameters: {},
      output: JSON_TEXT,
      async execute(_args, exec) {
        const root = toolRoot(workspaceOf(exec.agent))
        if (typeof root !== "string") return JSON.stringify(root)
        return JSON.stringify({ plugin: VERSION, ...checkComplete(root, env) })
      },
    }))
  })
}
