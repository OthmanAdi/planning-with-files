import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";

export type PlanScope = "scoped" | "root" | "none";

export interface PlanPaths {
	cwd: string;
	scope: PlanScope;
	planPath?: string;
	progressPath?: string;
	findingsPath?: string;
	planDir?: string;
	planId?: string;
	attestationCandidates: string[];
}

export interface PlanStatus extends PlanPaths {
	exists: boolean;
	totalPhases: number;
	completePhases: number;
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

function resolveNewestPlanDir(planRoot: string): string | undefined {
	if (!existsSync(planRoot)) return undefined;

	const dirs = readdirSync(planRoot, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
		.map((entry) => join(planRoot, entry.name))
		.filter((dir) => existsSync(join(dir, "task_plan.md")))
		.map((dir) => {
			let mtime = 0;
			try {
				mtime = statSync(dir).mtimeMs;
			} catch {
				mtime = 0;
			}
			return { dir, mtime };
		})
		.sort((a, b) => b.mtime - a.mtime);

	return dirs[0]?.dir;
}

export function resolvePlanPaths(cwd: string): PlanPaths {
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

	const planId = process.env.PLAN_ID?.trim();
	if (planId) {
		const candidate = join(planRoot, planId);
		if (existsSync(join(candidate, "task_plan.md"))) {
			return makeScoped(candidate);
		}
	}

	const activePlanFile = join(planRoot, ".active_plan");
	if (existsSync(activePlanFile)) {
		const activePlanId = safeRead(activePlanFile).trim();
		if (activePlanId) {
			const candidate = join(planRoot, activePlanId);
			if (existsSync(join(candidate, "task_plan.md"))) {
				return makeScoped(candidate);
			}
		}
	}

	const newest = resolveNewestPlanDir(planRoot);
	if (newest) {
		return makeScoped(newest);
	}

	const rootPlan = makeRoot();
	if (rootPlan.planPath && existsSync(rootPlan.planPath)) {
		return rootPlan;
	}

	return {
		cwd,
		scope: "none",
		attestationCandidates: [join(cwd, ".plan-attestation")],
	};
}

export function readPlanStatus(cwd: string): PlanStatus {
	const paths = resolvePlanPaths(cwd);
	if (!paths.planPath || !existsSync(paths.planPath)) {
		return {
			...paths,
			exists: false,
			totalPhases: 0,
			completePhases: 0,
			inProgressPhases: 0,
			pendingPhases: 0,
			firstLines50: "",
			headLines30: "",
			progressTail20: "",
		};
	}

	const planContent = safeRead(paths.planPath);
	const lines = planContent.split("\n");

	const phaseRegex = /^###\s+Phase\b/i;
	const statusComplete = /\*\*Status:\*\*\s*complete\b/i;
	const statusInProgress = /\*\*Status:\*\*\s*in_progress\b/i;
	const statusPending = /\*\*Status:\*\*\s*pending\b/i;

	let total = 0;
	let complete = 0;
	let inProgress = 0;
	let pending = 0;

	for (const line of lines) {
		if (phaseRegex.test(line)) total += 1;
		if (statusComplete.test(line)) complete += 1;
		else if (statusInProgress.test(line)) inProgress += 1;
		else if (statusPending.test(line)) pending += 1;
	}

	if (complete + inProgress + pending === 0) {
		complete = (planContent.match(/\[complete\]/gi) || []).length;
		inProgress = (planContent.match(/\[in_progress\]/gi) || []).length;
		pending = (planContent.match(/\[pending\]/gi) || []).length;
	}

	let progressTail20 = "";
	if (paths.progressPath && existsSync(paths.progressPath)) {
		const progressLines = safeRead(paths.progressPath).split("\n");
		progressTail20 = progressLines.slice(-20).join("\n");
	}

	return {
		...paths,
		exists: true,
		totalPhases: total,
		completePhases: complete,
		inProgressPhases: inProgress,
		pendingPhases: pending,
		firstLines50: lines.slice(0, 50).join("\n"),
		headLines30: lines.slice(0, 30).join("\n"),
		progressTail20,
	};
}

export function isAllPhasesComplete(status: PlanStatus): boolean {
	return status.exists && status.totalPhases > 0 && status.completePhases >= status.totalPhases;
}

export function isPlanIncomplete(status: PlanStatus): boolean {
	return status.exists && status.totalPhases > 0 && status.completePhases < status.totalPhases;
}

export function isSessionAttached(cwd: string, sessionId: string | undefined): boolean {
	const sessionsDir = join(cwd, ".planning", "sessions");
	if (!existsSync(sessionsDir)) return true;
	if (!sessionId) return false;
	return existsSync(join(sessionsDir, `${sessionId}.attached`));
}
