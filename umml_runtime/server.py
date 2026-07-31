from __future__ import annotations

import json
import os
import secrets
import socketserver
import threading
from pathlib import Path
from typing import Any, Callable

from .protocol import CompatibilityGate, ProtocolError, decode_message, encode_message

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class RuntimeBridgeServer:
    """Loopback-only bridge server with token auth and explicit build gating."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        gate: CompatibilityGate | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("runtime bridge must bind to loopback")
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.state_dir / "runtime-token"
        self.pending_path = self.state_dir / "runtime-pending.json"
        self.token = self._load_or_create_token()
        self.gate = gate or CompatibilityGate()
        self.handlers: dict[str, Handler] = {}
        owner = self

        class RequestHandler(socketserver.StreamRequestHandler):
            def handle(self):
                raw = self.rfile.readline(64 * 1024 + 1)
                try:
                    request = decode_message(raw.rstrip(b"\r\n"))
                    response = owner.dispatch(request)
                except ProtocolError as exc:
                    response = {"ok": False, "error": str(exc)}
                except Exception as exc:
                    response = {"ok": False, "error": f"bridge failure: {exc}"}
                self.wfile.write(encode_message(response))

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server = Server((host, port), RequestHandler)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def register(self, command: str, handler: Handler) -> None:
        if command not in {"status", "reload_feature"}:
            raise ValueError("only status and reload_feature may have runtime handlers")
        self.handlers[command] = handler

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._server.serve_forever, name="umml-runtime", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        if not secrets.compare_digest(str(request.get("token", "")), self.token):
            return {"ok": False, "error": "authentication failed"}
        command = str(request["command"])
        build = str(request.get("build", ""))
        compatibility = self.gate.check(build)
        if command == "hello":
            return {
                "ok": True,
                "mode": "enabled" if compatibility.features else "disabled",
                "build": build,
                "features": sorted(compatibility.features),
            }
        if command == "queue_profile":
            profile = str(request.get("profile", "")).strip()
            if not profile:
                return {"ok": False, "error": "profile is required"}
            self._write_pending({"profile": profile, "reason": "runtime-request", "build": build})
            return {"ok": True, "pending_restart": True, "profile": profile}
        if not compatibility.features:
            return {"ok": False, "error": "unsupported game build", "features": []}
        if command == "reload_feature":
            feature = str(request.get("feature", ""))
            if feature not in compatibility.features:
                return {"ok": False, "error": "feature not allowed for this build"}
        handler = self.handlers.get(command)
        if handler is None:
            if command == "status":
                return {"ok": True, "build": build, "features": sorted(compatibility.features)}
            return {"ok": False, "error": "runtime handler not installed"}
        response = dict(handler(request))
        response.setdefault("ok", True)
        return response

    def _load_or_create_token(self) -> str:
        if self.token_path.is_file():
            token = self.token_path.read_text(encoding="utf-8").strip()
            if token:
                return token
        token = secrets.token_urlsafe(32)
        self.token_path.write_text(token + "\n", encoding="utf-8")
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass
        return token

    def _write_pending(self, data: dict[str, Any]) -> None:
        temp = self.pending_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, self.pending_path)
