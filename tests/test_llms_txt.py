"""Guard: llms.txt keeps its AI-search surface contract.

llms.txt is the machine-readable project summary consumed by AI search
engines (llmstxt.org convention). The v3.8.0 rewrite added a Q&A section
mirroring the README FAQ. These checks pin the parts that must not drift:
the llms.txt shape (H1 + blockquote summary), the canonical links list,
the seven FAQ questions, the money phrases, the honesty constraints
(only numbers already public in the repo, no rejected SEO topics, no
competitor names), the 60+ agent count, and the ~120 line budget.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LLMS_TXT = REPO_ROOT / "llms.txt"

CANONICAL_LINKS = [
    "https://github.com/OthmanAdi/planning-with-files/blob/master/README.md",
    "https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/SKILL.md",
    "https://github.com/OthmanAdi/planning-with-files/blob/master/MIGRATION.md",
    "https://github.com/OthmanAdi/planning-with-files/blob/master/docs/evals.md",
    "https://github.com/OthmanAdi/planning-with-files/blob/master/CITATION.cff",
]

FAQ_QUESTIONS = [
    "### How do I stop my coding agent from losing its plan after /clear or a crash?",
    "### What is the difference between planning-with-files and an agent memory tool?",
    "### How does this prevent context rot?",
    "### Which coding agents does this work with?",
    "### How does this work with Claude Code's plan mode?",
    "### What happens to the plan files after a task is complete?",
    "### How much overhead does the skill add?",
]

# SEO money phrases; each must appear at least once (case-insensitive).
MONEY_PHRASES = [
    r"persistent planning for AI coding agents",
    r"survives? /clear and context loss",
    r"context rot",
    r"long-running agent tasks",
    r"session recovery",
    r"Agent Skills standard",
]

# Only numbers already public in the repo (README FAQ + docs/evals.md).
PUBLIC_NUMBERS = ["96.7%", "1084", "330", "5.0", "13.3"]

# Topics rejected on honesty grounds plus competitor names. Word-bounded so
# e.g. "decline" cannot false-positive on "cline".
FORBIDDEN_TERMS = [
    r"\bmcp\b",
    r"\bagent-memory\b",
    r"\bsuperpowers\b",
    r"\bspec-kit\b",
    r"\bmemory-bank\b",
    r"\bcline\b",
]


class LlmsTxtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = LLMS_TXT.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def test_h1_and_summary_shape(self):
        self.assertEqual(self.lines[0], "# planning-with-files")
        body = [ln for ln in self.lines[1:] if ln.strip()]
        self.assertTrue(
            body and body[0].startswith("> "),
            "first non-empty line after the H1 must be the '> ' summary",
        )

    def test_line_budget(self):
        self.assertLessEqual(len(self.lines), 120, "llms.txt must stay compact")

    def test_canonical_links_present(self):
        for url in CANONICAL_LINKS:
            self.assertIn(url, self.text, f"canonical link missing: {url}")

    def test_faq_questions_present(self):
        for q in FAQ_QUESTIONS:
            self.assertIn(q, self.text, f"FAQ question missing: {q}")

    def test_money_phrases_present(self):
        for pattern in MONEY_PHRASES:
            self.assertTrue(
                re.search(pattern, self.text, re.IGNORECASE),
                f"money phrase missing: {pattern}",
            )

    def test_public_numbers_present(self):
        for num in PUBLIC_NUMBERS:
            self.assertIn(num, self.text, f"public number missing: {num}")

    def test_recovery_turns_marked_internal_benchmark(self):
        # 5.0 vs 13.3 may only be cited as internal benchmark v1.
        self.assertIn("internal benchmark v1", self.text)

    def test_agent_count_is_60_plus(self):
        self.assertIn("60+", self.text)
        self.assertNotIn("70+", self.text)
        self.assertNotIn("71", self.text)

    def test_forbidden_terms_absent(self):
        for pattern in FORBIDDEN_TERMS:
            self.assertFalse(
                re.search(pattern, self.text, re.IGNORECASE),
                f"forbidden term present: {pattern}",
            )

    def test_no_dash_punctuation(self):
        # Prose rule: no em dashes or en dashes anywhere in the file.
        self.assertNotIn("—", self.text)
        self.assertNotIn("–", self.text)


if __name__ == "__main__":
    unittest.main()
