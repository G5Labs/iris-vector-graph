#!/usr/bin/env python3
"""Reproducibility guard (review R5-01): no file under experiment/playbook-completion may be git-ignored, because an
ignored file is invisible to `git status` (verify.sh's worktree_status_lines) and absent from a clean checkout, while
cells, findings or checkers may cite it. Byte-code caches are the only exception.

    python tools/ignored_check.py              # exit 1 and list the ignored files
    python tools/ignored_check.py --self-test  # a seeded ignored file must be reported
"""
import subprocess
import sys
import tempfile
from pathlib import Path

PC = Path(__file__).resolve().parents[1]
REPO = PC.parents[1]
ALLOW = ("__pycache__/", ".pyc")


def ignored(paths=None):
    out = subprocess.run(["git", "-C", str(REPO), "status", "--ignored", "--porcelain", "--untracked-files=all",
                          *(paths or [str(PC.relative_to(REPO))])], capture_output=True, text=True).stdout
    return [l[3:] for l in out.splitlines() if l.startswith("!! ") and not any(a in l for a in ALLOW)]


def main():
    if "--self-test" in sys.argv:
        with tempfile.NamedTemporaryFile(dir=PC, prefix="coverage-selftest-", suffix=".json", delete=True) as f:
            got = ignored([str(Path(f.name).relative_to(REPO))])
        ok = len(got) == 1
        print("self-test", "pass" if ok else "FAIL", got)
        return 0 if ok else 1
    got = ignored()
    for g in got:
        print("ignored:", g)
    print(f"ignored files under the completion directory: {len(got)}")
    return 1 if got else 0


if __name__ == "__main__":
    sys.exit(main())
