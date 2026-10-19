"""Right-side menu + keyboard travel between the menu and the content area.

The Billing/options menu lives on the right side of the window and the user
can travel between the two panels without touching the mouse.

Usage (from App.__init__, after the sidebar and nav buttons exist):
    from nav_travel import install_nav_travel
    install_nav_travel(self)

Keys:
    F10        jump to the menu (press again to jump back to the content)
    Up/Down    move between menu items while the menu has focus (wraps)
    Enter      open the highlighted screen; focus moves into the content
    Escape     back to the content area without switching screens
"""

import customtkinter as ctk

NAV_HINT = "F10 menu \u2022 \u2191\u2193 move \u2022 Enter open \u2022 Esc back"


def install_nav_travel(app):
    order = list(app.nav_buttons.keys())
    app._nav_mode = False
    app._return_focus = None

    def _move(idx, step):
        app.nav_buttons[order[(idx + step) % len(order)]].focus_set()
        return "break"

    def _leave():
        app._nav_mode = False
        restore_content_focus(app)
        return "break"

    def _open(key):
        app.show(key)  # wrapped below: drops focus into the new screen
        return "break"

    for i, key in enumerate(order):
        b = app.nav_buttons[key]
        b.bind("<Up>", lambda e, i=i: _move(i, -1))
        b.bind("<Down>", lambda e, i=i: _move(i, 1))
        b.bind("<Return>", lambda e, k=key: _open(k))
        b.bind("<Escape>", lambda e: _leave())
        # CTkButton is a composite: focus can land on its inner label, whose
        # bindtags would otherwise skip the button's key bindings. Route the
        # button's bindings into every descendant so keys work regardless.
        for child in b.winfo_children():
            bt = child.bindtags()
            if str(b) not in bt:
                child.bindtags((str(b),) + bt)

    # Wrap show() so a screen opened from the menu hands focus to the content.
    # All callers use app.show / self.show, so the instance attribute is enough.
    orig_show = app.show

    def show_and_restore(key):
        was_nav = app._nav_mode
        orig_show(key)
        if was_nav:
            app._nav_mode = False
            restore_content_focus(app)

    app.show = show_and_restore
    app.bind("<F10>", lambda e: _toggle(app))

    ctk.CTkLabel(app.sidebar, text=NAV_HINT, text_color="gray",
                 font=ctk.CTkFont(size=11)).pack(side="bottom", pady=10, padx=8)


def _toggle(app):
    if getattr(app, "_nav_mode", False):
        app._nav_mode = False
        restore_content_focus(app)
    else:
        try:
            app._return_focus = app.focus_get()
        except Exception:
            app._return_focus = None
        app._nav_mode = True
        cur = getattr(app, "current", None)
        btn = app.nav_buttons.get(cur)
        if btn is None:
            btn = next(iter(app.nav_buttons.values()))
        btn.focus_set()
    return "break"


def restore_content_focus(app):
    """Put focus back into the content area (best effort, never raises)."""
    w = getattr(app, "_return_focus", None)
    try:
        if w is not None and w.winfo_exists():
            w.focus_set()
            return
    except Exception:
        pass
    scr = getattr(app, "screens", {}).get(getattr(app, "current", ""))
    foc = getattr(scr, "focus_search", None)
    if callable(foc):
        try:
            foc()
            return
        except Exception:
            pass
    try:
        app.content.focus_set()
    except Exception:
        pass
