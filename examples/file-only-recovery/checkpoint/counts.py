"""Halfway counts: word_count is done. The other two are not."""


def word_count(text: str) -> int:
    if text == "":
        return 0
    return len(text.split())


def line_count(text: str) -> int:
    raise NotImplementedError


def unique_words(text: str) -> int:
    raise NotImplementedError
