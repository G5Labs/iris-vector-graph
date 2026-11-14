"""A TCP proxy between one IVG client process and the IRIS superserver, for the disconnect world (gate 3.7).

The client connects to the proxy instead of the superserver; nothing in the product or the driver changes. The proxy
frames the IRIS wire protocol (a 14-byte header: payload length uint32 LE, message id uint32 LE, statement id uint32
LE, a 2-character message type; then the payload) in both directions, so a disconnect can be placed at an exact
message:

- ``drop_request(pred)``: the first client message for which ``pred(msg)`` holds is not forwarded; the proxy reports
  it (event ``request_dropped``) and forwards nothing more in either direction. The server never sees the request.
- ``hold_reply(pred)``: the first client message for which ``pred`` holds is forwarded; the server's reply with the
  same message id is held (event ``reply_held``, its bytes kept in ``held``) and nothing more is forwarded. The
  server has finished the call; the client never reads its answer: the ambiguous acknowledgement.

After an event the harness kills the client process (SIGKILL) and calls ``close()``, which closes both sockets: the
server process then finds its client gone. ``log`` keeps (direction, id, type, length, ascii preview) of every
message for the record.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

HDR = 14


@dataclass
class Msg:
    direction: str      # "c2s" or "s2c"
    length: int
    msg_id: int
    stmt_id: int
    mtype: str
    payload: bytes

    def text(self) -> str:
        """Payload as latin-1 with non-printables as '.', for matching names and for the log."""
        return "".join(chr(b) if 32 <= b < 127 else "." for b in self.payload)

    def has(self, *needles: str) -> bool:
        t = self.payload
        return all(n.encode() in t or n.encode("utf-16-le") in t for n in needles)


@dataclass
class Proxy:
    upstream_port: int
    host: str = "127.0.0.1"
    port: int = 0
    log: List[tuple] = field(default_factory=list)
    held: bytes = b""
    dropped: Optional[Msg] = None
    trigger_msg: Optional[Msg] = None
    request_dropped: threading.Event = field(default_factory=threading.Event)
    reply_held: threading.Event = field(default_factory=threading.Event)
    request_seen: threading.Event = field(default_factory=threading.Event)
    request_forwarded: threading.Event = field(default_factory=threading.Event)
    t_request: Optional[float] = None
    t_reply: Optional[float] = None

    def __post_init__(self) -> None:
        self._mode: Optional[str] = None
        self._pred: Optional[Callable[[Msg], bool]] = None
        self._await_id: Optional[int] = None
        self._frozen = False
        self._lock = threading.Lock()
        self._socks: List[socket.socket] = []
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, 0))
        self._srv.listen(4)
        self.port = self._srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    # -- control ---------------------------------------------------------------
    def drop_request(self, pred: Callable[[Msg], bool]) -> None:
        with self._lock:
            self._mode, self._pred = "drop", pred

    def hold_reply(self, pred: Callable[[Msg], bool]) -> None:
        with self._lock:
            self._mode, self._pred = "hold", pred

    def close(self) -> None:
        with self._lock:
            self._frozen = True
        for s in self._socks + [self._srv]:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    # -- pumps -----------------------------------------------------------------
    def _accept(self) -> None:
        while True:
            try:
                c, _ = self._srv.accept()
            except OSError:
                return
            u = socket.create_connection((self.host, self.upstream_port))
            for s in (c, u):
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._socks += [c, u]
            threading.Thread(target=self._pump, args=(c, u, "c2s"), daemon=True).start()
            threading.Thread(target=self._pump, args=(u, c, "s2c"), daemon=True).start()

    @staticmethod
    def _read_exact(s: socket.socket, n: int) -> Optional[bytes]:
        buf = b""
        while len(buf) < n:
            try:
                chunk = s.recv(n - len(buf))
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    def _pump(self, src: socket.socket, dst: socket.socket, direction: str) -> None:
        while True:
            hdr = self._read_exact(src, HDR)
            if hdr is None:
                return
            length, msg_id, stmt_id = struct.unpack("<III", hdr[:12])
            mtype = hdr[12:14].decode("latin-1")
            body = self._read_exact(src, length) if length else b""
            if body is None:
                return
            m = Msg(direction, length, msg_id, stmt_id, mtype, body)
            self.log.append((round(time.time(), 4), direction, msg_id, mtype, length, m.text()[:160]))
            with self._lock:
                if self._frozen:
                    continue  # after an event nothing more crosses
                if direction == "c2s" and self._mode is not None and self._await_id is None and self._pred(m):
                    self.trigger_msg = m
                    self.request_seen.set()
                    if self._mode == "drop":
                        self.dropped = m
                        self._frozen = True
                        self.request_dropped.set()
                        continue
                    self._await_id = msg_id
                if direction == "s2c" and self._await_id is not None and msg_id == self._await_id:
                    self.t_reply = time.time()
                    self.held = hdr + body
                    self._frozen = True
                    self.reply_held.set()
                    continue
            try:
                dst.sendall(hdr + body)
            except OSError:
                return
            if m is self.trigger_msg and direction == "c2s":
                self.t_request = time.time()
                self.request_forwarded.set()
