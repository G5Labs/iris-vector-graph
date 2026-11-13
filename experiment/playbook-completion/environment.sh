# Source from bash on the experiment VM before opening Claude Code.
ivg_experiment_id=iris-vector-graph-playbook-uplift-20261113
export IVG_BASE_RUN="$HOME/runs/$ivg_experiment_id/playbook"
source "$IVG_BASE_RUN/environment.sh"
export IVG_EXPERIMENT="$HOME/experiments/$ivg_experiment_id"
export WORK_DIR="$IVG_EXPERIMENT/iris-vector-graph-completion"
export RUN_DIR="$HOME/runs/$ivg_experiment_id/completion"
export IVG_REFERENCES="$IVG_EXPERIMENT/post-run-references"
mkdir -p "$RUN_DIR"
if ! cmp -s "$IVG_BASE_RUN/run-community-redaction.py" "$RUN_DIR/run-community-redaction.py"; then
    cp "$IVG_BASE_RUN/run-community-redaction.py" "$RUN_DIR/run-community-redaction.py"
fi
cd "$WORK_DIR"
