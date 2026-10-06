"""Finished counts: all three functions match TASK.md."""


def word_count(text: str) -> int:
    if text == "":
        return 0
    return len(text.split())


def line_count(text: str) -> int:
    if text == "":
        return 0
    return len(text.splitlines())


def unique_words(text: str) -> int:
    if text == "":
        return 0
    return len(set(text.split()))
