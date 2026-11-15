# rel_prop_text — notes

Consolidated uplift, 2026-11-14. Product baseline `3eaa79cf`. Root [rel_prop_text.rs](rel_prop_text.rs); controls in [model.json](model.json); binding [binding.py](binding.py). Public case M18. Owner block: [query.values.relationship_text](../../../ontology/features/cypher.g5.md#query.values.relationship_text). Neither prior arm modeled this decoder.

Two decoders are modeled. `decode` is the **reviewed rule** (the decoder's docstring: canonical integer and decimal text over ASCII digits). `as_built` transcribes Python's `re.match` semantics for the two patterns at `prop_values.py:90-91`: `\d` also matches non-ASCII decimal digits, and `$` also matches before one final line break.

## Theorems

| Claim | Theorem | Design |
|---|---|---|
| the classes: `true`/`false` booleans, canonical integer, canonical decimal, list or map, `True` stays text | `theorem_decode_classes` | reviewed |
| any character outside `[0-9.-]` (plus sign, exponent, space, line break, non-ASCII digit) or a leading zero keeps the text | `theorem_noncanonical_stays_text` | reviewed |
| the as-built decoder equals the reviewed rule on every ASCII text not ending in a line break | `theorem_as_built_agrees_on_plain_ascii` | both |
| as built, `"12\n"` reads as an integer | `witness_as_built_trailing_newline_promoted` | as-built |
| as built, `"1٢"` reads as an integer | `witness_as_built_unicode_digit_promoted` | as-built |

Expected: 10 verified, 0 errors; 5 controls EXPECTED_FAIL: `leading-zero-canonical`, `sign-plus-canonical`, `legacy-bool-spellings` (reviewed rule), and `as-built-without-final-newline-match`, `as-built-ascii-digits`, which apply the repaired pattern (`\Z`, `re.ASCII`) to the as-built decoder and make the corresponding witness fail. Those two controls show that the departure comes from exactly those two pattern features.

## Bindings

| Model | Product (pin) | Grade |
|---|---|---|
| `as_built` | `iris_vector_graph/prop_values.py::parse_rel_prop_text` :141-168 with `::parse_prop_text` :129-138, `::decode_json_list_map` :234-248, `_CANONICAL_INT_RE` / `_CANONICAL_FLOAT_RE` :90-91 | Observed (binding) |
| column choice and arity guard (not in the Verus model) | `iris_vector_graph/_engine/query.py::_decode_rel_prop_text_columns` :1200-1216 | Observed (binding, 4 cases) |
| which columns are marked | `iris_vector_graph/cypher/translator.py::_rel_prop_text_columns` :7517-7556 | Inspected |

Binding: every text of length 0-3 over `{0, 1, 2, -, +, ., e, space, line break, U+0662}` plus 28 named cases (1,139 texts): the real decoder's class equals the `as_built` transcription on every one (0 mismatches). Against the reviewed rule it departs on 38 texts, every one containing a line break or U+0662. Detected: a changed observation, and a decoder with the repaired pattern.

## Premises and limits

- Values are classified, not computed: the numeric value of a canonical text (`int()`/`float()` of ASCII digits) is not modeled. `"-0"` is canonical by the pattern and becomes the integer 0.
- Whether IRIS's `JSON_VALUE` returns a stored line break or non-ASCII digit unchanged is **not observed** here (no IRIS); the end-to-end reachability of bug-cyp-101 through a Cypher `RETURN r.p` is therefore Suspected. The documented known issue (`docs/KNOWN_ISSUES.md`, "A Cypher-written relationship number is stored as JSON text") is related: canonical number text written as a string reads back as a number by design; this finding is about text that is not canonical.
- Trust inventory: none; bundled `vstd` only.
