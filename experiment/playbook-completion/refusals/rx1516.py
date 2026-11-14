"""Helpers for the refusals lane's module 15 and 16 probes (test instruments only; nothing of the product changes).

- Listener: a local TCP listener this process owns, recording every connection it gets; modes 'http500' (answers
  HTTP 500), 'silent' (accepts and never answers), 'record' (answers HTTP 200 with an empty body).
- hidden_modules(): makes `import rdflib` / `import pyshacl` fail in this process only (the dependency absent).
- fake_rdflib8(): `rdflib` replaced, in this process only, by a module that is the installed rdflib minus
  ConjunctiveGraph with __version__ '8.0.0' (the case KNOWN_ISSUES and F-1506 describe).
- Spy: counts an engine's Native API and FHIR server calls (wrappers on the instance that delegate unchanged), so
  a probe can show a refusal came before IVG reached IRIS.
- Bolt: a minimal raw Bolt client (handshake, chunking, PackStream for the messages used), so a probe can send what
  a driver never sends (RUN before HELLO, a second LOGON, RESET after a refusal).
"""
from __future__ import annotations

import builtins
import contextlib
import socket
import struct
import sys
import threading
import types
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------------------------------------ listener
class Listener:
    def __init__(self, mode: str = "record"):
        self.mode = mode
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.connections: List[Dict[str, Any]] = []
        self._stop = False
        self._held: List[socket.socket] = []
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _run(self):
        self.sock.settimeout(0.5)
        while not self._stop:
            try:
                c, addr = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            rec = {"peer": addr[1], "first_bytes": ""}
            self.connections.append(rec)
            try:
                c.settimeout(2)
                try:
                    data = c.recv(4096)
                    rec["first_bytes"] = data[:200].decode("latin-1")
                except socket.timeout:
                    pass
                if self.mode == "http500":
                    c.sendall(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    c.close()
                elif self.mode == "record":
                    c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    c.close()
                else:  # silent: keep it open, answer nothing
                    self._held.append(c)
            except Exception:  # noqa: BLE001
                with contextlib.suppress(Exception):
                    c.close()

    def close(self):
        self._stop = True
        for c in self._held:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.sock.close()
        self.t.join(timeout=3)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ------------------------------------------------------------------------------------------------ dependencies
@contextlib.contextmanager
def hidden_modules(*names: str):
    """`import <name>` (and its submodules) raises ImportError in this process while the block runs."""
    real = builtins.__import__

    def hide(name, *a, **k):
        if any(name == n or name.startswith(n + ".") for n in names):
            raise ImportError(f"No module named '{name}' (hidden by the refusals probe)")
        return real(name, *a, **k)
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if any(k == n or k.startswith(n + ".") for n in names)}
    builtins.__import__ = hide
    try:
        yield
    finally:
        builtins.__import__ = real
        sys.modules.update(saved)


@contextlib.contextmanager
def fake_rdflib8():
    """The installed rdflib minus ConjunctiveGraph, reporting version 8.0.0, as `rdflib` in this process."""
    import rdflib as real_rdflib
    fake = types.ModuleType("rdflib")
    for k, v in vars(real_rdflib).items():
        if k not in ("ConjunctiveGraph", "__name__", "__loader__", "__spec__"):
            setattr(fake, k, v)
    fake.__version__ = "8.0.0"
    fake.__path__ = list(getattr(real_rdflib, "__path__", []))  # submodules (rdflib.namespace) still import
    saved = sys.modules.get("rdflib")
    sys.modules["rdflib"] = fake
    try:
        yield fake
    finally:
        if saved is not None:
            sys.modules["rdflib"] = saved


# ------------------------------------------------------------------------------------------------ spy
class Spy:
    """Count an engine's IRIS contacts: Native API object requests and FHIR server calls (instance wrappers)."""

    def __init__(self, eng):
        self.eng = eng
        self.native = 0
        self.fhir_calls: List[str] = []

    def __enter__(self):
        eng = self.eng
        cls = type(eng)
        orig_native = cls._iris_obj
        orig_fhir = getattr(cls, "_fhir_call", None)
        spy = self

        def native(*a, **k):
            spy.native += 1
            return orig_native(eng, *a, **k)
        eng._iris_obj = native
        if orig_fhir is not None:
            def fhir(operation, *a):
                spy.fhir_calls.append(operation)
                return orig_fhir(eng, operation, *a)
            eng._fhir_call = fhir
        return self

    def __exit__(self, *exc):
        for k in ("_iris_obj", "_fhir_call"):
            self.eng.__dict__.pop(k, None)

    def report(self) -> Dict[str, Any]:
        return {"native_api_requests": self.native, "fhir_server_calls": list(self.fhir_calls)}


# ------------------------------------------------------------------------------------------------ bolt
def _pack(v) -> bytes:
    if v is None:
        return b"\xC0"
    if v is True:
        return b"\xC3"
    if v is False:
        return b"\xC2"
    if isinstance(v, int):
        if -16 <= v < 128:
            return struct.pack(">b", v)
        return b"\xCB" + struct.pack(">q", v)
    if isinstance(v, str):
        b = v.encode()
        n = len(b)
        if n < 16:
            return bytes([0x80 | n]) + b
        if n < 256:
            return b"\xD0" + bytes([n]) + b
        return b"\xD1" + struct.pack(">H", n) + b
    if isinstance(v, (list, tuple)):
        n = len(v)
        head = bytes([0x90 | n]) if n < 16 else b"\xD4" + bytes([n])
        return head + b"".join(_pack(x) for x in v)
    if isinstance(v, dict):
        n = len(v)
        head = bytes([0xA0 | n]) if n < 16 else b"\xD8" + bytes([n])
        return head + b"".join(_pack(k) + _pack(x) for k, x in v.items())
    raise TypeError(type(v))


def _unpack(b: bytes, i: int):
    m = b[i]
    if m == 0xC0:
        return None, i + 1
    if m == 0xC2:
        return False, i + 1
    if m == 0xC3:
        return True, i + 1
    if m < 0x80:
        return m, i + 1
    if m >= 0xF0:
        return m - 0x100, i + 1
    if m == 0xC8:
        return struct.unpack(">b", b[i + 1:i + 2])[0], i + 2
    if m == 0xC9:
        return struct.unpack(">h", b[i + 1:i + 3])[0], i + 3
    if m == 0xCA:
        return struct.unpack(">i", b[i + 1:i + 5])[0], i + 5
    if m == 0xCB:
        return struct.unpack(">q", b[i + 1:i + 9])[0], i + 9
    if m == 0xC1:
        return struct.unpack(">d", b[i + 1:i + 9])[0], i + 9
    if 0x80 <= m <= 0x8F or m in (0xD0, 0xD1, 0xD2):
        if m <= 0x8F:
            n, j = m & 0x0F, i + 1
        elif m == 0xD0:
            n, j = b[i + 1], i + 2
        elif m == 0xD1:
            n, j = struct.unpack(">H", b[i + 1:i + 3])[0], i + 3
        else:
            n, j = struct.unpack(">I", b[i + 1:i + 5])[0], i + 5
        return b[j:j + n].decode("utf-8", "replace"), j + n
    if 0x90 <= m <= 0x9F or m in (0xD4, 0xD5):
        if m <= 0x9F:
            n, j = m & 0x0F, i + 1
        elif m == 0xD4:
            n, j = b[i + 1], i + 2
        else:
            n, j = struct.unpack(">H", b[i + 1:i + 3])[0], i + 3
        out = []
        for _ in range(n):
            x, j = _unpack(b, j)
            out.append(x)
        return out, j
    if 0xA0 <= m <= 0xAF or m in (0xD8, 0xD9):
        if m <= 0xAF:
            n, j = m & 0x0F, i + 1
        elif m == 0xD8:
            n, j = b[i + 1], i + 2
        else:
            n, j = struct.unpack(">H", b[i + 1:i + 3])[0], i + 3
        out = {}
        for _ in range(n):
            k, j = _unpack(b, j)
            x, j = _unpack(b, j)
            out[k] = x
        return out, j
    if 0xB0 <= m <= 0xBF:
        n = m & 0x0F
        tag = b[i + 1]
        j = i + 2
        fields = []
        for _ in range(n):
            x, j = _unpack(b, j)
            fields.append(x)
        return {"__struct__": tag, "fields": fields}, j
    raise ValueError(f"unpack marker 0x{m:02x}")


NAMES = {0x70: "SUCCESS", 0x71: "RECORD", 0x7E: "IGNORED", 0x7F: "FAILURE"}


class Bolt:
    """One raw Bolt session over TCP: proposes the given versions, sends single messages, reads replies."""

    def __init__(self, port: int, versions=(0x00000405, 0x00000404)):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=30)
        props = list(versions) + [0] * (4 - len(versions))
        self.s.sendall(b"\x60\x60\xb0\x17" + b"".join(struct.pack(">I", v) for v in props))
        self.version = struct.unpack(">I", self._read(4))[0]

    def _read(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            d = self.s.recv(n - len(out))
            if not d:
                raise ConnectionError("closed")
            out += d
        return out

    def send(self, tag: int, *fields) -> None:
        body = bytes([0xB0 | len(fields), tag]) + b"".join(_pack(f) for f in fields)
        out = b""
        for k in range(0, len(body), 0xFFFF):
            chunk = body[k:k + 0xFFFF]
            out += struct.pack(">H", len(chunk)) + chunk
        self.s.sendall(out + b"\x00\x00")

    def recv(self) -> Tuple[str, Any]:
        buf = b""
        while True:
            n = struct.unpack(">H", self._read(2))[0]
            if n == 0:
                if buf:
                    break
                continue
            buf += self._read(n)
        v, _ = _unpack(buf, 0)
        tag = v["__struct__"]
        return NAMES.get(tag, hex(tag)), (v["fields"][0] if v["fields"] else None)

    def call(self, tag: int, *fields) -> List[Tuple[str, Any]]:
        """Send one message and read replies up to its summary (SUCCESS / FAILURE / IGNORED)."""
        self.send(tag, *fields)
        out = []
        while True:
            name, meta = self.recv()
            out.append((name, meta))
            if name != "RECORD":
                return out

    def close(self):
        with contextlib.suppress(Exception):
            self.send(0x02)
        with contextlib.suppress(Exception):
            self.s.close()


HELLO, GOODBYE, LOGON, LOGOFF, RESET, RUN, PULL = 0x01, 0x02, 0x6A, 0x6B, 0x0F, 0x10, 0x3F


def summary(replies: List[Tuple[str, Any]]) -> Dict[str, Any]:
    last = replies[-1] if replies else (None, None)
    return {"messages": [r[0] for r in replies], "summary": last[0],
            "code": (last[1] or {}).get("code") if isinstance(last[1], dict) else None,
            "message": (last[1] or {}).get("message") if isinstance(last[1], dict) else None}
