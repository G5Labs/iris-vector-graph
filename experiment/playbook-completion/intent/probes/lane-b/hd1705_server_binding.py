"""HD-1705 probe (no IRIS, no network): does `ivg server start` refuse to listen on every address without a key?

`uvicorn` is replaced in this process by a recorder, so nothing listens; the click command is invoked in-process
with IVG_API_KEY unset.

Stated contracts disagree:
  deploy/README.md:86  "The server refuses `auth: none` with `host: 0.0.0.0` unless `--force-no-auth` is passed."
  docs/ADMIN_GUIDE.md:828 "Unset, the server asks for no key at all, and it listens on every interface (0.0.0.0:8200)."
Oracle used for the result: deploy/README.md:86 (the refusal). A start that reaches uvicorn.run on 0.0.0.0 with no
key, and a `--force-no-auth` option that does not exist, violate it (and agree with ADMIN_GUIDE section 5).
"""
import os
import sys
import types

os.environ.pop("IVG_API_KEY", None)
calls = []
fake = types.ModuleType("uvicorn")
fake.run = lambda app, **kw: calls.append(kw)
sys.modules["uvicorn"] = fake

from click.testing import CliRunner  # noqa: E402

from iris_vector_graph import cli as ivg_cli  # noqa: E402
from iris_vector_graph._api_key import configured_key  # noqa: E402

runner = CliRunner()
start = ivg_cli.cli.commands["server"].commands["start"]
opts = {p.name: (p.default, p.opts) for p in start.params}
print(f"server start options: { {k: v[0] for k, v in opts.items()} }")
print(f"--force-no-auth declared: {any('--force-no-auth' in v[1] for v in opts.values())}")

r1 = runner.invoke(ivg_cli.cli, ["server", "start"], env={"IVG_API_KEY": ""})
print(f"start, no key, default host: exit={r1.exit_code} uvicorn.run called with={calls[-1] if calls else None} "
      f"configured_key={configured_key()!r} output={r1.output.strip()[:120]!r}")
n_calls = len(calls)
r2 = runner.invoke(ivg_cli.cli, ["server", "start", "--force-no-auth"], env={"IVG_API_KEY": ""})
print(f"start --force-no-auth: exit={r2.exit_code} uvicorn_called_again={len(calls) > n_calls} "
      f"output={r2.output.strip().splitlines()[-1] if r2.output.strip() else ''!r}")

refused = r1.exit_code != 0 and n_calls == 0
listened_open = n_calls == 1 and calls[0].get("host") == "0.0.0.0"
print(f"ORACLE deploy/README.md:86 (refuse no-auth on 0.0.0.0 unless --force-no-auth): refused={refused}")
print(f"ADMIN_GUIDE.md:828 (open on 0.0.0.0:8200 with no key): matches={listened_open and calls[0].get('port') == 8200}")
print("OUTCOME:", "pass" if refused else "fail (deploy/README.md:86 refusal not implemented; behaviour is ADMIN_GUIDE section 5's)")
