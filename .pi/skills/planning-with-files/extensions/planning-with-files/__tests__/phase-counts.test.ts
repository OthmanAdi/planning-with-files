import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isAllPhasesComplete, readPlanStatus } from "../plan.ts";

const cases = JSON.parse(fs.readFileSync(fileURLToPath(new URL("../../../../../../tests/fixtures/phase-counts/cases.json", import.meta.url)), "utf8"));

describe("shared phase-count fixtures (#377)", () => {
  for (const fixture of cases) {
    it(fixture.name, () => {
      const root = fs.mkdtempSync(path.join(os.tmpdir(), "pwf-phase-counts-"));
      try {
        fs.writeFileSync(path.join(root, "task_plan.md"), fixture.plan);
        const status = readPlanStatus(root);
        expect([status.totalPhases, status.completePhases, status.inProgressPhases, status.pendingPhases])
          .toEqual([fixture.total, fixture.complete, fixture.in_progress, fixture.pending]);
        expect(isAllPhasesComplete(status)).toBe(!fixture.invalid_structure && fixture.total > 0 && fixture.complete === fixture.total);
      } finally { fs.rmSync(root, { recursive: true, force: true }); }
    });
  }
});

it("preserves case-insensitive phase and status labels in Pi", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pwf-phase-counts-"));
  try {
    fs.writeFileSync(path.join(root, "task_plan.md"), "### phase 1: Review\n**status:** Complete\n");
    expect(isAllPhasesComplete(readPlanStatus(root))).toBe(true);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
