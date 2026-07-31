from __future__ import annotations

from dataclasses import dataclass

from .models import PACKAGE_HACHIMI, PACKAGE_UMML_ASSETS, PACKAGE_UNKNOWN


@dataclass(frozen=True)
class BackendDescriptor:
    id: str
    name: str
    package_types: tuple[str, ...]
    can_prepare: bool
    can_deploy: bool
    can_hot_reload: bool
    status: str
    notes: str = ""


LEGACY_ASSET_BACKEND = BackendDescriptor(
    id="legacy-assets",
    name="UMML hashed asset deployment",
    package_types=(PACKAGE_UMML_ASSETS,),
    can_prepare=True,
    can_deploy=True,
    can_hot_reload=False,
    status="available",
    notes="Uses decrypted metadata, immutable prepared caches, and restart-safe file deployment.",
)

HACHIMI_BACKEND = BackendDescriptor(
    id="hachimi-runtime",
    name="Hachimi runtime deployment",
    package_types=(PACKAGE_HACHIMI,),
    can_prepare=False,
    can_deploy=False,
    can_hot_reload=False,
    status="planned",
    notes="Packages are detected and preserved but remain blocked until a separately tested runtime backend exists.",
)

UNKNOWN_BACKEND = BackendDescriptor(
    id="unsupported",
    name="Unsupported package",
    package_types=(PACKAGE_UNKNOWN,),
    can_prepare=False,
    can_deploy=False,
    can_hot_reload=False,
    status="unsupported",
)

BACKENDS = (LEGACY_ASSET_BACKEND, HACHIMI_BACKEND, UNKNOWN_BACKEND)


def backend_for_package(package_type: str) -> BackendDescriptor:
    for backend in BACKENDS:
        if package_type in backend.package_types:
            return backend
    return UNKNOWN_BACKEND
