"""UMML-Manager: safe mod profiles, creator tooling, and transactional deployment."""

from .deployment import (
    ApplyEngine,
    ApplyError,
    LegacyBaselineMigrationRequired,
)
from .library import ManagerStore
from .models import ModRecord, Profile
from .resolver import Resolution, resolve_profile

# GameBanana's anonymous /dl and /mmdl routes can return browser-only HTML.
# Install the bounded browser-assisted bridge once so GUI and CLI imports share
# the same safe fallback while official 1-click registration is being arranged.
from . import gamebanana_browser_bridge as _gamebanana_browser_bridge

__all__ = [
    "ApplyEngine",
    "ApplyError",
    "LegacyBaselineMigrationRequired",
    "ManagerStore",
    "ModRecord",
    "Profile",
    "Resolution",
    "resolve_profile",
]
