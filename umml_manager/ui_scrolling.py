from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any


class ScrollablePage(ttk.Frame):
    """Wrap a normal page in a vertically scrollable, width-responsive viewport.

    Library and Discover keep their own table scrolling. This wrapper is intended
    for document-like pages such as Settings and Studio whose controls can exceed
    the available window height on smaller desktops.
    """

    def __init__(
        self,
        parent,
        page_factory: Callable[[ttk.Frame], ttk.Frame],
    ) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.body = ttk.Frame(self.canvas)
        self.body.columnconfigure(0, weight=1)
        self._window = self.canvas.create_window(
            (0, 0),
            window=self.body,
            anchor="nw",
        )
        self.page = page_factory(self.body)
        self.page.grid(row=0, column=0, sticky="new")

        self.body.bind("<Configure>", self._body_configured, add="+")
        self.canvas.bind("<Configure>", self._canvas_configured, add="+")
        self._bind_wheel_tree(self.page)

    def __getattr__(self, name: str) -> Any:
        """Expose the wrapped page's public controls to the existing GUI code."""

        page = self.__dict__.get("page")
        if page is not None and not name.startswith("_"):
            try:
                return getattr(page, name)
            except AttributeError:
                pass
        raise AttributeError(name)

    def _body_configured(self, _event=None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return

    def _canvas_configured(self, event) -> None:
        try:
            self.canvas.itemconfigure(self._window, width=max(1, event.width))
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return

    def _bind_wheel_tree(self, widget: tk.Misc) -> None:
        if not isinstance(widget, (ttk.Combobox, ttk.Treeview, tk.Text, tk.Listbox)):
            widget.bind("<MouseWheel>", self._mousewheel, add="+")
            widget.bind("<Button-4>", self._mousewheel, add="+")
            widget.bind("<Button-5>", self._mousewheel, add="+")
        try:
            children = widget.winfo_children()
        except tk.TclError:
            children = ()
        for child in children:
            self._bind_wheel_tree(child)

    def _mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = int(getattr(event, "delta", 0))
            if not delta:
                return None
            units = -max(-3, min(3, delta // 120 or (1 if delta > 0 else -1)))
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            return None
        return "break"
