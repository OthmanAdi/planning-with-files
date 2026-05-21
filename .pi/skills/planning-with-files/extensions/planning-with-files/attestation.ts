import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import type { PlanStatus } from "./plan.ts";

export interface AttestationCheck {
	enabled: boolean;
	tampered: boolean;
	expected?: string;
	actual?: string;
	attestationPath?: string;
}

function normalizeHash(value: string): string | undefined {
	const hash = value.trim().toLowerCase();
	if (!/^[a-f0-9]{64}$/.test(hash)) return undefined;
	return hash;
}

function sha256File(path: string): string | undefined {
	try {
		const content = readFileSync(path);
		return createHash("sha256").update(content).digest("hex");
	} catch {
		return undefined;
	}
}

export function checkPlanAttestation(status: PlanStatus): AttestationCheck {
	if (!status.exists || !status.planPath) {
		return { enabled: false, tampered: false };
	}

	const attestationPath = status.attestationCandidates.find((candidate) => existsSync(candidate));
	if (!attestationPath) {
		return { enabled: false, tampered: false };
	}

	const expected = normalizeHash(readFileSync(attestationPath, "utf-8"));
	if (!expected) {
		return { enabled: true, tampered: true, attestationPath };
	}

	const actual = sha256File(status.planPath);
	if (!actual) {
		return { enabled: true, tampered: true, expected, attestationPath };
	}

	return {
		enabled: true,
		tampered: actual !== expected,
		expected,
		actual,
		attestationPath,
	};
}
