# UMML Manager themes

UMML Manager provides three persistent appearance modes in **Settings → Appearance**:

- **System** follows the current desktop preference and re-checks it while the Manager is open.
- **Light** uses a warm race-day palette with cream surfaces, racing green actions, and pink accents.
- **Dark** uses deep green surfaces with bright green actions and restrained pink accents.

The theme setting is stored in the existing Manager `settings.json` document. Saving installation settings does not remove or replace it because settings updates are merged.

## System-theme detection

System mode resolves the desktop preference in this order:

1. `UMML_SYSTEM_THEME=light|dark`, used by package smoke tests and available as an explicit diagnostic override.
2. Theme names exposed through `GTK_THEME`, `KDE_COLOR_SCHEME`, or `QT_STYLE_OVERRIDE`.
3. Windows `AppsUseLightTheme` when running on Windows.
4. KDE `~/.config/kdeglobals`, including window-background luminance when the color-scheme name is ambiguous.
5. GTK 4 and GTK 3 `settings.ini`, including `gtk-application-prefer-dark-theme`.
6. A predictable Light fallback when no preference can be established.

The Manager polls System mode every five seconds. Explicit Light and Dark selections are stable and do not change when the desktop theme changes.

## Widget coverage

The theme engine configures all ttk styles used by Library, Discover, Studio, Conflicts, Settings, navigation, badges, forms, tables, notebooks, progress bars, and scrollbars. It also re-themes classic Tk widgets such as text views, preview labels, menus, and diagnostic windows when they are created or mapped.

Tk cannot reproduce every skewed panel, animation, mask, or micro-effect from Umamusume's Unity interface. The Manager instead preserves the recognizable visual language: bright green primary actions, pink highlights, cream or deep-green panels, sporty hierarchy, strong badges, and high text contrast without shipping game assets.

## Validation

`tests/test_manager_theme.py` covers:

- mode normalization and fail-safe behavior;
- explicit-mode isolation from the desktop;
- environment, KDE, and GTK system detection;
- fallback behavior;
- normal-text contrast for both palettes.

`scripts/test_manager_theme_runtime.py` launches a GUI runtime once with the Light palette and once with the Dark palette. The Manager workflow runs this against:

- the source GUI;
- the frozen runtime;
- the AppImage;
- the extracted Debian runtime;
- the installed Debian command.

Each pass uses the existing disposable `--smoke-test`, renders every page under Xvfb, and does not touch real Manager or game data.
