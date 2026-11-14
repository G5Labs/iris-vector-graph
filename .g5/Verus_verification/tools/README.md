# Tools

- `make_findings_index.py` regenerates [findings.md](../findings.md) from the three register files (counts, High list, ranked simplifications and questions). Run from the repository root: `python3 .g5/Verus_verification/tools/make_findings_index.py`.
- `check_evidence.py` is the foundation's freshness gate: it checks every model's latest prove receipt and the latest receipt of each control named in its `model.json` against the current input files and expected verdicts, and every native observation under `receipts/native/` against its recorded probe, helper and harness hashes. Exit 0 = fresh. To exercise it, edit any probe or model file in a scratch copy of the repository and require a STALE line and exit 1.
