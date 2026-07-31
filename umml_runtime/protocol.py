from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 64 * 1024
ALLOWED_COMMANDS = {"hello", "status", "queue_profile", "reload_feature"}


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Compatibility:
    build: str
    features: frozenset[str] = field(default_factory=frozenset)


class CompatibilityGate:
    """Explicit build allowlist. Unknown builds receive no runtime features."""

    def __init__(self, builds: dict[str, set[str] | list[str] | tuple[str, ...]] | None = None):
        self._builds = {str(build): frozenset(features) for build, features in (builds or {}).items()}

    def check(self, build: str) -> Compatibility:
        return Compatibility(build=build, features=self._builds.get(build, frozenset()))

    def supported(self, build: str, feature: str) -> bool:
        return feature in self.check(build).features


def decode_message(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProtocolError("message must be an object")
    if int(data.get("protocol", 0)) != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    command = str(data.get("command", ""))
    if command not in ALLOWED_COMMANDS:
        raise ProtocolError("unsupported command")
    return data


def encode_message(data: dict[str, Any]) -> bytes:
    payload = dict(data)
    payload.setdefault("protocol", PROTOCOL_VERSION)
    return (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
