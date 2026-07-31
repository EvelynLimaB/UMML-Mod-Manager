"""UMML-Manager: safe mod profiles, creator tooling, and transactional deployment."""

from .deployment import (
    ApplyEngine,
    ApplyError,
    LegacyBaselineMigrationRequired,
)
from .library import ManagerStore
from .models import ModRecord, Profile
from .resolver import Resolution, resolve_profile

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
