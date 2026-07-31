from .base import ProviderDescriptor, ProviderRegistry
from .gamebanana import GameBananaClient, GameBananaFile, GameBananaMod
from .gamebanana_previews import PreviewGameBananaClient

GameBananaClient.descriptor = ProviderDescriptor(  # type: ignore[attr-defined]
    id="gamebanana",
    name="GameBanana",
    supports_browse=True,
    supports_updates=True,
    supports_file_selection=True,
    regions=("global", "japan"),
)
PreviewGameBananaClient.descriptor = GameBananaClient.descriptor  # type: ignore[attr-defined]


def default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(PreviewGameBananaClient())
    return registry


__all__ = [
    "GameBananaClient",
    "GameBananaFile",
    "GameBananaMod",
    "PreviewGameBananaClient",
    "ProviderDescriptor",
    "ProviderRegistry",
    "default_provider_registry",
]
