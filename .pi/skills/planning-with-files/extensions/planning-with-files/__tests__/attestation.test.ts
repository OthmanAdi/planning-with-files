import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { checkPlanAttestation } from "../attestation.ts";
import { readPlanStatus } from "../plan.ts";

const tempRoots: string[] = [];

function makeWorkspace(): string {
	const cwd = mkdtempSync(join(tmpdir(), "pwf-pi-attestation-"));
	tempRoots.push(cwd);
	return cwd;
}

function sha256(content: string): string {
	return createHash("sha256").update(content).digest("hex");
}

function writePlan(cwd: string, content: string): void {
	const planDir = join(cwd, ".planning", "demo");
	mkdirSync(planDir, { recursive: true });
	writeFileSync(join(planDir, "task_plan.md"), content);
}

afterEach(() => {
	while (tempRoots.length > 0) {
		const root = tempRoots.pop();
		if (root) rmSync(root, { recursive: true, force: true });
	}
});

describe("Pi extension plan attestation", () => {
	it("accepts a known-good SHA-256 attestation", () => {
		const cwd = makeWorkspace();
		const plan = "### Phase 1\n**Status:** complete\n";
		writePlan(cwd, plan);
		writeFileSync(join(cwd, ".planning", "demo", ".attestation"), sha256(plan));

		const result = checkPlanAttestation(readPlanStatus(cwd));

		expect(result).toMatchObject({
			enabled: true,
			tampered: false,
			expected: sha256(plan),
			actual: sha256(plan),
		});
	});

	it("rejects mutated plan content when the attestation hash no longer matches", () => {
		const cwd = makeWorkspace();
		const originalPlan = "### Phase 1\n**Status:** complete\n";
		const mutatedPlan = "### Phase 1\n**Status:** in_progress\n";
		writePlan(cwd, originalPlan);
		writeFileSync(join(cwd, ".planning", "demo", ".attestation"), sha256(originalPlan));
		writeFileSync(join(cwd, ".planning", "demo", "task_plan.md"), mutatedPlan);

		const result = checkPlanAttestation(readPlanStatus(cwd));

		expect(result.enabled).toBe(true);
		expect(result.tampered).toBe(true);
		expect(result.expected).toBe(sha256(originalPlan));
		expect(result.actual).toBe(sha256(mutatedPlan));
	});

	it("treats an invalid attestation file as a blocking mismatch", () => {
		const cwd = makeWorkspace();
		writePlan(cwd, "### Phase 1\n**Status:** complete\n");
		writeFileSync(join(cwd, ".planning", "demo", ".attestation"), "not-a-sha256");

		const result = checkPlanAttestation(readPlanStatus(cwd));

		expect(result.enabled).toBe(true);
		expect(result.tampered).toBe(true);
		expect(result.expected).toBeUndefined();
		expect(result.actual).toBeUndefined();
	});
});
