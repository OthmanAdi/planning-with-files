# Task Plan: Word and line counts

## Goal

Implement counts.py with word_count, line_count, and unique_words.

## Next Step

Check line_count and unique_words against TASK.md, including the empty string.

## Current Phase

Phase 4

## Phases

### Phase 1: Requirements & Discovery

- [x] Read TASK.md
- [x] Record the counting rules in findings.md
- **Status:** complete

### Phase 2: Planning & Structure

- [x] Define word, line, and unique-word rules
- [x] Create counts.py
- **Status:** complete

### Phase 3: Implementation

- [x] Implement word_count
- [x] Implement line_count
- [x] Implement unique_words
- **Status:** complete

### Phase 4: Testing & Verification

- [ ] Check the empty string
- [ ] Check Hello hello
- **Status:** in_progress

### Phase 5: Delivery

- [ ] Leave the finished counts.py in this directory
- **Status:** pending

## Key Questions

1. How are words split? Whitespace, via `str.split()` with no arguments.
2. Are unique words case-sensitive? Yes. `Hello` and `hello` are different.
3. What does an empty string return? 0 for all three functions.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Whitespace split | Matches `str.split()` with no arguments |
| Case-sensitive unique words | `Hello hello` is two unique words |
| Empty string returns 0 | Specified for all three functions |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes

- Phase 3 is complete. The current phase is Phase 4.
