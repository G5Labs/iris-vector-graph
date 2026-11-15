"""Replay unchanged frozen binding with an audited legacy artifact-root alias.

Only old native receipt absolute paths need rebasing for relative input labels.
No product, model, oracle, provider result or deciding binding code is changed.
"""
import hashlib
import importlib.util
import json
import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[4]
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path(json.loads((HERE / "ppr-review-frozen-start.json").read_text())["scratch"])
BINDING = SCRATCH / ".g5/Verus_verification/models/ppr_walk/binding.py"
old_relative_to = pathlib.PurePath.relative_to
aliases = []


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def artifact_relative_to(self, *other):
    try:
        return old_relative_to(self, *other)
    except ValueError:
        if len(other) != 1 or pathlib.Path(other[0]) != SCRATCH or not self.is_absolute():
            raise
        relative = old_relative_to(self, ROOT)
        copied = SCRATCH / relative
        assert copied.is_file() and sha(self) == sha(copied), (self, "legacy artifact alias differs")
        aliases.append({"original": str(self), "copied": str(copied), "sha256": sha(self)})
        return relative


spec = importlib.util.spec_from_file_location("ppr_independent_frozen_binding", BINDING)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)
with patch.object(pathlib.PurePath, "relative_to", artifact_relative_to):
    code = binding.main()
metadata = {
    "exit_code": code,
    "binding_sha256": sha(BINDING),
    "wrapper_sha256": sha(__file__),
    "legacy_artifact_aliases": aliases,
    "scope": "Unchanged frozen binding replay; only absolute legacy native-fact input labels rebased after byte equality checks. No native calls or product/oracle/deciding-code mutation.",
    "initial_attempt": "All core journeys ran, then native reverse5 absolute path relative_to scratch raised ValueError; no pass receipt emitted. This wrapper resolves only that artifact portability boundary.",
}
(HERE / "ppr-review-binding-adapter.json").write_text(json.dumps(metadata, indent=2) + "\n")
raise SystemExit(code)
