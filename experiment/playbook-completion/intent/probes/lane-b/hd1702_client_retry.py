"""HD-1702 probe (no IRIS): does IVGClient resend a write query after an ambiguous outcome?

A local stub HTTP server on 127.0.0.1 (ephemeral port, stopped at the end) stands in for `ivg server`. Each POST
/api/cypher is counted as one execution (the stub "commits" before it answers), so the count is the number of times
the server would have run the statement.

Oracle (working assumption, not a stated contract): after an ambiguous outcome (5xx after the server ran the
statement, or a read timeout) the client must not resend a write unless it is known idempotent. The stated
behaviour is the opposite: IVGServerError says "a 5xx status on the last retry", IVGClientError "every retry failed
to connect or timed out" (sdk.py docstrings, docs/API_REFERENCE.md), commit aaa54a44 "Retry on 5xx".
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from iris_vector_graph import IVGClient, IVGClientError, IVGServerError

MODE = {"name": "", "count": 0, "bodies": []}
LOCK = threading.Lock()


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        with LOCK:
            MODE["count"] += 1
            k = MODE["count"]
            MODE["bodies"].append(json.loads(body)["query"])
        mode = MODE["name"]
        if mode == "always500":
            code, payload = 500, b"internal"
        elif mode == "commit_then_502_once":
            code, payload = (502, b"bad gateway") if k == 1 else (200, None)
        elif mode == "slow_commit":
            time.sleep(1.2)  # the statement "committed"; the answer arrives after the client's timeout
            code, payload = 200, None
        else:
            code, payload = 200, None
        if payload is None:
            payload = json.dumps({"status": "OK", "columns": ["n"], "rows": [[k]]}).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
port = srv.server_address[1]
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
results = {}
try:
    for mode, query in [("always500", "CREATE (n:ib2_P {id: 'x'})"),
                        ("always500", "MATCH (n) RETURN count(n)"),
                        ("commit_then_502_once", "CREATE (n:ib2_P {id: 'y'})"),
                        ("slow_commit", "CREATE (n:ib2_P {id: 'z'})")]:
        MODE.update(name=mode, count=0, bodies=[])
        client = IVGClient(f"http://127.0.0.1:{port}", timeout=0.5, max_retries=3)
        outcome = "returned"
        try:
            r = client.execute_cypher(query)
            outcome = f"returned rows={r.rows}"
        except IVGServerError as e:
            outcome = f"IVGServerError http_code={e.http_code}"
        except IVGClientError as e:
            outcome = f"IVGClientError {str(e)[:80]}"
        finally:
            client.close()
        time.sleep(1.5)  # let a slow handler finish counting
        results[(mode, query)] = (MODE["count"], outcome)
        print(f"mode={mode:22s} query={query!r:32s} server_executions={MODE['count']} client_outcome={outcome}")
finally:
    srv.shutdown()
    srv.server_close()

writes_resent = [k for k, v in results.items() if k[1].startswith("CREATE") and v[0] > 1]
silent_dup = results[("commit_then_502_once", "CREATE (n:ib2_P {id: 'y'})")]
print(f"ORACLE (working assumption) no resend of a write after an ambiguous outcome: writes resent in {len(writes_resent)} of 3 write cases")
print(f"silent duplicate: commit_then_502_once -> {silent_dup[0]} executions and the caller saw: {silent_dup[1]}")
print("read and write treated alike:", results[("always500", "CREATE (n:ib2_P {id: 'x'})")][0] == results[("always500", "MATCH (n) RETURN count(n)")][0])
print("OUTCOME:", "pass" if not writes_resent else "expected-violation (writes resent; documented retry behaviour)")
