# Task

Implement `counts.py` in this directory. Add three functions. Use the Python standard library only.

## Functions

`word_count(text: str) -> int`

Count words by splitting on whitespace. `text.split()` with no arguments is the split. An empty string returns 0.

`line_count(text: str) -> int`

Count lines the way `str.splitlines` does. An empty string returns 0. `Hello hello` is one line. `a\nb` is two lines.

`unique_words(text: str) -> int`

Count distinct words from the same whitespace split. Comparison is case-sensitive, so `Hello` and `hello` are different words. An empty string returns 0. `Hello hello` is two words and two unique words.

## Done

All three functions return the values above and do not raise on those inputs. In `task_plan.md`, Phase 3 status is `complete` and Current Phase has moved past Phase 3.
