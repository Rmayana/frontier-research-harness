"""Narrow newline-delimited JSON-RPC client for the installed Codex app-server."""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


class HostRejected(RuntimeError):
    """A definite JSON-RPC rejection, distinct from an uncertain transport loss."""


class CodexAppServer:
    """One foreground connection; server requests remain pending for the user."""

    def __init__(self, executable: str = "codex", *, timeout: float = 15.0):
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        self.process = subprocess.Popen([executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
                                        creationflags=flags)
        self.timeout = timeout; self._next_id = 1
        self._write_lock = threading.Lock()
        self._eof = threading.Event()
        self.diagnostics: deque[str] = deque(maxlen=100)
        self._responses: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._closed = False
        self._reader = threading.Thread(target=self._read, daemon=True); self._reader.start()
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_reader.start()
        try:
            result = self.call("initialize", {"clientInfo": {"name": "frontier-research-harness", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
            self.runtime_identity = json.dumps(result, ensure_ascii=False, sort_keys=True)
            self.notify("initialized", {})
        except BaseException:
            self.close()
            raise

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.diagnostics.append(line[-2048:].rstrip())

    def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                try: message = json.loads(line)
                except json.JSONDecodeError: continue
                if not isinstance(message, dict): continue
                request_id = message.get("id")
                if request_id is not None and ("result" in message or "error" in message):
                    target = self._responses.get(request_id)
                    if target:
                        try: target.put_nowait(message)
                        except queue.Full: pass
                else:
                    self._events.put(message)
        finally:
            self._eof.set()
            self._events.put({"method": "transport/closed", "params": {}})

    def _write(self, message: dict[str, Any]) -> None:
        if self._closed or self.process.poll() is not None: raise RuntimeError("Codex app-server is not running")
        assert self.process.stdin is not None
        with self._write_lock:
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n"); self.process.stdin.flush()

    def respond(self, request_id: int | str, result: dict[str, Any]) -> None:
        """Only called for an explicit operator response to a pending request."""
        self._write({"id": request_id, "result": result})

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id; self._next_id += 1
        inbox: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1); self._responses[request_id] = inbox
        try:
            self._write({"id": request_id, "method": method, "params": params})
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    response = inbox.get(timeout=min(0.1, max(0, deadline - time.monotonic())))
                    break
                except queue.Empty:
                    if self._eof.is_set(): raise ConnectionError(f"transport closed before acknowledgement for {method}")
                    if time.monotonic() >= deadline: raise TimeoutError(f"no acknowledgement for {method}")
            if "error" in response: raise HostRejected(f"{method} failed: {response['error']}")
            result = response.get("result", {})
            return result if isinstance(result, dict) else {"value": result}
        finally: self._responses.pop(request_id, None)

    def drain_events(self) -> list[dict[str, Any]]:
        events = []
        while True:
            try: events.append(self._events.get_nowait())
            except queue.Empty: return events

    def close(self) -> None:
        if self._closed: return
        self._closed = True
        if self.process.stdin:
            try: self.process.stdin.close()
            except OSError: pass
        try: self.process.wait(timeout=3)
        except subprocess.TimeoutExpired: self.process.terminate(); self.process.wait(timeout=3)
        self._reader.join(timeout=1)
        self._stderr_reader.join(timeout=1)
        if self.process.stdout: self.process.stdout.close()
        if self.process.stderr: self.process.stderr.close()

    def __enter__(self) -> "CodexAppServer": return self
    def __exit__(self, *_: object) -> None: self.close()


def handshake(executable: str = "codex") -> dict[str, Any]:
    """Start, initialize, and close without creating a thread or model turn."""
    with CodexAppServer(executable) as host:
        return {"runtime_identity": json.loads(host.runtime_identity), "no_thread_started": True}
