#!/usr/bin/env bash
# Check the committed, staged and unstaged inputs independently. Also detect
# untracked nonignored product files. A submodule must match its pinned gitlink.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
pin=3eaa79cf77d3e0a879b2cced634cf2729d81499e
paths=(. ':(exclude)experiment/**')
git diff --no-ext-diff --ignore-submodules=none --exit-code "$pin" HEAD -- "${paths[@]}"
git diff --no-ext-diff --ignore-submodules=none --cached --exit-code "$pin" -- "${paths[@]}"
git diff --no-ext-diff --ignore-submodules=none --exit-code -- "${paths[@]}"
if [[ -n "$(git ls-files --others --exclude-standard -- "${paths[@]}")" ]]; then
    echo "Untracked files outside the experiment" >&2
    git ls-files --others --exclude-standard -- "${paths[@]}" >&2
    exit 1
fi
echo "Product matches $pin in HEAD, index and worktree."
