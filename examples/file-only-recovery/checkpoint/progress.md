# Progress Log

Use this file as the chronological record of work performed, files changed, validation results, and errors.

## Session: 2026-10-06

This session is the committed halfway checkpoint, not a model transcript.

### Phase 1: Requirements & Discovery

- **Status:** complete
- **Started:** 2026-10-06
- Actions taken:
  - Read TASK.md
  - Recorded the counting rules in findings.md
- Files created/modified:
  - findings.md

### Phase 2: Planning & Structure

- **Status:** complete
- Actions taken:
  - Defined the word, line, and unique-word rules
  - Created counts.py
- Files created/modified:
  - counts.py
  - task_plan.md

### Phase 3: Implementation

- **Status:** in_progress
- Actions taken:
  - Implemented word_count
  - Left line_count and unique_words unimplemented
- Files created/modified:
  - counts.py

## Test Results

| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| word_count | empty string | 0 | 0 | pass |
| word_count | Hello hello | 2 | 2 | pass |
| line_count | any | a line count | NotImplementedError | fail |
| unique_words | Hello hello | 2 | NotImplementedError | fail |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
|           |       | 1       |            |

## 5-Question Reboot Check

Use this table when resuming to confirm the current phase, destination, goal, findings, and completed work.

| Question | Answer |
|----------|--------|
| Where am I? | Phase 3 |
| Where am I going? | Phase 4 and Phase 5 |
| What's the goal? | Implement word_count, line_count, and unique_words in counts.py |
| What have I learned? | Whitespace split, case-sensitive unique words, empty string returns 0. See findings.md |
| What have I done? | word_count is done. line_count and unique_words are not |

---

*Update this file after completing a phase, running validation, or encountering an error.*
