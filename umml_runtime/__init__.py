"""Optional, fail-closed local bridge between UMML Manager and an in-game adapter."""

from .protocol import PROTOCOL_VERSION, CompatibilityGate, ProtocolError
from .server import RuntimeBridgeServer

__all__ = ["PROTOCOL_VERSION", "CompatibilityGate", "ProtocolError", "RuntimeBridgeServer"]
