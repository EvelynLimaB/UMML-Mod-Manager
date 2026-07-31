from __future__ import annotations

import tkinter as tk


def present_toplevel(
    dialog: tk.Toplevel,
    parent: tk.Misc,
    *,
    modal: bool = True,
) -> None:
    """Center, raise, and focus a Manager-owned window without leaving it topmost."""

    try:
        dialog.update_idletasks()
        parent_top = parent.winfo_toplevel()
        width = max(dialog.winfo_reqwidth(), dialog.winfo_width())
        height = max(dialog.winfo_reqheight(), dialog.winfo_height())
        x = parent_top.winfo_rootx() + max(24, (parent_top.winfo_width() - width) // 2)
        y = parent_top.winfo_rooty() + max(24, (parent_top.winfo_height() - height) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        dialog.lift(parent_top)
        if modal:
            dialog.grab_set()
        try:
            dialog.attributes("-topmost", True)
            dialog.after(180, lambda: _clear_topmost(dialog))
        except tk.TclError:
            pass
        dialog.focus_force()
    except tk.TclError:
        return


def _clear_topmost(dialog: tk.Toplevel) -> None:
    try:
        if dialog.winfo_exists():
            dialog.attributes("-topmost", False)
            dialog.lift()
            dialog.focus_force()
    except tk.TclError:
        pass
