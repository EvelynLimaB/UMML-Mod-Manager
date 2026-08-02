from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .ui_theme import SURFACE


ResizeCallback = Callable[[int], None]


def responsive_columns(width: int, *, breakpoint: int = 820) -> int:
    """Return a stable one- or two-column layout for document-like pages."""

    return 2 if max(0, int(width)) >= max(1, int(breakpoint)) else 1


class ScrollablePage(ttk.Frame):
    """A vertically scrollable page that keeps focused controls visible.

    This container is intentionally limited to document-like pages. Tables,
    editors, and other widgets that already own scrolling should keep their own
    dedicated layout instead of being wrapped in another generic canvas.
    """

    _WHEEL_NATIVE_WIDGETS = (
        tk.Canvas,
        tk.Listbox,
        tk.Text,
        ttk.Combobox,
        ttk.Treeview,
    )

    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            background=SURFACE,
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            takefocus=False,
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.content = ttk.Frame(self.canvas)
        self.content.columnconfigure(0, weight=1)
        self._content_window = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )
        self._resize_callback: ResizeCallback | None = None
        self._viewport_width = 0
        self._bindings_finalized = False

        self.content.bind("<Configure>", self._content_configured, add="+")
        self.canvas.bind("<Configure>", self._canvas_configured, add="+")
        self.canvas.bind("<Prior>", self._page_up, add="+")
        self.canvas.bind("<Next>", self._page_down, add="+")

    @property
    def viewport_width(self) -> int:
        return self._viewport_width

    def set_resize_callback(self, callback: ResizeCallback) -> None:
        self._resize_callback = callback
        if self._viewport_width:
            callback(self._viewport_width)

    def finalize_scroll_bindings(self) -> None:
        """Bind wheel and focus behavior after the page has created its widgets."""

        if self._bindings_finalized:
            return
        self._bindings_finalized = True
        self._bind_widget_tree(self.content)

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)

    def _content_configured(self, _event=None) -> None:
        bounds = self.canvas.bbox("all")
        if bounds is not None:
            self.canvas.configure(scrollregion=bounds)

    def _canvas_configured(self, event) -> None:
        width = max(1, int(event.width))
        self.canvas.itemconfigure(self._content_window, width=width)
        if width == self._viewport_width:
            return
        self._viewport_width = width
        if self._resize_callback is not None:
            self._resize_callback(width)
        self.content.update_idletasks()
        self._content_configured()

    def _bind_widget_tree(self, widget) -> None:
        widget.bind("<FocusIn>", self._focus_entered, add="+")
        widget.bind("<Prior>", self._page_up, add="+")
        widget.bind("<Next>", self._page_down, add="+")
        if not isinstance(widget, self._WHEEL_NATIVE_WIDGETS):
            widget.bind("<MouseWheel>", self._mousewheel, add="+")
            widget.bind("<Button-4>", self._mousewheel, add="+")
            widget.bind("<Button-5>", self._mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_widget_tree(child)

    def _can_scroll(self) -> bool:
        try:
            return self.content.winfo_reqheight() > self.canvas.winfo_height()
        except tk.TclError:
            return False

    def _mousewheel(self, event):
        if not self._can_scroll():
            return None
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            delta = int(getattr(event, "delta", 0) or 0)
            if not delta:
                return None
            direction = -1 if delta > 0 else 1
        self.canvas.yview_scroll(direction * 3, "units")
        return "break"

    def _page_up(self, _event=None):
        if not self._can_scroll():
            return None
        self.canvas.yview_scroll(-1, "pages")
        return "break"

    def _page_down(self, _event=None):
        if not self._can_scroll():
            return None
        self.canvas.yview_scroll(1, "pages")
        return "break"

    def _focus_entered(self, event) -> None:
        try:
            self.after_idle(lambda widget=event.widget: self._reveal_widget(widget))
        except tk.TclError:
            return

    def _reveal_widget(self, widget) -> None:
        try:
            if not widget.winfo_exists() or not self._is_descendant(widget):
                return
            viewport_height = max(1, self.canvas.winfo_height())
            content_height = max(1, self.content.winfo_reqheight())
            top = widget.winfo_rooty() - self.content.winfo_rooty()
            bottom = top + max(1, widget.winfo_height())
            visible_top = self.canvas.canvasy(0)
            visible_bottom = visible_top + viewport_height
            margin = 12
            if top - margin < visible_top:
                target = max(0, top - margin)
                self.canvas.yview_moveto(target / content_height)
            elif bottom + margin > visible_bottom:
                target = max(0, bottom + margin - viewport_height)
                self.canvas.yview_moveto(target / content_height)
        except tk.TclError:
            return

    def _is_descendant(self, widget) -> bool:
        current = widget
        while current is not None:
            if current is self.content:
                return True
            current = getattr(current, "master", None)
        return False
