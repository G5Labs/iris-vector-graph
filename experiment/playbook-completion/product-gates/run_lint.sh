#!/usr/bin/env bash
# Gate 3.5-lint (IVG counterpart of "zero default lint warnings"): run the product's OWN configured linters on the
# unchanged pin, read in place, every output and cache under OUT (never in the tree).
#
#   source experiment/playbook-completion/environment.sh
#   bash experiment/playbook-completion/product-gates/run_lint.sh $RUN_DIR/product-gates/lint-rN
#
# Tools and why each is "the product's own" (pin 3eaa79cf):
#   ruff check .           CONTRIBUTING.md:36-39 ("Lint before you commit: ruff check . && black . && isort ."),
#                          PRE_RELEASE_CHECKLIST.md:139-146 (§5: "`ruff check .` - zero errors"). No [tool.ruff] and no
#                          ruff pin anywhere: run with ruff 0.15.14 (the version the product last recorded,
#                          specs/release-4.6.0/known-issues-triage.md:193) and, separately, with the newest ruff the
#                          index served on the audit date ($RUFF_CURRENT), whose default rule set is larger.
#   black ., isort .       CONTRIBUTING.md:39; configured in pyproject.toml [tool.black] / [tool.isort]; versions from
#                          uv.lock (dev extra). Run in check mode (--check / --check-only): nothing is rewritten.
#   flake8                 dev extra (pyproject.toml), uv.lock 7.3.0; no configuration file at the pin (defaults).
#   mypy                   dev extra, uv.lock 2.1.0, configured in pyproject.toml [tool.mypy]; the pin documents no
#                          target (no `files`), so the shipped package iris_vector_graph is checked (audit choice).
#   markdownlint-cli2,     .markdownlint-cli2.jsonc; PRE_RELEASE_CHECKLIST.md:217 (§8c hygiene). Unpinned: newest
#   prettier --check       versions on the audit date, on every tracked .md of the pin.
#   ObjectScript           no linter configured; PRE_RELEASE_CHECKLIST.md:150-156 (§6) is a compile gate, observed
#                          only through the pin's deploy path (deploy-AUDITIA.json), not rerun here.
#
# experiment/ is excluded from every discovery: it is not part of the pin's tree (git ls-tree 3eaa79cf has no
# experiment/). Discovery is otherwise each tool's own (pyproject excludes, .gitignore).
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
OUT="${1:?output directory}"
PG="$RUN_DIR/product-gates"
V="$PG/venv/bin"                       # uv.lock versions (uv export --frozen --extra dev --extra full)
R15="$PG/venv-ruff-0.15.14/bin/ruff"   # ruff 0.15.14
RCUR="$V/ruff"                         # newest ruff on the audit date
MD="$PG/mdtools/node_modules/.bin"
export PATH="$PG/node/bin:$PATH"
mkdir -p "$OUT"
cd "$WORK_DIR"
bash experiment/playbook-completion/check-product-scope.sh > "$OUT/scope-before.txt" 2>&1 || { echo "product differs from pin"; exit 2; }

{
  echo "date_utc: $(date -u +%FT%TZ)"
  echo "python: $($V/python --version 2>&1)"
  echo "ruff_pinned_by_product: none (no [tool.ruff], not in uv.lock)"
  echo "ruff_0.15.14: $($R15 --version)"
  echo "ruff_current: $($RCUR --version)"
  echo "black: $($V/black --version | head -1)"
  echo "isort: $($V/isort --version-number)"
  echo "flake8: $($V/flake8 --version | tr '\n' ' ')"
  echo "mypy: $($V/mypy --version)"
  echo "node: $(node --version)"
  echo "markdownlint-cli2: $($MD/markdownlint-cli2 --version 2>&1 | head -1)"
  echo "prettier: $($MD/prettier --version)"
} > "$OUT/versions.txt"

run() {  # name, command...
  local name="$1"; shift
  printf '%s\n' "$*" > "$OUT/$name.cmd"
  "$@" > "$OUT/$name.out" 2> "$OUT/$name.err"
  echo $? > "$OUT/$name.rc"
}

run ruff-0.15.14 "$R15" check . --no-cache --extend-exclude experiment --output-format json
run ruff-0.15.14-statistics "$R15" check . --no-cache --extend-exclude experiment --statistics
run ruff-current "$RCUR" check . --no-cache --extend-exclude experiment --output-format json
run ruff-current-statistics "$RCUR" check . --no-cache --extend-exclude experiment --statistics
# black: the pyproject extend-exclude regex plus ^/experiment/ (a CLI --extend-exclude replaces the config's)
export BLACK_CACHE_DIR="$OUT/black-cache"
run black "$V/black" --check . --extend-exclude '(/(\.eggs|\.git|\.hg|\.mypy_cache|\.tox|\.venv|_build|buck-out|build|dist)/|^/experiment/)'
run isort "$V/isort" --check-only --extend-skip experiment .
run flake8 "$V/flake8" --extend-exclude experiment --format='%(path)s:%(row)d:%(col)d:%(code)s:%(text)s' .
run mypy timeout 1800 "$V/mypy" iris_vector_graph --cache-dir "$OUT/mypy-cache" --show-error-codes
git ls-files -- '*.md' ':(exclude)experiment/**' > "$OUT/md-files.txt"
# shellcheck disable=SC2046
run markdownlint "$MD/markdownlint-cli2" $(cat "$OUT/md-files.txt")
# shellcheck disable=SC2046
run prettier "$MD/prettier" --check $(cat "$OUT/md-files.txt")

bash experiment/playbook-completion/check-product-scope.sh > "$OUT/scope-after.txt" 2>&1 || { echo "product changed during the run"; exit 3; }
"$V/python" -I "$WORK_DIR/experiment/playbook-completion/product-gates/lint_summary.py" "$OUT" "$WORK_DIR" > "$OUT/summary.txt"
cat "$OUT/summary.txt"
