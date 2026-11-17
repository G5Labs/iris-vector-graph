"""Run a model binding.py against the local fixture: install local-runtime/runtime.py as `runtime`, then exec the binding.

Usage: python -B run_binding.py <models/<m>/binding.py> [args...]
The binding's own argv follows. The local module is the only `runtime` importable here; the cloud iteration-36 module is
not on sys.path. Prints the fixture identity first so the log records which database ran.
"""
import importlib.util
import json
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("runtime", HERE / "runtime.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)
sys.modules["runtime"] = rt
target = Path(sys.argv[1]).resolve()
sys.argv = [str(target)] + sys.argv[2:]
print(json.dumps({"runtime": str(HERE / "runtime.py"), "fixture": rt.FIXTURE}), flush=True)
runpy.run_path(str(target), run_name="__main__")
