export const PKG_NAME = "planning-with-files";
export const CUSTOM_TYPE = "planning-with-files";

export const PLAN_DATA_BEGIN = "===BEGIN PLAN DATA===";
export const PLAN_DATA_END = "===END PLAN DATA===";

// Keep this reminder stable in cache-safe mode.
export const CACHE_SAFE_REMINDER =
	"[planning-with-files] Read task_plan.md for current phase and status. " +
	"Read findings.md for research context. Read progress.md for recent changes. " +
	"Continue from the current phase.";

// Keep this reminder stable in cache-safe mode.
export const PRE_TOOL_CACHE_SAFE_REMINDER =
	"[planning-with-files] Before tool use, read task_plan.md for the active phase and constraints.";

export const POST_WRITE_REMINDER =
	"[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status.";

export const TAMPERED_PREFIX = "[planning-with-files] [PLAN TAMPERED — injection blocked]";

export const AUTO_CONTINUE_LIMIT = 3;

export const DEFAULT_LOOP_INTERVAL_MS = 10 * 60 * 1000;
export const DEFAULT_LOOP_PROMPT =
	"Read task_plan.md and progress.md. Run scripts/check-complete.sh to see remaining phases. " +
	"If no progress.md entry has been added since the last loop tick, write one summarizing the current state. " +
	"If a phase finished, update its Status: line in task_plan.md. Continue the next phase if work remains.";

export const DEFAULT_GOAL_CONDITION =
	"all phases in task_plan.md report Status: complete and check-complete.sh reports ALL PHASES COMPLETE";
