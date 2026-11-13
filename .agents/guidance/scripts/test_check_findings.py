#!/usr/bin/env python3
"""Regressions for the findings format checker."""

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from check_findings import check, check_text, parse

SCRIPT = Path(__file__).with_name("check_findings.py")
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "findings"


EVIDENCE = "Found by: source review\n\nReproduced by: none\n\n"


def entry(entry_id, severity="High", decision="Open", body=EVIDENCE + "What goes wrong.", title=None):
    status = f"Severity: {severity}" + (f" · Decision: {decision}" if decision else "")
    return f'<a id="{entry_id}"></a>\n### {title or "Entry " + entry_id}\n\n{status}\n\n{body}\n'


def findings(*entries, others=()):
    text = "# Bugs and issues\n\n## Actionable\n\n" + "\n".join(entries)
    if others:
        text += "\n## Other entries\n\n" + "\n".join(others)
    return text


class Fixtures(unittest.TestCase):
    @unittest.skipUnless(FIXTURES.is_dir(), "repository fixtures are not shipped")
    def test_parse_matches_the_shared_fixtures(self):
        for folder in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
            expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
            source = next(folder.glob("*.md"))
            entries, problems = parse(source.read_text(encoding="utf-8"))
            self.assertEqual(
                [{"line": line, "message": message} for line, message in problems],
                expected["fileProblems"],
            )
            self.assertEqual(
                [
                    {
                        "id": e.id, "title": e.title, "level": e.level, "line": e.line,
                        "end": e.end, "statusLine": e.status_line, "severity": e.severity,
                        "decision": e.decision,
                        "issue": {"key": e.issue[0], "url": e.issue[1]} if e.issue else None,
                        "run": e.run,
                        "problems": e.problems,
                    }
                    for e in entries
                ],
                expected["entries"],
                folder.name,
            )


class FileChecks(unittest.TestCase):
    def messages(self, text):
        return [issue.message for issue in check_text("f.md", text)[1]]

    def test_a_well_formed_file_is_clean(self):
        text = findings(
            entry("a", "Critical"),
            entry("b", "High", "Need fix — [ACME-1](https://g5.example/i/1)"),
            entry("c", "Low", "Irrelevant — user decided this issue is not important."),
            others=[entry("q", "Medium", None)],
        )
        self.assertEqual(self.messages(text), [])

    def test_order_duplicates_and_heading_level(self):
        text = findings(
            entry("a", "Low"),
            entry("b", "High"),
            entry("a", "Low"),
            others=[entry("q", "Medium", None)],
        ) + entry("late", "Low") + '<a id="h2"></a>\n## Wrong level\n\nSeverity: Low\n'
        messages = self.messages(text)
        self.assertIn("`b` (High) comes after less severe `a` (Low)", messages)
        self.assertIn("duplicate ID `a` (first at line 5)", messages)
        self.assertIn("actionable entry `late` comes after other entries (first: `q`)", messages)
        self.assertIn("an entry heading is `###`", messages)

    def test_a_level_three_heading_without_anchor_is_reported(self):
        text = findings(entry("a", body="Text.\n\n### Proposed repair\n\nOrphaned.\n\n#### Fine\n"))
        self.assertIn(
            "heading `Proposed repair` has no anchor; an entry needs one, and headings inside an entry are `####`",
            self.messages(text),
        )

    def test_anchor_without_heading_and_bad_id(self):
        messages = self.messages('<a id="x"></a>\n\nText\n\n' + entry("bad id"))
        self.assertIn("anchor `x` is not directly followed by a heading", messages)
        self.assertIn("ID `bad id` must be letters, digits, `.`, `_` or `-`", messages)


class OntologyLinks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / ".g5"
        self.verification = self.root / "TLA_verification"
        self.ontology = self.root / "ontology"
        (self.ontology / "features").mkdir(parents=True)
        self.verification.mkdir()
        (self.verification / "bugs_issues.md").write_text(findings(entry("a")), encoding="utf-8")

    def test_unknown_ids_and_root_links_are_reported(self):
        (self.ontology / "features" / "f.g5.md").write_text(
            "See [a](../../TLA_verification/bugs_issues.md#a), [gone](../../TLA_verification/bugs_issues.md#gone)"
            " and `[code](../../TLA_verification/bugs_issues.md#ignored)`.\n",
            encoding="utf-8",
        )
        (self.ontology / "root.g5.md").write_text(
            "[Bugs](../TLA_verification/bugs_issues.md)\n", encoding="utf-8"
        )
        messages = [issue.message for issue in check(self.verification, self.ontology)]
        self.assertEqual(
            messages,
            [
                "`bugs_issues.md#gone` names no entry",
                "the ontology root links `bugs_issues.md`; G5's Core Ontology panel lists it instead",
            ],
        )


class Evidence(unittest.TestCase):
    """Open entries name their evidence; receipts they link exist; no `Sources:` lines."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.verification = Path(temp.name) / "TLA_verification"
        receipt = self.verification / "results" / "numbering" / "20261024T014713Z-safety-a"
        receipt.mkdir(parents=True)
        (receipt / "receipt.json").write_text("{}", encoding="utf-8")

    def messages(self, name, *entries):
        for other in ("bugs_issues.md", "design_simplification.md"):
            (self.verification / other).unlink(missing_ok=True)
        (self.verification / name).write_text(findings(*entries), encoding="utf-8")
        return [issue.message for issue in check(self.verification)]

    def test_an_open_bug_names_how_it_was_found_and_reproduced(self):
        run = "results/numbering/20261024T014713Z-safety-a/receipt.json"
        self.assertEqual(self.messages("bugs_issues.md", entry("a", body=f"Found by: [safety]({run})\n\nReproduced by: none\n\nWhy.")), [])
        self.assertEqual(
            self.messages("bugs_issues.md", entry("a", body="Why.")),
            ["`a` has no `Found by:` line", "`a` has no `Reproduced by:` line"],
        )
        self.assertEqual(
            self.messages("bugs_issues.md", entry("a", body="Found by: [ctl](results/numbering/missing/receipt.json)\n\nReproduced by: none\n\nWhy.")),
            ["`a` links a missing receipt `results/numbering/missing/receipt.json`"],
        )

    def test_a_decided_entry_and_other_entries_need_no_evidence_lines(self):
        decided = entry("a", "High", "Need fix — [ACME-1](https://g5.example/i/1)", body="Why.")
        self.assertEqual(self.messages("bugs_issues.md", decided), [])
        self.assertEqual(self.messages("bugs_issues.md", entry("q", "Low", None, body="Drift.")), [])

    def test_an_open_simplification_compares_runs(self):
        run = "results/numbering/20261024T014713Z-safety-a/receipt.json"
        for line in (
            f"Comparison: [As-built]({run}) → [Proposed simplification]({run}). Same bounds.",
            f"Comparison: [As-built]({run}) → none. The proposal was not run.",
            "Comparison: none. No model covers this change.",
        ):
            self.assertEqual(self.messages("design_simplification.md", entry("s", body=f"{line}\n\nWhy.")), [], line)
        self.assertEqual(
            self.messages("design_simplification.md", entry("s", body="Why.")),
            ["`s` has no `Comparison:` line"],
        )
        self.assertEqual(
            self.messages("design_simplification.md", entry("s", body="Comparison: [model](models/numbering/manifest.json) → none.\n\nWhy.")),
            ["`s`: `Comparison:` starts with the as-built run's receipt, or is `none`"],
        )

    def test_sources_lines_are_reported_unless_decided(self):
        sources = "Sources: Older register [PG-1](../uplift/code_gaps.md#pg-1)."
        self.assertEqual(
            self.messages("bugs_issues.md", entry("a", body=EVIDENCE + sources)),
            ["`a` has a `Sources:` line; link the evidence itself, not the reports the entry replaces"],
        )
        self.assertEqual(
            self.messages("bugs_issues.md", entry("q", "Low", None, body=sources)),
            ["`q` has a `Sources:` line; link the evidence itself, not the reports the entry replaces"],
        )
        decided = entry("a", "High", "Irrelevant — user decided this issue is not important.", body=sources)
        self.assertEqual(self.messages("bugs_issues.md", decided), [])


class RunLine(unittest.TestCase):
    """An optional `Run:` line directly after the status line names the run that first recorded the entry."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.verification = Path(temp.name)

    def messages(self, *entries):
        (self.verification / "bugs_issues.md").write_text(findings(*entries), encoding="utf-8")
        return [issue.message for issue in check(self.verification)]

    def test_a_run_line_after_the_status_line_is_read_and_evidence_still_found(self):
        entries = (
            entry("a", body="Run: Uplift 2026-10-24\n\n" + EVIDENCE + "Why."),
            entry("b", body="Run:  Base re-verification 2026-11-06 (incremental)  \n\n" + EVIDENCE + "Why."),
            entry("c"),
        )
        # Also on the line straight after the status line, and in other entries.
        other = '<a id="q"></a>\n### Entry q\n\nSeverity: Low\nRun: Uplift 2026-10-24\n\nDrift.\n'
        parsed, problems = parse(findings(*entries, others=[other]))
        self.assertEqual(problems, [])
        self.assertEqual(
            [(e.id, e.run, e.problems) for e in parsed],
            [
                ("a", "Uplift 2026-10-24", []),
                ("b", "Base re-verification 2026-11-06 (incremental)", []),
                ("c", None, []),
                ("q", "Uplift 2026-10-24", []),
            ],
        )
        self.assertEqual(self.messages(*entries), [])

    def test_an_empty_label_is_reported(self):
        entries, _ = parse(entry("a", body="Run:   \n\n" + EVIDENCE + "Why."))
        self.assertEqual((entries[0].run, entries[0].problems), (None, ["the `Run:` line names no run"]))
        self.assertEqual(self.messages(entry("a", body="Run:\n\n" + EVIDENCE + "Why.")), ["the `Run:` line names no run"])

    def test_a_run_line_elsewhere_is_reported_and_not_read(self):
        misplaced = entry("a", body=EVIDENCE + "Run: Uplift 2026-10-24\n\nWhy.")
        self.assertIsNone(parse(misplaced)[0][0].run)
        self.assertEqual(
            self.messages(misplaced),
            ["`a` has a `Run:` line away from its status line; it goes directly after it"],
        )
        # A fenced example is not a line of the entry.
        self.assertEqual(self.messages(entry("a", body=EVIDENCE + "```text\nRun: x\n```")), [])


class BackLinks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / ".g5"
        self.verification = self.root / "TLA_verification"
        self.ontology = self.root / "ontology"
        (self.ontology / "features").mkdir(parents=True)
        self.verification.mkdir()

    def page(self, metadata):
        (self.ontology / "features" / "r.g5.md").write_text(
            '# R\n\n<a id="old-rule"></a>\n<a id="rule"></a>\n[I · rule]\n\nA rule.\n\n'
            f"## Metadata\n\n### rule\n\n- agent\n{metadata}\n",
            encoding="utf-8",
        )

    def messages(self, body):
        (self.verification / "bugs_issues.md").write_text(findings(entry("a", body=EVIDENCE + body)), encoding="utf-8")
        return [issue.message for issue in check(self.verification, self.ontology)]

    def test_a_named_statement_must_link_the_entry_back(self):
        self.page("")
        self.assertEqual(
            self.messages("Governing: [rule](../ontology/features/r.g5.md#rule)."),
            ["`a` names `features/r.g5.md#rule`, whose metadata does not link the entry back"],
        )
        self.page("- Findings: [a](../../TLA_verification/bugs_issues.md#a)")
        self.assertEqual(self.messages("Governing: [rule](../ontology/features/r.g5.md#rule)."), [])
        # A former ID is an alias anchor of the same statement.
        self.assertEqual(self.messages("Governing: [rule](../ontology/features/r.g5.md#old-rule)."), [])

    def test_root_statements_need_no_back_link(self):
        (self.ontology / "root.g5.md").write_text(
            '# Root\n\n<a id="purpose"></a>\n[I · purpose]\n\nWhy.\n\n## Metadata\n\n### purpose\n\n- human\n',
            encoding="utf-8",
        )
        self.assertEqual(self.messages("Governing: [purpose](../ontology/root.g5.md#purpose)."), [])

    def test_links_are_read_as_the_viewer_reads_them(self):
        # A title, a link written from the `.g5` folder, and a single-quoted alias.
        (self.ontology / "features" / "r.g5.md").write_text(
            "# R\n\n<a id='old-rule'></a>\n<a id=\"rule\"></a>\n[I · rule]\n\nA rule.\n\n"
            "## Metadata\n\n### rule\n\n- agent\n- Findings: [a](../TLA_verification/bugs_issues.md#a \"Entry a\")\n",
            encoding="utf-8",
        )
        self.assertEqual(self.messages('See [rule](../ontology/features/r.g5.md#old-rule "The rule").'), [])

    def test_a_decided_entry_naming_a_removed_statement_is_left_alone(self):
        self.page("")
        (self.verification / "bugs_issues.md").write_text(
            findings(entry("a", "High", "Defer — [ACME-1](https://g5.example/i/1)", body="See [gone](../ontology/features/r.g5.md#gone).")),
            encoding="utf-8",
        )
        self.assertEqual([issue.message for issue in check(self.verification, self.ontology)], [])

    def test_a_link_to_a_missing_statement_is_reported(self):
        self.page("")
        self.assertEqual(
            self.messages("See [gone](../ontology/features/r.g5.md#gone) and [code](../../src/a.cs#L1)."),
            ["`a` links `features/r.g5.md#gone`, which is not a statement"],
        )


class Previous(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.verification = self.repo / ".g5" / "TLA_verification"
        self.verification.mkdir(parents=True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.decided = entry("a", "High", "Defer — [ACME-1](https://g5.example/i/1)")
        self.write(findings(self.decided, entry("b", "Low")))
        self.git("add", "-A")
        self.git("commit", "-qm", "findings")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True)

    def write(self, text):
        (self.verification / "bugs_issues.md").write_text(text, encoding="utf-8")

    def messages(self):
        return [issue.message for issue in check(self.verification, previous="HEAD")]

    def test_moving_a_decided_entry_is_allowed(self):
        self.write(findings(entry("c", "Critical"), self.decided, entry("b", "Low")))
        self.assertEqual(self.messages(), [])

    def test_changing_or_removing_a_decided_entry_is_reported(self):
        self.write(findings(self.decided.replace("What goes wrong.", "Rewritten."), entry("b", "Low")))
        self.assertEqual(self.messages(), ["decided entry `a` changed; keep its text and status line"])
        self.write(findings(entry("b", "Low")))
        self.assertEqual(self.messages(), ["decided entry `a` was removed"])

    def test_a_run_line_is_added_to_open_entries_only(self):
        run = "Run: Base re-verification 2026-11-06 (incremental)\n\n"
        self.write(findings(self.decided, entry("b", "Low", body=run + EVIDENCE + "What goes wrong.")))
        self.assertEqual(self.messages(), [])
        self.write(findings(self.decided.replace(EVIDENCE, run + EVIDENCE), entry("b", "Low")))
        self.assertEqual(self.messages(), ["decided entry `a` changed; keep its text and status line"])


class PreviousCopies(unittest.TestCase):
    """The owner's decisions may be uncommitted: compare with copies taken before editing."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.verification = Path(temp.name) / "TLA_verification"
        self.before = Path(temp.name) / "before"
        self.verification.mkdir()
        self.before.mkdir()

    def test_an_uncommitted_decision_is_protected_and_a_redecision_is_not_flagged(self):
        decided = entry("a", "High", "Irrelevant — user decided this issue is not important.")
        (self.before / "bugs_issues.md").write_text(findings(decided), encoding="utf-8")
        (self.verification / "bugs_issues.md").write_text(findings(decided), encoding="utf-8")
        self.assertEqual(check(self.verification, previous=str(self.before)), [])
        (self.verification / "bugs_issues.md").write_text(findings(entry("a", "High")), encoding="utf-8")
        self.assertEqual(
            [i.message for i in check(self.verification, previous=str(self.before))],
            ["decided entry `a` changed; keep its text and status line"],
        )

    def test_a_removed_file_with_decided_entries_is_reported(self):
        (self.before / "bugs_issues.md").write_text(
            findings(entry("a", "High", "Defer — [ACME-1](https://g5.example/i/1)")), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.verification), "--previous", str(self.before)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("decided entry `a` was removed", result.stdout)

    def test_an_unknown_revision_is_a_usage_error(self):
        (self.verification / "bugs_issues.md").write_text(findings(entry("a")), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.verification), "--previous", "no-such-ref"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.assertEqual(self.run_cli(str(folder)).returncode, 0)
            (folder / "bugs_issues.md").write_text(findings(entry("a")), encoding="utf-8")
            self.assertEqual(self.run_cli(str(folder)).returncode, 0)
            (folder / "design_simplification.md").write_text(entry("a", "Severe"), encoding="utf-8")
            result = self.run_cli(str(folder))
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown severity `Severe`", result.stdout)
            self.assertEqual(self.run_cli(str(folder / "missing")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
