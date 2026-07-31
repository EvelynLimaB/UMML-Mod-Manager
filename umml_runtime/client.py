from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from .protocol import encode_message


class RuntimeClient:
    def __init__(self, host: str, port: int, token: str):
        self.host = host
        self.port = port
        self.token = token

    @classmethod
    def from_token_file(cls, host: str, port: int, token_path: str | Path):
        return cls(host, port, Path(token_path).read_text(encoding="utf-8").strip())

    def request(self, command: str, **payload: Any) -> dict[str, Any]:
        request = {"command": command, "token": self.token, **payload}
        with socket.create_connection((self.host, self.port), timeout=5) as stream:
            stream.sendall(encode_message(request))
            response = b""
            while not response.endswith(b"\n"):
                chunk = stream.recv(4096)
                if not chunk:
                    break
                response += chunk
        return decode_response(response)


def decode_response(raw: bytes) -> dict[str, Any]:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid runtime response")
    return data
