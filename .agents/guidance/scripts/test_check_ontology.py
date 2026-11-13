#!/usr/bin/env python3
"""Focused filesystem/CLI regressions for the uplift-only structural checker."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

from check_ontology import check_paths, sentence_count


SCRIPT = Path(__file__).with_name("check_ontology.py")


def contract(stable_id="example.rule", kind="I", tags="- agent", body="Retain the required behavior."):
    return f'# Contract\n\n## A rule\n\n<a id="{stable_id}"></a>\n[{kind} · {stable_id}]\n\n{body}\n\n## Metadata\n\n### {stable_id}\n\n{tags}\n- From the supplied requirement.\n'


class OntologyChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ontology = self.root / "ontology"
        self.ontology.mkdir()

    def write(self, name, content):
        path = self.ontology / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def check(self, *paths, **kwargs):
        return check_paths(list(paths) or [self.ontology], **kwargs)

    def codes(self, result):
        return [issue.code for issue in result.issues]

    def assert_valid(self, result):
        self.assertEqual(result.issues, [], "\n".join(map(str, result.issues)))

    def test_valid_contract_index_and_architecture_overview(self):
        self.write("root.g5.md", contract(body="See [Architecture](concepts/software_architecture.g5.md#architecture)."))
        self.write("concepts/software_architecture.g5.md", "# Architecture\n\nA readable overview.\n")
        self.write("index.md", "# Reading index\n\n[Contract](root.g5.md#a-rule)\n")
        result = self.check()
        self.assert_valid(result)
        self.assertEqual((len(result.files), result.blocks), (3, 1))

    def test_plain_markdown_under_g5_ontology_is_flagged_but_still_checked(self):
        ontology = self.root / ".g5" / "ontology"
        (ontology / "features").mkdir(parents=True)
        (ontology / "root.g5.md").write_text(contract(), encoding="utf-8")
        (ontology / "features" / "notes.md").write_text('<a id="notes.rule"></a>\n[I · notes.rule]\n\nNo footer.\n', encoding="utf-8")
        result = check_paths([ontology])
        flagged = [issue for issue in result.issues if issue.code == "ontology-file-name"]
        self.assertEqual([issue.path.name for issue in flagged], ["notes.md"])
        self.assertIn("rename it to .g5.md", flagged[0].message.lower())
        self.assertIn("metadata-missing", self.codes(result), "the misnamed page's structure is still checked")
        self.assertEqual(len(result.files), 2)

    def test_plain_markdown_outside_g5_ontology_is_not_flagged(self):
        self.write("index.md", "# Reading index\n")
        self.assertNotIn("ontology-file-name", self.codes(self.check()))

    def test_valid_heading_variants_and_q_tag_forms(self):
        for number, tags in enumerate(["- uncertain", "- agent; uncertain", "* human-verified, `uncertain`", "+ `agent`; `uncertain`", "- agent · uncertain"]):
            value = contract(f"q.{number}", "Q", tags)
            value = value.replace("## A rule", "A rule\n------")
            value = value.replace("## Metadata", "## Metadata ##").replace(f"### q.{number}", f"### q.{number} ###")
            self.write(f"{number}.g5.md", value)
        self.assert_valid(self.check())

    def test_fenced_examples_and_comments_do_not_define_blocks_or_links(self):
        example = "\n~~~md\n[I bad marker]\n[missing](absent.md)\n~~~\n\n````md\n```\n[Q · q.fake]\n````\n"
        self.write("root.g5.md", contract(body="Required.\n<!-- [I bad] -->\n" + example))
        result = self.check()
        self.assert_valid(result)
        self.assertEqual(result.blocks, 1)

    def test_explicit_tag_prefix_can_share_provenance_bullet(self):
        self.write("source.md", "# Source\n\nHuman statement.\n")
        for tags in [
            "- agent; uncertain — [human statement](source.md) leaves the choice open.",
            "- `agent`; `uncertain` — [human statement](source.md).",
            "- agent; uncertain: [human statement](source.md).",
            "- agent; uncertain – [human statement](source.md).",
            "* human-verified, `uncertain`: [human statement](source.md).",
            "+ `agent` · uncertain — [human statement](source.md).",
        ]:
            with self.subTest(tags=tags):
                path = self.write("question.g5.md", contract(kind="Q", tags=tags))
                self.assert_valid(self.check(path))

    def test_explicit_tag_list_can_end_with_period(self):
        for tags in ["- agent; uncertain.", "* `agent`; `uncertain`.", "+ uncertain.  "]:
            with self.subTest(tags=tags):
                path = self.write("question.g5.md", contract(kind="Q", tags=tags))
                self.assert_valid(self.check(path))

    def test_annotation_boundary_does_not_turn_prose_or_code_into_tags(self):
        for tags in [
            "- agent; not uncertain — provenance.",
            "- agent; uncertainty remains: provenance.",
            "- agent; uncertain if the source supports the choice — provenance.",
            "- agent; uncertain?: provenance.",
            "- agent; `uncertain — quoted example`",
            "- agent; `uncertain: quoted example`",
            "- agent; `uncertain.`",
            "- agent; uncertainty.",
            "- agent; `uncertain",
            "- agent; uncertain`",
            "- [uncertain](https://example.org): provenance.",
            "- agent\n- The evidence is uncertain — provenance.",
        ]:
            with self.subTest(tags=tags):
                path = self.write("question.g5.md", contract(kind="Q", tags=tags))
                self.assertIn("q-uncertain", self.codes(self.check(path)))

    def test_duplicate_ids_across_explicit_files_and_optional_root(self):
        first = self.write("first.g5.md", contract())
        second = self.write("second.g5.md", contract())
        self.assert_valid(self.check(first))
        result = self.check(first, ontology_root=self.ontology)
        self.assertEqual(self.codes(result), ["duplicate-id"])
        self.assertEqual(result.issues[0].path, second.resolve())
        self.assertIn(str(first.resolve()), result.issues[0].message)

    def test_missing_extra_duplicate_and_empty_metadata(self):
        cases = {
            "missing-footer": (contract().split("## Metadata")[0], "metadata-missing"),
            "missing-entry": (contract().replace("### example.rule\n\n- agent\n- From the supplied requirement.", ""), "metadata-missing"),
            "extra-entry": (contract() + "\n### orphan\n\n- agent\n", "metadata-extra"),
            "duplicate-entry": (contract() + "\n### example.rule\n\n- agent\n", "metadata-duplicate"),
            "empty-entry": (contract().replace("- agent\n- From the supplied requirement.", "<!-- no metadata -->\n-"), "metadata-empty"),
        }
        for name, (value, code) in cases.items():
            with self.subTest(name=name):
                path = self.write(f"{name}.g5.md", value)
                self.assertIn(code, self.codes(self.check(path)))

    def test_recorded_four_order_errors_and_three_missing_q_tags(self):
        for n in range(4):
            self.write(f"order{n}.g5.md", f'# Rules\n\n<a id="a{n}"></a>\n[I · a{n}]\n\nFirst.\n\n<a id="b{n}"></a>\n[D · b{n}]\n\nSecond.\n\n## Metadata\n\n### b{n}\n\n- agent\n\n### a{n}\n\n- agent\n')
        for n in range(3):
            self.write(f"question{n}.g5.md", contract(f"q{n}", "Q"))
        codes = self.codes(self.check())
        self.assertEqual(codes.count("metadata-order"), 4)
        self.assertEqual(codes.count("q-uncertain"), 3)
        self.assertEqual(len(codes), 7)

    def test_q_uncertainty_must_be_a_tag_not_prose_or_link(self):
        for tags in ["- agent\n- Evidence is uncertain.", "- agent\n- [uncertain](https://example.org)", "- agent; the choice is uncertain", "- agent\n`- uncertain`"]:
            with self.subTest(tags=tags):
                path = self.write("question.g5.md", contract(kind="Q", tags=tags))
                self.assertIn("q-uncertain", self.codes(self.check(path)))

    def test_malformed_markers_cannot_silently_pass_as_index_pages(self):
        for marker in ["[I·example.rule]", "[I - example.rule]", "[I · ]", "[I · example.rule", "[I · example.rule] extra", "**[D · example.rule]**", "> [Q · example.rule]", "[X · example.rule]", "I · example.rule", "[I1. old format]", "[I · two words]"]:
            with self.subTest(marker=marker):
                path = self.write("bad.g5.md", f"# Rule\n\n{marker}\n\nText.\n")
                self.assertIn("block-syntax", self.codes(self.check(path)))

    def test_block_needs_matching_anchor_and_body_not_own_heading(self):
        no_heading = self.write("heading.g5.md", contract().replace("## A rule", "Introductory prose."))
        self.assert_valid(self.check(no_heading))
        for anchor in ["", '<a id="another.rule"></a>', '<!-- <a id="example.rule"></a> -->']:
            path = self.write("anchor.g5.md", contract().replace('<a id="example.rule"></a>', anchor))
            self.assertIn("block-anchor", self.codes(self.check(path)))
        empty = self.write("empty.g5.md", contract(body="<!-- empty -->"))
        self.assertIn("block-empty", self.codes(self.check(empty)))
        indented = self.write("indent.g5.md", contract().replace("[I ·", "    [I ·"))
        self.assertIn("block-syntax", self.codes(self.check(indented)))

    def test_multiple_blocks_share_section_and_keep_precise_links(self):
        first_body, first_meta = contract("first", body="See [second](#second).").split("## Metadata")
        second_body, second_meta = contract("second").split("## Metadata")
        second_body = second_body.split("## A rule\n\n", 1)[1]
        value = first_body + second_body + "## Metadata" + first_meta + second_meta
        path = self.write("root.g5.md", value)
        self.assert_valid(self.check(path))
        # The next block's anchor must not count as this block's missing body.
        path.write_text(value.replace("See [second](#second).", "<!-- empty -->"))
        self.assertEqual(self.codes(self.check(path)), ["block-empty"])

    def test_shared_metadata_summary_precedes_per_block_entries(self):
        path = self.write("root.g5.md", contract().replace("## Metadata", "## Metadata\n\nShared assessment; scoped evidence remains below."))
        self.assert_valid(self.check(path))

    def test_trailing_marker_whitespace_is_valid(self):
        path = self.write("root.g5.md", contract().replace("[I · example.rule]", "[I · example.rule]  \t"))
        self.assert_valid(self.check(path))

    def test_bad_footer_placement_or_heading(self):
        for name, value, expected in [
            ("heading", contract().replace("## Metadata", "# Metadata"), "metadata-heading"),
            ("tail", contract() + "\n## More content\n\nText.\n", "footer-position"),
            ("duplicate", contract() + "\n## Metadata\n", "metadata-duplicate"),
            ("block", contract() + "\n#### Late block\n\n[D · late]\n\nLate.\n", "block-placement"),
        ]:
            with self.subTest(name=name):
                path = self.write(name + ".md", value)
                self.assertIn(expected, self.codes(self.check(path)))

    def test_source_line_references_are_bounded(self):
        self.write("evidence.md", "# Evidence\n\nFirst source line.\nSecond source line.\n")
        path = self.write("root.g5.md", contract(body="[single](evidence.md#L3) [range](evidence.md#L1-L4)"))
        self.assert_valid(self.check(path))
        for fragment in ["L0", "L5", "L4-L2", "L1-L5"]:
            path.write_text(contract(body=f"[bad](evidence.md#{fragment})"))
            self.assertEqual(self.codes(self.check(path)), ["link-anchor"])

    def test_local_links_encoded_paths_balanced_parentheses_titles_and_images(self):
        self.write("sub/with space.md", "# Destination\n")
        self.write("sub/file(v2).md", "# Destination\n")
        (self.ontology / "image.png").write_bytes(b"fixture")
        body = "\n".join([
            '[angle](<sub/with space.md#destination> "A title")',
            "[encoded](sub/with%20space.md?ignored=yes#destination)",
            "[balanced](sub/file(v2).md#destination)",
            r"[escaped](sub/file\(v2\).md#destination 'title')",
            "![image](image.png)",
            "[external](https://example.invalid/nonexistent#fragment)",
            "[app](codex://threads/not-read)",
            "[relative external](//example.invalid/not-read)",
            "`[code sample](not-a-link.md)`",
        ])
        self.write("root.g5.md", contract(body=body))
        self.assert_valid(self.check())

    def test_reference_links_full_collapsed_shortcut_multiline_and_casefold(self):
        self.write("target.md", "# Target\n")
        body = "[full][TARGET] [collapsed][] [shortcut] [I](target.md)\n\n[target]: target.md#target \"title\"\n[collapsed]: <target.md#target>\n[shortcut]:\n  target.md#target\n"
        self.write("root.g5.md", contract(body=body))
        self.assert_valid(self.check())

    def test_single_letter_reference_definitions_and_list_links_are_not_blocks(self):
        self.write("target.md", "# Target\n")
        body = "[I]: target.md\n\n[I]\n\n- [Q](target.md)\n\n> [D](target.md)\n"
        self.write("root.g5.md", contract(body=body))
        self.assert_valid(self.check())

    def test_undefined_reference_and_malformed_links_fail(self):
        for body, expected in [
            ("[label][missing]", "link-reference"),
            ("[label](missing.md", "link-syntax"),
            ("[label](<missing.md)", "link-syntax"),
            ("[label](file(a.md)", "link-syntax"),
            ("[label]: target.md garbage", "link-syntax"),
        ]:
            with self.subTest(body=body):
                path = self.write("root.g5.md", contract(body=body))
                self.assertIn(expected, self.codes(self.check(path)))

    def test_heading_anchors_unicode_punctuation_duplicates_setext_and_html(self):
        target = "# Don't lose `IDs`: **important**!\n\n## Duplicate\n\n## Duplicate\n\n## Duplicate-1\n\nCafé déjà vu\n============\n\n<a id=\"explicit\"></a>\n\n## _Emphasis_ and __strong__\n\n## `_literal_` and `<T>`\n"
        self.write("target.md", target)
        links = ["dont-lose-ids-important", "duplicate", "duplicate-1", "duplicate-1-1", "caf%C3%A9-d%C3%A9j%C3%A0-vu", "explicit", "emphasis-and-strong", "_literal_-and-t"]
        self.write("root.g5.md", contract(body="\n".join(f"[link](target.md#{anchor})" for anchor in links)))
        self.assert_valid(self.check())

    def test_missing_file_and_anchor_report_accurate_source_lines(self):
        self.write("target.md", "# Present\n")
        path = self.write("index.md", "# Index\n\n[missing](absent.md)\n[anchor](target.md#absent)\n")
        result = self.check(path)
        self.assertEqual([(issue.line, issue.code) for issue in result.issues], [(3, "link-target"), (4, "link-anchor")])

    def test_outer_or_unmatched_prose_brackets_cannot_hide_links(self):
        for body in ["The interval starts at [a.\n\n[missing](missing.md)", "[See [missing](missing.md) for details.]"]:
            with self.subTest(body=body):
                path = self.write("root.g5.md", contract(body=body))
                self.assertEqual(self.codes(self.check(path)), ["link-target"])

    def test_linked_evidence_is_not_scanned_as_ontology(self):
        evidence = self.root / "evidence.md"
        evidence.write_text("# Evidence\n\n[I malformed example]\n", encoding="utf-8")
        self.write("root.g5.md", contract(body="[Evidence](../evidence.md#evidence)"))
        result = self.check()
        self.assert_valid(result)
        self.assertEqual(len(result.files), 1)

    def test_invalid_inputs_are_not_success(self):
        empty = self.root / "empty"
        empty.mkdir()
        for path in [empty, self.root / "missing.md"]:
            self.assertIn("input", self.codes(self.check(path)))
        source = self.root / "not-markdown.py"
        source.write_text("pass\n")
        self.assertIn("input", self.codes(self.check(source)))
        self.assertIn("input", self.codes(check_paths([])))
        self.assertIn("input", self.codes(self.check(empty, ontology_root=self.root / "missing")))

    def test_invalid_utf8_reports_input_error(self):
        (self.ontology / "bad.md").write_bytes(b"\xff")
        self.assertIn("input", self.codes(self.check()))

    def warnings(self, result, code):
        return [(issue.line, issue.message) for issue in result.warnings if issue.code == code]

    def test_sentence_cap_counts_statement_prose_together_and_each_bullet_alone(self):
        self.write("x.md", "# X\n\n## A\n")
        counted = "One e.g. this, i.e. that. Two at v1.2 and `a. b. c.` in code. Three [see this](x.md#a)."
        self.assertEqual(sentence_count("Version 1.2. One. Two. Three."), 4)
        result = self.check(self.write("root.g5.md", contract(body=counted)), self.ontology / "x.md")
        self.assert_valid(result)
        self.assertEqual(self.warnings(result, "writing-length"), [])
        body = (
            "One. Two.\n\n"
            "- One. Two. Three.\n\n  Four, in the same bullet.\n- One. Two. Three.\n\n"
            "Three. Four.\n"
        )
        result = self.check(self.write("root.g5.md", contract(body=body)))
        self.assertEqual(self.warnings(result, "writing-length"), [
            (8, "4 sentences in the statement outside its bullets; keep at most 3"),
            (10, "4 sentences in one bullet; keep at most 3"),
        ])

    def test_statement_has_at_most_ten_bullets_including_nested_ones(self):
        ten = "Rules:\n\n" + "".join(f"- Rule {n}.\n" for n in range(9)) + "  - Nested rule.\n"
        result = self.check(self.write("root.g5.md", contract(body=ten)))
        self.assertEqual(self.warnings(result, "writing-bullets"), [])
        result = self.check(self.write("root.g5.md", contract(body=ten + "- One too many.\n")))
        self.assertEqual(self.warnings(result, "writing-bullets"), [(20, "11 bullets in one statement; keep at most 10 or define a new concept with its own statements")])

    def test_sentence_cap_ignores_metadata_tables_and_intro_prose(self):
        text = "# Contract\n\nOne. Two. Three. Four.\n\n" + contract(body="| A. B. C. D. |\n|---|\n").split("\n", 1)[1]
        text = text.replace("- From the supplied requirement.", "- One. Two. Three. Four.")
        result = self.check(self.write("root.g5.md", text))
        self.assertEqual(self.warnings(result, "writing-length"), [])

    def test_provenance_in_statement_prose_is_flagged_but_not_in_metadata_or_links(self):
        cases = {
            "Fixed after issue #12.": "issue #12",
            "See PR 34 for details.": "PR 34",
            "As G5Labs/G5-Lean#56 reported.": "G5Labs/G5-Lean#56",
            "Since #78.": "#78",
            "Reported in [the tracker](https://github.com/o/r/issues/9).": "https://github.com/o/r/issues/9",
        }
        for number, (body, found) in enumerate(cases.items()):
            result = self.check(self.write(f"{number}.g5.md", contract(f"p.{number}", body=body)))
            self.assertEqual([message.split("'")[1] for _, message in self.warnings(result, "writing-provenance")], [found], body)
        clean = contract(body="See [rule](#a-rule) and [plan](plan.md#1-scope); use `#12` and `&#35;`.")
        clean = clean.replace("- From the supplied requirement.", "- Source: issue #12.")
        self.write("plan.md", "# 1 Scope\n")
        result = self.check(self.write("clean.g5.md", clean), self.ontology / "plan.md")
        self.assert_valid(result)
        self.assertEqual(self.warnings(result, "writing-provenance"), [])

    def test_each_id_level_below_the_top_name_needs_a_defining_block(self):
        text = (
            "# Page\n\n"
            '<a id="app.shop"></a>\n[I · app.shop]\n\nA shop sells goods.\n\n'
            '<a id="app.shop.cart.limit"></a>\n[I · app.shop.cart.limit]\n\nA cart holds ten items.\n\n'
            '<a id="app.old.rule"></a>\n<a id="app.rule"></a>\n[I · app.rule]\n\nA former ID is not a definition.\n\n'
            "## Metadata\n\n### app.shop\n\n- agent\n\n### app.shop.cart.limit\n\n- agent\n\n### app.rule\n\n- agent\n"
        )
        result = self.check(self.write("root.g5.md", text))
        self.assert_valid(result)
        self.assertEqual([message.split("'")[1] for _, message in self.warnings(result, "writing-id-level")], ["app.shop.cart"])

    def test_writing_warnings_do_not_change_the_exit_status(self):
        self.write("root.g5.md", contract("app.area.rule", body="One. Two. Three. Four, per issue #5."))
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        run = subprocess.run([sys.executable, str(SCRIPT), str(self.ontology)], text=True, capture_output=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("0 issue(s), 3 writing warning(s)", run.stdout)
        for code in ("writing-length", "writing-provenance", "writing-id-level"):
            self.assertIn(f"warning: {self.ontology / 'root.g5.md'}", run.stderr)
            self.assertIn(code, run.stderr)

    def test_cli_reports_limits_exit_codes_and_is_read_only(self):
        path = self.write("root.g5.md", contract())
        before = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        good = subprocess.run([sys.executable, str(SCRIPT), str(self.ontology)], text=True, capture_output=True, env=env)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("Mechanical", good.stdout)
        self.assertIn("no claim about intent", good.stdout)
        after = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        path.write_text(contract(kind="Q"), encoding="utf-8")
        bad = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True, env=env)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("q-uncertain", bad.stderr)
        invalid = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "absent")], text=True, capture_output=True, env=env)
        self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
