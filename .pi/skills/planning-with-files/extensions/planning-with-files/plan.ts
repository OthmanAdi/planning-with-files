import { createHash } from "node:crypto";
import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync, statSync } from "node:fs";
import { basename, dirname, join, sep } from "node:path";

export type PlanScope = "scoped" | "root" | "none";

export interface PlanPaths {
	cwd: string;
	scope: PlanScope;
	selectionError?: "session-plan-ambiguous";
	planPath?: string;
	progressPath?: string;
	findingsPath?: string;
	planDir?: string;
	planId?: string;
	attestationCandidates: string[];
}

export const SESSION_PLAN_AMBIGUOUS_NOTICE =
	"[planning-with-files] Multiple plans are available while session isolation is armed. Set PLAN_ID=<slug> for this session; nothing injected.";

export interface PlanStatus extends PlanPaths {
	exists: boolean;
	// Digest of the same raw read used for the text and phase counts below.
	// Undefined means that the selected plan could not be read.
	planSha256?: string;
	// Keep the selected attestation binding even if the file later disappears.
	attestationPath?: string;
	closed: boolean;
	totalPhases: number;
	completePhases: number;
	invalidPhaseStructure?: boolean;
	inProgressPhases: number;
	pendingPhases: number;
	firstLines50: string;
	headLines30: string;
	progressTail20: string;
}

function safeRead(path: string): string {
	try {
		return readFileSync(path, "utf-8");
	} catch {
		return "";
	}
}

function selectAttestationPath(candidates: string[]): string | undefined {
	for (const candidate of candidates) {
		try {
			lstatSync(candidate);
			return candidate;
		} catch (error) {
			// Only absence allows a fallback. Permission or other lookup errors
			// retain this candidate so verification fails closed on its read.
			if ((error as NodeJS.ErrnoException).code !== "ENOENT") return candidate;
		}
	}
	return undefined;
}

// Wall-clock times inside the injected progress tail move on every fire, so the
// bytes after them stop matching a cached prefix. The shell hooks have flattened
// them since v2.40; this is the same substitution, kept equivalent to the sed -E
// expression in scripts/inject-plan.sh so every route emits identical bytes for
// identical input. Matters most in parity mode, which re-sends the tail each turn.
export function normalizeWallClock(text: string): string {
	return text
		.replace(/T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z/g, "T00:00:00Z")
		.replace(/T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([+-][0-9]{2}:[0-9]{2})/g, "T00:00:00$2");
}

function resolveNewestPlanDir(planRoot: string): string | undefined {
	if (!existsSync(planRoot)) return undefined;

	const dirs = readdirSync(planRoot, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && !entry.name.startsWith(".") && SLUG_RE.test(entry.name))
		.map((entry) => join(planRoot, entry.name))
		.filter((dir) => existsSync(join(dir, "task_plan.md")))
		.map((dir) => {
			let mtime = 0;
			try {
				// Rank by task_plan.md mtime, not the directory: editing a plan's contents does not bump the dir mtime, which let a completed plan lose to a stale sibling (#203).
				mtime = statSync(join(dir, "task_plan.md")).mtimeMs;
			} catch {
				mtime = 0;
			}
			return { dir, mtime };
		})
		.sort((a, b) => b.mtime - a.mtime);

	return dirs[0]?.dir;
}

// Same shape as the sh resolver's slug_is_valid: first char [A-Za-z0-9_],
// rest [A-Za-z0-9._-]. Blocks traversal tokens (no separators), hidden names,
// and whitespace before any path is built; keeps Pi resolution in lockstep
// with resolve-plan-dir.sh on the same trees.
const SLUG_RE = /^[A-Za-z0-9_][A-Za-z0-9._-]*$/;

type SessionIsolationState = "absent" | "armed" | "invalid";

function sessionIsolationState(cwd: string): SessionIsolationState {
	try {
		const sessions = lstatSync(join(cwd, ".planning", "sessions"));
		return sessions.isDirectory() && !sessions.isSymbolicLink() ? "armed" : "invalid";
	} catch (error) {
		return (error as NodeJS.ErrnoException).code === "ENOENT" ? "absent" : "invalid";
	}
}

function isSessionIsolationArmed(cwd: string): boolean {
	return sessionIsolationState(cwd) === "armed";
}

function hasMultipleLivePlans(cwd: string, planRoot: string): boolean {
	let count = existsSync(join(cwd, "task_plan.md")) ? 1 : 0;

	try {
		for (const entry of readdirSync(planRoot, { withFileTypes: true })) {
			if (!entry.isDirectory() || entry.name.startsWith(".") || !SLUG_RE.test(entry.name)) continue;
			const candidate = join(planRoot, entry.name);
			if (!existsSync(join(candidate, "task_plan.md")) || !isWithinRoot(cwd, candidate)) continue;
			count += 1;
			if (count > 1) return true;
		}
	} catch {
		return true;
	}

	return false;
}

// Containment (security A1.3 parity with the sh resolver): a scoped candidate
// must canonicalize to a path under the anchor, or a symlinked/junctioned
// slug dir could hand the hooks an arbitrary file outside the project. Fails
// closed on canonicalization failure, matching resolve-plan-dir.sh.
function isWithinRoot(root: string, candidate: string): boolean {
	let rootReal: string;
	let candReal: string;
	try {
		rootReal = realpathSync(root);
		candReal = realpathSync(candidate);
	} catch {
		return false;
	}
	if (candReal === rootReal) return true;
	return candReal.startsWith(rootReal.endsWith(sep) ? rootReal : rootReal + sep);
}

const ANCHOR_WALK_CAP = 10;

// The Pi session cwd follows the live shell, so an agent that cd's into a
// subdirectory used to lose the project's plan entirely: resolution found
// nothing, recitation went dark, and the "No task_plan.md found" warning
// fired on every write/edit (#208). Anchor resolution walks parents until a
// directory carries planning state (.planning/ or task_plan.md). A .git
// boundary without planning state, or the depth cap, stops the walk so a
// plan outside the repository can never leak into the session. Exported so
// runtime consumers that take a directory (attachment gate, mode config,
// script cwds) resolve from the same anchor as the plan itself.
export function resolveAnchor(cwd: string): string {
	let dir = cwd;
	for (let depth = 0; depth < ANCHOR_WALK_CAP; depth++) {
		if (existsSync(join(dir, ".planning")) || existsSync(join(dir, "task_plan.md"))) {
			return dir;
		}
		const parent = dirname(dir);
		if (existsSync(join(dir, ".git")) || parent === dir) {
			return cwd;
		}
		dir = parent;
	}
	return cwd;
}

export function resolvePlanPaths(sessionCwd: string): PlanPaths {
	// All plan paths are built on the anchor (the nearest ancestor with
	// planning state), not the raw shell cwd. The returned cwd field carries
	// the anchor; runtime call sites that take a directory route through
	// resolveAnchor/anchorCwd so they land on the same plan.
	const cwd = resolveAnchor(sessionCwd);
	const planRoot = join(cwd, ".planning");

	const makeScoped = (planDir: string): PlanPaths => ({
		cwd,
		scope: "scoped",
		planDir,
		planId: basename(planDir),
		planPath: join(planDir, "task_plan.md"),
		progressPath: join(planDir, "progress.md"),
		findingsPath: join(planDir, "findings.md"),
		attestationCandidates: [join(planDir, ".attestation"), join(cwd, ".plan-attestation")],
	});

	const makeRoot = (): PlanPaths => ({
		cwd,
		scope: "root",
		planPath: join(cwd, "task_plan.md"),
		progressPath: join(cwd, "progress.md"),
		findingsPath: join(cwd, "findings.md"),
		attestationCandidates: [join(cwd, ".plan-attestation")],
	});

	const makeNone = (selectionError?: PlanPaths["selectionError"]): PlanPaths => ({
		cwd,
		scope: "none",
		selectionError,
		attestationCandidates: [join(cwd, ".plan-attestation")],
	});

	// A set PLAN_ID is a BINDING, not a hint (issue #237).
	//
	// A slug that resolves to a contained scoped plan wins. One that does NOT
	// resolve ends resolution right here. Falling through to .active_plan, the
	// newest slug and the root plan turned a one-character typo into a silent
	// switch: the operator asked for plan A, the pointer or newest-by-mtime
	// answered with plan B, and B was what got attested and injected at rc=0.
	// Every rejection route ends the same way, whether the selector failed
	// SLUG_RE (traversal shapes included), named no plan directory, or failed
	// containment. The session gets the "none" scope and takes its own
	// fail-closed path rather than a plan nobody selected.
	//
	// An EMPTY or unset PLAN_ID still means "no selector": resolution continues
	// below exactly as before, which is what the legacy root path depends on.
	const planId = process.env.PLAN_ID?.trim();
	if (planId) {
		if (SLUG_RE.test(planId)) {
			const candidate = join(planRoot, planId);
			if (existsSync(join(candidate, "task_plan.md")) && isWithinRoot(cwd, candidate)) {
				return makeScoped(candidate);
			}
		}
		return makeNone();
	}

	// An attachment admits a session to the project, but it does not choose one
	// of several plans. With isolation armed, the shared pointer and newest-plan
	// fallback would otherwise cross session boundaries. Match the canonical hook:
	// an explicit PLAN_ID remains the only task selector in this state.
	if (isSessionIsolationArmed(cwd) && hasMultipleLivePlans(cwd, planRoot)) {
		return makeNone("session-plan-ambiguous");
	}

	const activePlanFile = join(planRoot, ".active_plan");
	if (existsSync(activePlanFile)) {
		const activePlanId = safeRead(activePlanFile).trim();
		if (activePlanId && SLUG_RE.test(activePlanId)) {
			const candidate = join(planRoot, activePlanId);
			if (existsSync(join(candidate, "task_plan.md")) && isWithinRoot(cwd, candidate)) {
				return makeScoped(candidate);
			}
		}
	}

	const newest = resolveNewestPlanDir(planRoot);
	// Containment is checked on the winner only; a rejected winner falls
	// through to root/none (the safe direction) rather than promoting the
	// next-newest sibling.
	if (newest && isWithinRoot(cwd, newest)) {
		return makeScoped(newest);
	}

	const rootPlan = makeRoot();
	if (rootPlan.planPath && existsSync(rootPlan.planPath)) {
		return rootPlan;
	}

	return makeNone();
}

function planPhases(text: string) {
  const phases: { heading: string; statuses: string[] }[] = []
  let phase: (typeof phases)[number] | null = null
  let fence = ""
  let fenceLength = 0
  let malformedHeading = false
  for (const line of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    if (fence) {
      if (new RegExp(`^ {0,3}${fence}{${fenceLength},}[ \\t]*$`).test(line)) fence = ""
      continue
    }
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})/)
    if (marker && (marker[1][0] !== "`" || !line.slice(marker[0].length).includes("`"))) {
      fence = marker[1][0]; fenceLength = marker[1].length; continue
    }
    if (/^ {0,3}>/.test(line)) continue
    if (/^ {0,3}### Phase(?:[ \t]|$)/i.test(line)) {
      phase = { heading: line.trimStart().slice(4), statuses: [] }
      phases.push(phase)
    } else if (/^ {0,3}### Phase(?:[0-9:]|-[0-9])/i.test(line)) {
      malformedHeading = true
      phase = null
    } else if (/^ {0,3}#{1,3}(?:[ \t]|$)/.test(line)) phase = null
    if (phase) {
      for (const match of line.matchAll(/\*\*Status:\*\*[ \t]+(pending|in_progress|complete)(?![A-Za-z0-9_])|\[(pending|in_progress|complete)\]/gi)) {
        phase.statuses.push((match[1] || match[2]).toLowerCase())
      }
    }
  }
  return { phases, invalidStructure: fence !== "" || malformedHeading }
}

export function readPlanStatus(cwd: string): PlanStatus {
	const paths = resolvePlanPaths(cwd);
	if (!paths.planPath) {
		return {
			...paths,
			exists: false,
			closed: false,
			totalPhases: 0,
			completePhases: 0,
			inProgressPhases: 0,
			pendingPhases: 0,
			firstLines50: "",
			headLines30: "",
			progressTail20: "",
		};
	}

	const attestationPath = selectAttestationPath(paths.attestationCandidates);
	let planBytes: Buffer | undefined;
	try {
		planBytes = readFileSync(paths.planPath);
	} catch {
		// Keep the selected path and attestation, but no digest. A later read
		// must not approve an empty snapshot after a transient read failure.
	}
	const planSha256 = planBytes === undefined ? undefined : createHash("sha256").update(planBytes).digest("hex");
	const planContent = planBytes?.toString("utf-8") ?? "";
	const closed = /<!--\s*pwf:\s*closed\s*-->/i.test(planContent);
	const lines = planContent.split("\n");

	const { phases, invalidStructure } = planPhases(planContent);
	const total = phases.length;
	const count = (state: string) => phases.filter((p) => p.statuses.length === 1 && p.statuses[0] === state).length;
	const complete = count("complete");
	const inProgress = phases.filter((p) => p.statuses.includes("in_progress")).length;
	const pending = count("pending");

	let progressTail20 = "";
	if (paths.progressPath && existsSync(paths.progressPath)) {
		const progressLines = safeRead(paths.progressPath).split("\n");
		progressTail20 = normalizeWallClock(progressLines.slice(-20).join("\n"));
	}

	return {
		...paths,
		exists: true,
		planSha256,
		attestationPath,
		closed,
		totalPhases: total,
		completePhases: complete,
		invalidPhaseStructure: invalidStructure,
		inProgressPhases: inProgress,
		pendingPhases: pending,
		firstLines50: lines.slice(0, 50).join("\n"),
		headLines30: lines.slice(0, 30).join("\n"),
		progressTail20,
	};
}

export function isAllPhasesComplete(status: PlanStatus): boolean {
	return status.exists && !status.invalidPhaseStructure && status.totalPhases > 0 && status.completePhases >= status.totalPhases;
}

export function isPlanIncomplete(status: PlanStatus): boolean {
	return status.exists && status.totalPhases > 0 && status.completePhases < status.totalPhases;
}

export function isSessionAttached(cwd: string, sessionId: string | undefined): boolean {
	const sessionsDir = join(cwd, ".planning", "sessions");
	if (sessionIsolationState(cwd) === "absent") return true;
	if (!isSessionIsolationArmed(cwd)) return false;
	if (!sessionId) return false;
	return existsSync(join(sessionsDir, `${sessionId}.attached`));
}
