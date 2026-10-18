"""BillBook - grid_billing.py
Marg-ERP-style sale-entry product grid for the Billing screen.

Columns: DESCRIPTION | PACKING | STOCK | UNIT | RATE, a "Find Name ? >>"
type-to-filter box (filters live on name and SKU, like Marg), arrow-key
navigation with Enter to pick, and an item-detail footer (PurRate, M.R.P.,
Margin %, Company) for the highlighted row.

The panel is data-only: picking a product calls the parent's on_add hook,
which reuses the existing billing flow (fill product entry -> qty -> rate ->
discount). It never touches bill state itself.
"""

from tkinter import ttk

import customtkinter as ctk

RUPEE = "\u20b9"
WARN = "\u26a0"


def money(n):
    try:
        return f"{RUPEE}{float(n):,.2f}"
    except (TypeError, ValueError):
        return f"{RUPEE}0.00"


def margin_pct(p):
    cp = float(p.get("purchase_price") or 0)
    wp = float(p.get("wholesale_price") or 0)
    if cp <= 0:
        return "\u2014"
    return f"{(wp - cp) / cp * 100:.1f}%"


class GridPanel(ctk.CTkFrame):
    """Marg-style product grid + find box + detail footer."""

    COLS = ("DESCRIPTION", "PACKING", "STOCK", "UNIT", "RATE")

    def __init__(self, master, db, on_add, price_mode="wholesale"):
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.on_add = on_add
        self.price_mode = price_mode
        self._products = []   # full product list (dicts)
        self._shown = []      # products currently in the grid

        gframe = ctk.CTkFrame(self)
        gframe.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(gframe, columns=self.COLS,
                               show="headings", height=14)
        for c, w, a in (("DESCRIPTION", 260, "w"), ("PACKING", 90, "center"),
                        ("STOCK", 130, "e"), ("UNIT", 70, "center"),
                        ("RATE", 110, "e")):
            self.tv.heading(c, text=c)
            self.tv.column(c, width=w, anchor=a)
        vsb = ttk.Scrollbar(gframe, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)
        self.tv.bind("<Return>", self._pick_selected)
        self.tv.bind("<Double-1>", self._pick_selected)

        find = ctk.CTkFrame(self, fg_color="transparent")
        find.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(find, text="Find Name ? >>",
                     font=ctk.CTkFont(weight="bold")).pack(side="left",
                                                           padx=(2, 6))
        self.find_e = ctk.CTkEntry(find, width=280,
                                   placeholder_text="type to filter "
                                                    "name or SKU...")
        self.find_e.pack(side="left")
        self.find_e.bind("<KeyRelease>", self._on_find_key)
        ctk.CTkLabel(find, text="(arrows move \u00b7 Enter picks)",
                     text_color="gray").pack(side="left", padx=8)

        self.detail = ctk.CTkLabel(
            self, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=12))
        self.detail.pack(fill="x", pady=(2, 0))
        self._blank_detail()

    def _rate_of(self, p):
        return (p["wholesale_price"] if self.price_mode == "wholesale"
                else p["retail_price"])

    def _low(self, p):
        th = float(p.get("low_stock_threshold") or 0)
        return th > 0 and float(p.get("stock") or 0) <= th

    def _blank_detail(self):
        self.detail.configure(
            text="PurRate: \u2014      M.R.P.: \u2014      "
                 "Margin%: \u2014      Company: \u2014")

    def _update_detail(self, p):
        if not p:
            self._blank_detail()
            return
        mrp = p.get("mrp") or 0
        comp = (p.get("company") or "").strip()
        self.detail.configure(
            text=f"PurRate: {money(p.get('purchase_price') or 0)}      "
                 f"M.R.P.: {money(mrp) if mrp else '\u2014'}      "
                 f"Margin%: {margin_pct(p)}      "
                 f"Company: {comp if comp else '\u2014'}")

    def set_price_mode(self, mode):
        self.price_mode = mode
        self._render()

    def set_products(self, products):
        self._products = list(products)
        self.refresh()

    def refresh(self):
        q = self.find_e.get().strip().lower()
        if q:
            self._shown = [p for p in self._products
                           if q in (p.get("name") or "").lower()
                           or q in (p.get("sku") or "").lower()]
        else:
            self._shown = list(self._products)
        self._render()

    def focus_find(self):
        self.find_e.focus_set()
        self.find_e.select_range(0, "end")

    def selected_product(self):
        sel = self.tv.selection()
        if not sel:
            return None
        pid = sel[0]
        for p in self._shown:
            if str(p["id"]) == pid:
                return p
        return None

    def _render(self):
        tv = self.tv
        for r in tv.get_children():
            tv.delete(r)
        for p in self._shown:
            pack = int(p.get("pack_size") or 1)
            stock = float(p.get("stock") or 0)
            stock_txt = (f"{WARN} {stock:g}" if self._low(p)
                         else f"{stock:g}")
            tv.insert("", "end", iid=str(p["id"]), values=(
                p.get("name") or "", pack, stock_txt, p.get("unit") or "",
                money(self._rate_of(p))))
        if self._shown:
            first = str(self._shown[0]["id"])
            tv.selection_set(first)
            tv.focus(first)
            tv.see(first)
            self._update_detail(self._shown[0])
        else:
            self._blank_detail()

    def _on_select(self, _event=None):
        self._update_detail(self.selected_product())

    def _pick_selected(self, _event=None):
        p = self.selected_product()
        if p:
            self.on_add(p)
        return "break"

    def _on_find_key(self, event):
        if event.keysym == "Down":
            if self._shown:
                self.tv.focus_set()
            return "break"
        if event.keysym == "Return":
            self._pick_selected()
            return "break"
        if event.keysym == "Escape":
            self.find_e.delete(0, "end")
            self.refresh()
            return "break"
        if event.keysym in ("Up", "Shift_L", "Shift_R", "Control_L",
                            "Control_R", "Alt_L", "Alt_R", "Caps_Lock",
                            "Tab", "ISO_Left_Tab"):
            return
        self.refresh()


# -- wiring helpers for BillingFrame (kept here to keep ui.py small) --------

def install_header(billing):
    """Grid | Cards toggle row under the Billing heading."""
    import customtkinter as ctk
    hdr = ctk.CTkFrame(billing, fg_color="transparent")
    hdr.pack(fill="x", pady=(0, 4))
    ctk.CTkLabel(hdr, text="Product picker",
                 text_color="gray").pack(side="left", padx=(2, 6))
    billing.view_var = ctk.StringVar(
        value="Grid" if billing.db.get_setting("billing_view",
                                               "grid") == "grid" else "Cards")
    ctk.CTkSegmentedButton(hdr, values=["Grid", "Cards"],
                           variable=billing.view_var,
                           command=billing.set_bill_view).pack(side="left")
    ctk.CTkLabel(hdr, text="(Ctrl+G toggles)",
                 text_color="gray",
                 font=ctk.CTkFont(size=11)).pack(side="left", padx=6)

def build_panel(frame, billing, tab, w):
    """Create the GridPanel for a billing tab and stash it in w."""
    panel = GridPanel(frame, billing.db,
                      on_add=lambda p: billing._suggest_pick(tab, w, p),
                      price_mode=tab.price_mode)
    w["grid_panel"] = panel
    view = billing.db.get_setting("billing_view", "grid")
    w["bill_view"] = view if view in ("grid", "cards") else "grid"


def apply_view(billing, tab, w):
    gp = w.get("grid_panel")
    if (w.get("bill_view") or "grid") == "grid":
        w["cards_sf"].pack_forget()
        if gp is not None:
            gp.set_price_mode(tab.price_mode)
            gp.set_products(billing.db.list_products(""))
            gp.pack(fill="both", expand=True, pady=6)
    else:
        if gp is not None:
            gp.pack_forget()
        w["cards_sf"].pack(fill="both", expand=True, pady=6)


def set_view(billing, value):
    cur = billing.current()
    if not cur:
        return
    tab, w = cur
    w["bill_view"] = "grid" if value == "Grid" else "cards"
    billing.db.set_setting("billing_view", w["bill_view"])
    apply_view(billing, tab, w)


def toggle_view(billing):
    cur = billing.current()
    if not cur:
        return
    tab, w = cur
    new = "cards" if (w.get("bill_view") or "grid") == "grid" else "grid"
    try:
        billing.view_var.set("Grid" if new == "grid" else "Cards")
    except Exception:
        pass
    set_view(billing, "Grid" if new == "grid" else "Cards")


def sync_view_var(billing):
    cur = billing.current()
    if cur:
        v = cur[1].get("bill_view") or "grid"
        try:
            billing.view_var.set("Grid" if v == "grid" else "Cards")
        except Exception:
            pass
