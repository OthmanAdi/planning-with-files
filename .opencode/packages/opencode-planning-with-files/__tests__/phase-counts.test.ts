import * as fs from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { gateCounts } from "../src/core.js"

const cases = JSON.parse(fs.readFileSync(fileURLToPath(new URL("../../../../tests/fixtures/phase-counts/cases.json", import.meta.url)), "utf8"))

describe("shared phase-count fixtures (#377)", () => {
  for (const fixture of cases) {
    it(fixture.name, () => {
      const { total, complete, in_progress, pending } = fixture
      expect(gateCounts(fixture.plan)).toEqual({ total, complete, in_progress, pending,
        ...(fixture.invalid_structure ? { invalid_structure: true } : {}) })
    })
  }
})
