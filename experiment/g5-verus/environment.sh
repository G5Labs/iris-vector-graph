# Source on the experiment VM from this worktree before starting Claude.
export RUN_DIR="$HOME/runs/iris-vector-graph-g5-verus-20261113"
export WORK_DIR="$HOME/experiments/iris-vector-graph-g5-verus-20261113/iris-vector-graph"
source "$HOME/.config/g5-verification/env.sh"
export VERUS_BIN="$G5_VERUS_TWENTY/verus"
export VIRTUAL_ENV="$RUN_DIR/venv" UV_PROJECT_ENVIRONMENT="$RUN_DIR/venv"
export UV_CACHE_DIR="$RUN_DIR/cache/uv" CARGO_TARGET_DIR="$RUN_DIR/cargo-target"
export PATH="$VIRTUAL_ENV/bin:$RUN_DIR/tools:$G5_VERUS_TWENTY:$HOME/.local/bin:$PATH"
export IVG_TEST_CONTAINER=ivg-g5-verus-20261113-iris IVG_PORT=35972 IVG_NAMESPACE=USER
export IVG_AUTO_START_CONTAINER=0 SKIP_IRIS_TESTS=false COMPOSE_PROJECT_NAME=ivg_g5_verus_20261113
export DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
# Run the upstream live redaction cases with the product's Community Edition schema initializer:
# python experiment/g5-verus/run-community-redaction.py
