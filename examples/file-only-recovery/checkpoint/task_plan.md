# Task Plan: Word and line counts

## Goal

Implement counts.py with word_count, line_count, and unique_words.

## Next Step

Implement line_count and unique_words in counts.py. word_count is already done.

## Current Phase

Phase 3

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
- [ ] Implement line_count
- [ ] Implement unique_words
- **Status:** in_progress

### Phase 4: Testing & Verification

- [ ] Check the empty string
- [ ] Check Hello hello
- **Status:** pending

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

- Update phase status as work progresses: `pending` to `in_progress` to `complete`.
- word_count is already done. line_count and unique_words are not.
