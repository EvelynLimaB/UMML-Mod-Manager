from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from .support_bundle import (
    SupportBundleError,
    create_support_bundle,
    default_support_bundle_name,
)


def create_support_bundle_from_ui(app) -> None:
    """Ask for a destination and create a scrubbed support archive in background."""

    if bool(getattr(app, "_busy", False)):
        messagebox.showinfo(
            "Uma Mod Manager is busy",
            "Wait for the current operation to finish before creating a support bundle.",
            parent=app.root,
        )
        return

    selected = filedialog.asksaveasfilename(
        parent=app.root,
        title="Save privacy-scrubbed support bundle",
        initialfile=default_support_bundle_name(),
        defaultextension=".zip",
        filetypes=(("ZIP archive", "*.zip"), ("All files", "*")),
    )
    if not selected:
        return

    destination = Path(selected).expanduser()

    def completed(path: Path) -> None:
        app.status.set(f"Support bundle created: {path.name}")
        messagebox.showinfo(
            "Support bundle ready",
            (
                f"Created:\n{path}\n\n"
                "Inspect support-report.json before uploading the ZIP. "
                "The bundle excludes game assets, mod payloads, baselines, "
                "roster snapshots, and raw settings."
            ),
            parent=app.root,
        )

    def failed(exc: Exception) -> None:
        app.status.set("Support bundle creation failed")
        messagebox.showerror(
            "Could not create support bundle",
            str(exc),
            parent=app.root,
        )

    app._run_task(
        "Creating privacy-scrubbed support bundle…",
        lambda: create_support_bundle(app.store, destination),
        completed,
        failed=failed,
    )


__all__ = [
    "SupportBundleError",
    "create_support_bundle_from_ui",
]
