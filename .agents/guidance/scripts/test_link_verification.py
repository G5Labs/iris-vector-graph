#!/usr/bin/env python3
"""Regressions for link_verification.py on small synthetic ontology/TLA trees."""

from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest

from link_verification import main


def statement(sid, body="The rule holds.", aliases=()):
    anchors = "".join(f'<a id="{a}"></a>\n' for a in aliases)
    return f'{anchors}<a id="{sid}"></a>\n[I · {sid}]\n\n{body}\n'


def page(statements, entries):
    return "# Page\n\n" + "\n".join(statements) + "\n## Metadata\n\n" + "\n".join(entries)


class LinkVerification(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / ".g5"
        self.ontology = self.root / "ontology"
        self.verification = self.root / "TLA_verification"
        (self.ontology / "features").mkdir(parents=True)
        (self.verification / "models").mkdir(parents=True)
        (self.verification / "results").mkdir()

    def write(self, relative, content):
        path = self.ontology / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def concern(self, name, ids, runs=True, title=None, receipt=False, manifest_text=None):
        folder = self.verification / "models" / name
        folder.mkdir()
        manifest = {"concern": name, "question": "Does it hold?", "ontology_ids": ids, "runs": []}
        if title:
            manifest["title"] = title
        (folder / "manifest.json").write_text(manifest_text or json.dumps(manifest), encoding="utf-8")
        (folder / "BINDINGS.md").write_text("# Bindings\n", encoding="utf-8")
        if runs:
            with (self.verification / "results" / "index.jsonl").open("a", encoding="utf-8") as index:
                index.write(json.dumps({"run_id": f"20261025T000000Z-{name}", "concern": name, "label": "safety", "outcome": "PASS"}) + "\n")
        if receipt:
            run = self.verification / "results" / name / "20261025T000000Z-x"
            run.mkdir(parents=True)
            (run / "receipt.json").write_text("{}", encoding="utf-8")

    def run_tool(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([*extra, str(self.ontology)])
        return code, out.getvalue()

    def test_links_tags_and_is_idempotent(self):
        path = self.write(
            "features/receiving.g5.md",
            page(
                [statement("receipt.number"), statement("receipt.draft")],
                ["### receipt.number\n\nDerivation: from the guide.\n- agent\n\nSources: guide.\n", "### receipt.draft\n\n- agent\n"],
            ),
        )
        self.concern("receiving-numbering", ["receipt.number"])
        code, out = self.run_tool("--dry-run")
        self.assertEqual(code, 1, out)
        self.assertNotIn("design-verified", path.read_text())
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)
        text = path.read_text()
        self.assertIn(
            "### receipt.number\n\nDerivation: from the guide.\n- agent\n- design-verified\n\nSources: guide.\n\n"
            "State machines: [Receiving numbering](../../TLA_verification/models/receiving-numbering/manifest.json)\n",
            text,
        )
        self.assertNotIn("design-verified", text.split("### receipt.draft")[1])
        code, out = self.run_tool("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(path.read_text(), text)

    def test_alias_and_unknown_ids(self):
        path = self.write(
            "root.g5.md",
            page([statement("receipt.number.suggestion", aliases=["receipt-suggestion"])], ["### receipt.number.suggestion\n\n- agent\n"]),
        )
        self.concern("numbering", ["receipt-suggestion", "receipt-missing"], title="Receiving numbering")
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("unknown ontology ID 'receipt-missing'", out)
        self.assertIn("State machines: [Receiving numbering](../TLA_verification/models/numbering/manifest.json)", path.read_text())

    def test_existing_link_in_another_form_counts(self):
        path = self.write(
            "features/a.g5.md",
            page([statement("a.rule")], ["### a.rule\n\n- human-provided\n- See [bindings](../../TLA_verification/models/a-machine/BINDINGS.md).\n"]),
        )
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        text = path.read_text()
        self.assertNotIn("State machines:", text)
        self.assertIn("- human-provided\n- design-verified\n- See [bindings]", text)

    def test_link_without_recorded_run_is_not_tagged(self):
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent\n"]))
        self.concern("a-machine", ["a.rule"], runs=False)
        self.run_tool()
        text = path.read_text()
        self.assertIn("State machines:", text)
        self.assertNotIn("design-verified", text)

    def test_only_a_complete_index_row_for_the_folder_is_a_recorded_run(self):
        # The viewer's test: a receipt alone, a row without a label, or a row
        # naming the manifest's own `concern` rather than the folder are not runs.
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent\n"]))
        self.concern("a-machine", ["a.rule"], runs=False, receipt=True)
        with (self.verification / "results" / "index.jsonl").open("a", encoding="utf-8") as index:
            index.write(json.dumps({"concern": "a-machine", "outcome": "PASS"}) + "\n")
            index.write(json.dumps({"concern": "renamed", "label": "safety", "outcome": "PASS"}) + "\n")
        code, out = self.run_tool()
        self.assertNotIn("design-verified", path.read_text())
        self.assertIn("1 run index row(s) without concern, label and outcome ignored", out)

    def test_weaker_tag_replaced_and_implementation_kept(self):
        path = self.write(
            "features/a.g5.md",
            page(
                [statement("a.weak"), statement("a.strong")],
                ["### a.weak\n\n- agent\n- test-coverage\n", "### a.strong\n\n- agent\n- implementation-verified\n"],
            ),
        )
        self.concern("a-machine", ["a.weak", "a.strong"])
        code, out = self.run_tool()
        text = path.read_text()
        self.assertIn("### a.weak\n\n- agent\n- design-verified\n", text)
        self.assertNotIn("test-coverage", text)
        self.assertIn("### a.strong\n\n- agent\n- implementation-verified\n", text)
        self.assertIn("Replaced test-coverage with design-verified: a.weak", out)
        self.assertIn("kept implementation-verified", out)

    def test_unrecognized_tag_bullet_is_reported_and_left(self):
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent.\n- implementation-verified.\n"]))
        self.concern("a-machine", ["a.rule"])
        code, out = self.run_tool()
        self.assertIn("unrecognized tag bullet '- implementation-verified.'", out)
        self.assertIn("- agent.\n- implementation-verified.\n\nState machines:", path.read_text())
        self.assertNotIn("- design-verified", path.read_text())

    def test_conflicting_tags_are_reported_and_left(self):
        path = self.write(
            "features/a.g5.md",
            page(
                [statement("a.two"), statement("a.mixed")],
                ["### a.two\n\n- agent\n- test-coverage\n- manual-check-review\n", "### a.mixed\n\n- agent\n- design-verified\n- test-coverage\n"],
            ),
        )
        self.concern("a-machine", ["a.two", "a.mixed"])
        code, out = self.run_tool()
        text = path.read_text()
        self.assertIn("### a.two\n\n- agent\n- test-coverage\n- manual-check-review\n", text)
        self.assertIn("### a.mixed\n\n- agent\n- design-verified\n- test-coverage\n", text)
        self.assertIn("a.two: more than one verification tag", out)
        self.assertIn("a.mixed: more than one verification tag", out)

    def test_folder_names_with_spaces_are_linked_once(self):
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent\n"]))
        self.concern("a machine", ["a.rule"])
        self.run_tool()
        text = path.read_text()
        self.assertIn("State machines: [A machine](../../TLA_verification/models/a%20machine/manifest.json)\n", text)
        self.assertIn("- design-verified", text)
        code, out = self.run_tool("--dry-run")
        self.assertEqual(code, 0, out)

    def test_links_in_code_examples_do_not_count(self):
        path = self.write(
            "features/a.g5.md",
            page([statement("a.rule")], ["### a.rule\n\n- agent\n\n```markdown\n[x](../../TLA_verification/models/a-machine/manifest.json)\n```\n\nOr `[y](../../TLA_verification/models/a-machine/BINDINGS.md)`.\n"]),
        )
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        text = path.read_text()
        self.assertIn("State machines: [A machine]", text)
        self.assertIn("- agent\n- design-verified\n", text)

    def test_link_written_from_the_repository_root_counts(self):
        path = self.write(
            "features/a.g5.md",
            page([statement("a.rule")], ["### a.rule\n\n- agent\n\nModel: [m](.g5/TLA_verification/models/a-machine/manifest.json)\n"]),
        )
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        text = path.read_text()
        self.assertNotIn("State machines:", text)
        self.assertIn("- design-verified", text)

    def test_unreadable_manifest_still_counts_as_found(self):
        path = self.write(
            "features/a.g5.md",
            page([statement("a.rule")], ["### a.rule\n\n- agent\n\nState machines: [A](../../TLA_verification/models/a-machine/manifest.json)\n"]),
        )
        self.concern("a-machine", [], manifest_text="{not json")
        code, out = self.run_tool()
        self.assertIn("unreadable manifest", out)
        self.assertIn("- design-verified", path.read_text())

    def test_continuation_lines_stay_with_their_bullet(self):
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent, from the guide\nand the code\n\nSource: x.\n"]))
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        self.assertIn("- agent, from the guide\nand the code\n- design-verified\n", path.read_text())

    def test_mixed_line_endings_keep_each_line_ending(self):
        path = self.ontology / "features/a.g5.md"
        text = page([statement("a.rule")], ["### a.rule\n\n- agent\n"]).replace("\n", "\r\n", 3)
        path.write_bytes(text.encode())
        self.concern("a-machine", ["a.rule"])
        code, out = self.run_tool()
        self.assertNotIn("unknown ontology ID", out)
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"# Page\r\n\r\n<a id"), data[:40])
        self.assertIn(b"- agent\n- design-verified\n", data)

    def test_non_utf8_input_is_an_input_error(self):
        (self.ontology / "features/a.g5.md").write_bytes(b"# Page\n\xff\n")
        self.concern("a-machine", [])
        code, _ = self.run_tool()
        self.assertEqual(code, 2)

    def test_a_symlinked_file_stays_a_link(self):
        real = self.root / "shared" / "a.g5.md"
        real.parent.mkdir()
        real.write_text(page([statement("a.rule")], ["### a.rule\n\n- agent\n"]), encoding="utf-8")
        link = self.ontology / "features/a.g5.md"
        link.symlink_to(real)
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        self.assertTrue(link.is_symlink())
        self.assertIn("- design-verified", real.read_text())

    def test_entry_without_provenance_bullet(self):
        path = self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\nSource: the guide.\n"]))
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        self.assertIn("### a.rule\n\n- design-verified\n\nSource: the guide.\n", path.read_text())

    def test_existing_state_machines_line_is_extended(self):
        path = self.write(
            "features/a.g5.md",
            page([statement("a.rule")], ["### a.rule\n\n- agent\n\nState machines: [One](../../TLA_verification/models/one/manifest.json)\n"]),
        )
        self.concern("one", ["a.rule"])
        self.concern("two", ["a.rule"])
        self.run_tool()
        self.assertIn(
            "State machines: [One](../../TLA_verification/models/one/manifest.json); [Two](../../TLA_verification/models/two/manifest.json)\n",
            path.read_text(),
        )

    def test_duplicates_and_fenced_examples_are_not_statements(self):
        self.write("features/a.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent\n"]))
        self.write("features/b.g5.md", page([statement("a.rule")], ["### a.rule\n\n- agent\n"]))
        example = "```markdown\n" + statement("fenced.rule") + "```\n"
        fenced = self.write("features/c.g5.md", "# C\n\n" + example + "\n## Metadata\n")
        self.concern("a-machine", ["a.rule", "fenced.rule"])
        code, out = self.run_tool()
        self.assertIn("duplicate statement ID 'a.rule'", out)
        self.assertIn("unknown ontology ID 'fenced.rule'", out)
        self.assertNotIn("design-verified", (self.ontology / "features/a.g5.md").read_text())
        self.assertNotIn("State machines", fenced.read_text())

    def test_crlf_files_keep_their_line_endings(self):
        path = self.ontology / "features/a.g5.md"
        path.write_bytes(page([statement("a.rule")], ["### a.rule\n\n- agent\n"]).replace("\n", "\r\n").encode())
        self.concern("a-machine", ["a.rule"])
        self.run_tool()
        data = path.read_bytes()
        self.assertIn(b"- agent\r\n- design-verified\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_missing_models_folder_is_an_error(self):
        (self.verification / "models").rmdir()
        code, _ = self.run_tool()
        self.assertEqual(code, 2)

if __name__ == "__main__":
    unittest.main()
