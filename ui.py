"""
BillBook — ui.py
All CustomTkinter screens: dashboard, product catalog, stock, multi-tab billing,
customer ledger, invoices, reports, backup/restore, settings.
"""

import csv
import shutil
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinter import ttk

import invoices

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
RUPEE = "\u20b9"


def money(n):
    try:
        return f"{RUPEE}{float(n):,.2f}"
    except (TypeError, ValueError):
        return f"{RUPEE}0.00"


def today_iso():
    return date.today().isoformat()


def fnum(widget, default=0.0):
    """Read a float from an entry widget safely."""
    try:
        return float(widget.get().strip() or default)
    except ValueError:
        return default


def tree(parent, columns, widths=None, height=12):
    """ttk.Treeview with headings, packed in a frame. Returns (frame, tree)."""
    frame = ctk.CTkFrame(parent)
    tv = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for i, c in enumerate(columns):
        tv.heading(c, text=c)
        tv.column(c, width=(widths[i] if widths else 110), anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=vsb.set)
    tv.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return frame, tv


class SearchPicker(ctk.CTkToplevel):
    """Search-as-you-type popup: pick a product or customer from a list."""

    def __init__(self, master, title, fetch_fn, display_fn, on_pick):
        super().__init__(master)
        self.title(title)
        self.geometry("460x420")
        self.fetch_fn = fetch_fn
        self.display_fn = display_fn
        self.on_pick = on_pick
        self.transient(master)
        self.grab_set()

        self.entry = ctk.CTkEntry(self, placeholder_text="Type to search...")
        self.entry.pack(fill="x", padx=12, pady=(12, 6))
        self.entry.bind("<KeyRelease>", lambda e: self.refresh())
        self.entry.bind("<Return>", lambda e: self.choose())
        self.listbox = ctk.CTkScrollableFrame(self)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.entry.focus()
        self.refresh()

    def refresh(self):
        q = self.entry.get().strip()
        for w in self.listbox.winfo_children():
            w.destroy()
        for row in self.fetch_fn(q)[:60]:
            b = ctk.CTkButton(self.listbox, text=self.display_fn(row),
                              anchor="w", fg_color="transparent",
                              text_color=("black", "white"),
                              hover_color=("gray75", "gray25"),
                              command=lambda r=row: self.pick(r))
            b.pack(fill="x", pady=1)

    def pick(self, row):
        self.destroy()
        self.on_pick(row)

    def choose(self):
        rows = self.fetch_fn(self.entry.get().strip())[:1]
        if rows:
            self.pick(rows[0])


# ---------------------------------------------------------------------------
# App shell + sidebar navigation
# ---------------------------------------------------------------------------
NAV = [
    ("Dashboard", "dashboard"),
    ("Billing", "billing"),
    ("Products", "products"),
    ("Stock", "stock"),
    ("Customers", "customers"),
    ("Invoices", "invoices"),
    ("Reports", "reports"),
    ("Backup", "backup"),
    ("Settings", "settings"),
]


class App(ctk.CTk):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.title("BillBook \u2014 Wholesale Billing")
        self.geometry("1280x800")
        self.minsize(1080, 680)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="BillBook",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(
                         pady=(18, 2), padx=12)
        prof = db.shop_profile()
        ctk.CTkLabel(self.sidebar,
                     text=prof.get("shop_name") or "Wholesale Billing",
                     text_color="gray").pack(pady=(0, 14), padx=12)

        self.nav_buttons = {}
        for label, key in NAV:
            b = ctk.CTkButton(self.sidebar, text=label, anchor="w",
                              fg_color="transparent",
                              command=lambda k=key: self.show(k))
            b.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = b

        # Theme toggle lives at the bottom of the sidebar
        self.theme_var = ctk.StringVar(
            value="Dark" if db.get_setting("theme") == "dark" else "Light")
        ctk.CTkLabel(self.sidebar, text="Theme").pack(pady=(16, 0))
        ctk.CTkSegmentedButton(self.sidebar, values=["Dark", "Light"],
                               variable=self.theme_var,
                               command=self.switch_theme).pack(
                                   padx=10, pady=6, fill="x")

        # Main content area
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.screens = {}
        self.show("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def switch_theme(self, value):
        mode = "dark" if value == "Dark" else "light"
        ctk.set_appearance_mode(mode)
        self.db.set_setting("theme", mode)
        # Rebuild current screen so ttk tables pick up readable colors
        self.show(self.current)

    def show(self, key):
        self.current = key
        for w in self.content.winfo_children():
            w.destroy()
        for k, b in self.nav_buttons.items():
            b.configure(fg_color=("gray75", "gray25") if k == key
                        else "transparent")
        screen_cls = {"dashboard": DashboardFrame, "billing": BillingFrame,
                      "products": ProductsFrame, "stock": StockFrame,
                      "customers": CustomersFrame, "invoices": InvoicesFrame,
                      "reports": ReportsFrame, "backup": BackupFrame,
                      "settings": SettingsFrame}[key]
        screen = screen_cls(self.content, self.db, self)
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens[key] = screen

    def open_billing_tab(self, **kwargs):
        """Jump to Billing and open a fresh tab (used by Invoices edit)."""
        self.show("billing")
        self.screens["billing"].new_tab(**kwargs)

    def on_close(self):
        self.db.close()
        self.destroy()


# ---------------------------------------------------------------------------
# 1. Dashboard
# ---------------------------------------------------------------------------
class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 10))

        n, total = db.sales_on(today_iso())
        dues = db.total_dues()
        low = db.low_stock_products()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        top = db.top_products(week_ago, today_iso(), limit=8)

        # KPI cards
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", pady=6)
        for title, value, color in [
                ("Today's sales", f"{n} bills \u00b7 {money(total)}", "#1f6f43"),
                ("Pending dues", money(dues), "#b3261e"),
                ("Low-stock items", str(len(low)), "#b26a00"),
                ("Stock value", money(db.stock_value()), "#0b5fa5")]:
            card = ctk.CTkFrame(cards, border_width=2, border_color=color)
            card.pack(side="left", fill="x", expand=True, padx=6)
            ctk.CTkLabel(card, text=title, text_color="gray").pack(
                anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=value,
                         font=ctk.CTkFont(size=18, weight="bold")).pack(
                             anchor="w", padx=12, pady=(0, 10))

        # Two-column: low stock + top sellers
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True, pady=8)
        cols.grid_columnconfigure(0, weight=1)
        cols.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left, text="\u26a0 Low stock alerts",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w",
                                                           padx=10, pady=6)
        fr, tv = tree(left, ("Product", "Stock", "Threshold"),
                      widths=(220, 80, 90), height=10)
        fr.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for p in low:
            tv.insert("", "end", values=(p["name"],
                                         f"{p['stock']:g} {p['unit']}",
                                         f"{p['low_stock_threshold']:g}"))

        right = ctk.CTkFrame(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(right, text="Top sellers \u2014 last 7 days",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w",
                                                           padx=10, pady=6)
        fr2, tv2 = tree(right, ("Product", "Qty sold", "Amount"),
                        widths=(220, 90, 110), height=10)
        fr2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for t in top:
            tv2.insert("", "end", values=(t["name"], f"{t['qty']:g} {t['unit']}",
                                          money(t["total"])))

        ctk.CTkButton(self, text="New bill (F2)",
                      command=lambda: app.show("billing")).pack(
                          anchor="w", pady=6)


# ---------------------------------------------------------------------------
# 2. Product catalog
# ---------------------------------------------------------------------------
UNITS = ["pcs", "kg", "g", "bag", "box", "litre", "packet", "dozen"]


class ProductsFrame(ctk.CTkFrame):
    COLS = ("ID", "Name", "SKU", "Purchase", "Wholesale", "Retail",
            "Unit", "GST%", "Stock", "Supplier")

    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(top, text="Product catalog",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         side="left")
        self.search = ctk.CTkEntry(top, placeholder_text="Search name / SKU / supplier...",
                                   width=300)
        self.search.pack(side="right", padx=6)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=4)
        ctk.CTkButton(btns, text="Add product", command=self.add_dialog).pack(
            side="left", padx=4)
        ctk.CTkButton(btns, text="Edit selected", command=self.edit_dialog).pack(
            side="left", padx=4)
        ctk.CTkButton(btns, text="Delete selected", fg_color="#b3261e",
                      hover_color="#8f1d17", command=self.delete_selected).pack(
                          side="left", padx=4)
        ctk.CTkButton(btns, text="Import CSV", command=self.import_csv).pack(
            side="right", padx=4)
        ctk.CTkButton(btns, text="Export CSV", command=self.export_csv).pack(
            side="right", padx=4)

        fr, self.tv = tree(self, self.COLS,
                            widths=(40, 220, 110, 80, 80, 80, 55, 55, 70, 130),
                            height=22)
        fr.pack(fill="both", expand=True, pady=6)
        self.tv.bind("<Double-1>", lambda e: self.edit_dialog())
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children():
            self.tv.delete(r)
        for p in self.db.list_products(self.search.get().strip()):
            self.tv.insert("", "end", iid=p["id"], values=(
                p["id"], p["name"], p["sku"], money(p["purchase_price"]),
                money(p["wholesale_price"]), money(p["retail_price"]),
                p["unit"], f"{p['gst_percent']:g}",
                f"{p['stock']:g}", p["supplier"]))

    def selected_id(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Products", "Select a product first.")
            return None
        return int(sel[0])

    def product_dialog(self, product=None):
        """Modal add/edit form. Returns dict or None."""
        win = ctk.CTkToplevel(self)
        win.title("Edit product" if product else "Add product")
        win.geometry("480x620")
        win.transient(self)
        win.grab_set()
        p = product or {}
        entries = {}

        def row(label, key, default=""):
            ctk.CTkLabel(win, text=label).pack(anchor="w", padx=14, pady=(8, 0))
            e = ctk.CTkEntry(win)
            e.insert(0, str(p.get(key, default)))
            e.pack(fill="x", padx=14)
            entries[key] = e

        row("Name *", "name")
        row("SKU / barcode", "sku")
        row("Purchase price (\u20b9)", "purchase_price", "0")
        row("Wholesale price (\u20b9)", "wholesale_price", "0")
        row("Retail price (\u20b9)", "retail_price", "0")
        ctk.CTkLabel(win, text="Unit").pack(anchor="w", padx=14, pady=(8, 0))
        unit = ctk.CTkOptionMenu(win, values=UNITS)
        unit.set(p.get("unit", "pcs") or "pcs")
        unit.pack(fill="x", padx=14)
        row("GST %", "gst_percent", "0")
        row("Current stock", "stock", "0")
        row("Low-stock alert below", "low_stock_threshold", "5")
        row("Supplier", "supplier")

        result = {}

        def save():
            if not entries["name"].get().strip():
                messagebox.showerror("Products", "Name is required.")
                return
            try:
                for k in ("purchase_price", "wholesale_price", "retail_price",
                          "gst_percent", "stock", "low_stock_threshold"):
                    float(entries[k].get() or 0)
            except ValueError:
                messagebox.showerror("Products",
                                     "Prices, GST, stock and threshold must be numbers.")
                return
            result.update({
                "name": entries["name"].get().strip(),
                "sku": entries["sku"].get().strip(),
                "purchase_price": float(entries["purchase_price"].get() or 0),
                "wholesale_price": float(entries["wholesale_price"].get() or 0),
                "retail_price": float(entries["retail_price"].get() or 0),
                "unit": unit.get(),
                "gst_percent": float(entries["gst_percent"].get() or 0),
                "stock": float(entries["stock"].get() or 0),
                "low_stock_threshold": float(
                    entries["low_stock_threshold"].get() or 5),
                "supplier": entries["supplier"].get().strip(),
            })
            win.destroy()

        ctk.CTkButton(win, text="Save", command=save).pack(pady=16)
        win.wait_window()
        return result or None

    def add_dialog(self):
        data = self.product_dialog()
        if data:
            self.db.add_product(**data)
            self.refresh()

    def edit_dialog(self):
        pid = self.selected_id()
        if pid is None:
            return
        data = self.product_dialog(self.db.get_product(pid))
        if data:
            self.db.update_product(pid, **data)
            self.refresh()

    def delete_selected(self):
        pid = self.selected_id()
        if pid is None:
            return
        p = self.db.get_product(pid)
        if not messagebox.askyesno("Delete",
                                    f"Delete '{p['name']}' permanently?"):
            return
        if not self.db.delete_product(pid):
            messagebox.showerror(
                "Delete",
                "This product appears on saved bills, so it cannot be "
                "deleted (invoice history must stay intact).")
        self.refresh()

    def import_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")],
            title="Import products from CSV")
        if not path:
            return
        # Expected header: name,sku,purchase_price,wholesale_price,retail_price,
        #                 unit,gst_percent,stock,low_stock_threshold,supplier
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if not (row.get("name") or "").strip():
                    continue
                def num(k, d=0.0):
                    try:
                        return float(row.get(k, d) or d)
                    except ValueError:
                        return d
                self.db.add_product(
                    name=row["name"].strip(), sku=(row.get("sku") or "").strip(),
                    purchase_price=num("purchase_price"),
                    wholesale_price=num("wholesale_price"),
                    retail_price=num("retail_price"),
                    unit=(row.get("unit") or "pcs").strip(),
                    gst_percent=num("gst_percent"),
                    stock=num("stock"), low_stock_threshold=num(
                        "low_stock_threshold", 5),
                    supplier=(row.get("supplier") or "").strip())
                count += 1
        messagebox.showinfo("Import", f"Imported {count} products.")
        self.refresh()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
            title="Export products to CSV")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["name", "sku", "purchase_price", "wholesale_price",
                        "retail_price", "unit", "gst_percent", "stock",
                        "low_stock_threshold", "supplier"])
            for p in self.db.list_products():
                w.writerow([p["name"], p["sku"], p["purchase_price"],
                            p["wholesale_price"], p["retail_price"], p["unit"],
                            p["gst_percent"], p["stock"],
                            p["low_stock_threshold"], p["supplier"]])
        messagebox.showinfo("Export", f"Exported to {path}")


# ---------------------------------------------------------------------------
# 3. Stock management
# ---------------------------------------------------------------------------
class StockFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Stock management",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", pady=4)
        self.value_lbl = ctk.CTkLabel(cards, text="",
                                     font=ctk.CTkFont(size=16, weight="bold"))
        self.value_lbl.pack(side="left", padx=6)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=4)
        ctk.CTkButton(btns, text="Stock IN (purchase)",
                      command=lambda: self.move_dialog("in")).pack(
                          side="left", padx=4)
        ctk.CTkButton(btns, text="Stock OUT (damage / return)",
                      fg_color="#b26a00", hover_color="#8a5200",
                      command=lambda: self.move_dialog("out")).pack(
                          side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh",
                      command=self.refresh).pack(side="right", padx=4)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, pady=6)
        tabs.add("Current stock")
        tabs.add("Movement log")

        fr, self.tv = tree(tabs.tab("Current stock"),
                           ("Product", "SKU", "Stock", "Unit",
                            "Purchase price", "Value", "Supplier"),
                           widths=(220, 110, 80, 60, 100, 110, 140), height=16)
        fr.pack(fill="both", expand=True, padx=8, pady=8)

        fr2, self.tv2 = tree(tabs.tab("Movement log"),
                             ("Date", "Product", "Change", "Reason", "Note"),
                             widths=(130, 220, 80, 100, 220), height=16)
        fr2.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children():
            self.tv.delete(r)
        for p in self.db.list_products():
            self.tv.insert("", "end", values=(
                p["name"], p["sku"], f"{p['stock']:g} {p['unit']}", p["unit"],
                money(p["purchase_price"]),
                money(p["purchase_price"] * p["stock"]), p["supplier"]))
        for r in self.tv2.get_children():
            self.tv2.delete(r)
        for m in self.db.stock_movements(limit=200):
            ch = f"{m['qty_change']:+g}"
            self.tv2.insert("", "end", values=(
                m["date"], m["name"] or "?", ch, m["reason"], m["note"]))
        self.value_lbl.configure(
            text=f"Total stock value: {money(self.db.stock_value())}")

    def move_dialog(self, direction):
        """Stock IN or OUT for one product."""
        win = ctk.CTkToplevel(self)
        win.title("Stock IN" if direction == "in" else "Stock OUT")
        win.geometry("420x400")
        win.transient(self)
        win.grab_set()

        chosen = {}

        def pick_product():
            SearchPicker(
                win, "Pick product",
                lambda q: self.db.list_products(q),
                lambda p: f"{p['name']}  ({p['stock']:g} {p['unit']})",
                lambda p: (chosen.update(p), prod_lbl.configure(
                    text=f"{p['name']} \u2014 now {p['stock']:g} {p['unit']}")))

        ctk.CTkButton(win, text="Choose product...",
                      command=pick_product).pack(pady=10, padx=14, fill="x")
        prod_lbl = ctk.CTkLabel(win, text="No product chosen",
                                text_color="gray")
        prod_lbl.pack(pady=4)

        ctk.CTkLabel(win, text="Quantity").pack(anchor="w", padx=14, pady=(6, 0))
        qty_e = ctk.CTkEntry(win)
        qty_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Note (supplier / reason)").pack(
            anchor="w", padx=14, pady=(6, 0))
        note_e = ctk.CTkEntry(win)
        note_e.pack(fill="x", padx=14)

        def save():
            if not chosen:
                messagebox.showerror("Stock", "Choose a product first.")
                return
            try:
                qty = float(qty_e.get())
                assert qty > 0
            except (ValueError, AssertionError):
                messagebox.showerror("Stock", "Enter a positive quantity.")
                return
            delta = qty if direction == "in" else -qty
            reason = "stock-in" if direction == "in" else "stock-out"
            self.db.adjust_stock(chosen["id"], delta, reason, note_e.get())
            win.destroy()
            self.refresh()
            messagebox.showinfo(
                "Stock", f"{'Added' if direction == 'in' else 'Removed'} "
                         f"{qty:g} {chosen['unit']} of {chosen['name']}.")

        ctk.CTkButton(win, text="Save", command=save).pack(pady=16)


# ---------------------------------------------------------------------------
# 4. Billing — multi-bill tabs
# ---------------------------------------------------------------------------
class BillTab:
    """In-memory state for one open bill tab."""

    def __init__(self, name):
        self.name = name
        self.edit_bill_id = None     # set when editing a finalized bill
        self.customer = None         # customer row dict
        self.payment_type = ""       # Cash / UPI / Credit (required)
        self.price_mode = "wholesale"
        self.items = []              # dicts: product_id,name,unit,qty,price,
                                     #         line_discount,gst_percent
        self.bill_discount = 0.0

    def totals(self, db):
        return db.compute_totals(self.items, self.bill_discount)


class BillingFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        self.tabs = {}          # tab name -> (tabview-name, BillTab, widgets)
        self.counter = 0

        ctk.CTkLabel(self, text="Billing",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 6))

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True)

        # Keyboard shortcuts for fast counter billing
        app.bind("<F2>", lambda e: self.new_tab())
        app.bind("<Control-s>", lambda e: self.finalize_current())
        app.bind("<Control-p>", lambda e: self.print_current())
        self.new_tab()

    # -- tabs ---------------------------------------------------------------
    def new_tab(self, edit_bill_id=None, label=None):
        self.counter += 1
        if edit_bill_id:
            bill = self.db.get_bill(edit_bill_id)
            tab_name = f"Edit {bill['bill_no']}"
        else:
            tab_name = label or f"Bill {self.counter}"
        # CTkTabview needs unique names
        base, i = tab_name, 1
        while tab_name in self.tabs:
            i += 1
            tab_name = f"{base} ({i})"
        self.tabview.add(tab_name)
        tab = BillTab(tab_name)
        if edit_bill_id:
            self._load_bill_into_tab(tab, edit_bill_id)
        widgets = self._build_tab_ui(self.tabview.tab(tab_name), tab)
        self.tabs[tab_name] = (tab, widgets)
        self.tabview.set(tab_name)
        self._refresh_totals(tab_name)
        return tab_name

    def current_name(self):
        return self.tabview.get()

    def current(self):
        name = self.current_name()
        return self.tabs.get(name)

    def _load_bill_into_tab(self, tab, bill_id):
        bill = self.db.get_bill(bill_id)
        tab.edit_bill_id = bill_id
        tab.customer = self.db.get_customer(bill["customer_id"]) if bill["customer_id"] else None
        tab.payment_type = bill["payment_type"]
        tab.bill_discount = bill["discount"]
        for it in self.db.bill_items(bill_id):
            tab.items.append({
                "product_id": it["product_id"], "name": it["name"],
                "unit": it["unit"], "qty": it["qty"], "price": it["price"],
                "line_discount": it["line_discount"],
                "gst_percent": it["gst_percent"],
                "sku": "", })
        self.db.log_bill_action(bill_id, "edited",
                                "Bill reopened for editing in Billing")

    def close_tab(self, name):
        if name in self.tabs:
            self.tabview.delete(name)
            del self.tabs[name]
        if not self.tabs:
            self.new_tab()

    # -- tab UI ----------------------------------------------------------------
    def _build_tab_ui(self, frame, tab):
        w = {}  # widget refs
        frame.grid_columnconfigure(0, weight=1)

        # Row 1: customer + payment type + price mode + bill discount
        r1 = ctk.CTkFrame(frame, fg_color="transparent")
        r1.pack(fill="x", pady=4)

        ctk.CTkLabel(r1, text="Customer *").pack(side="left", padx=(4, 2))
        cust_btn = ctk.CTkButton(r1, text="Walk-in \u2014 click to choose",
                                 width=220, anchor="w", fg_color=("gray80", "gray20"))
        cust_btn.pack(side="left", padx=4)

        ctk.CTkButton(r1, text="+ New", width=60,
                      command=lambda: self.new_customer_dialog(tab, w)).pack(
                          side="left", padx=2)

        ctk.CTkLabel(r1, text="Payment *").pack(side="left", padx=(10, 2))
        pay_var = ctk.StringVar(value=tab.payment_type)
        for pt in ("Cash", "UPI", "Credit"):
            ctk.CTkRadioButton(r1, text=pt, variable=pay_var, value=pt,
                               command=lambda: self._on_pay_change(tab, pay_var, w)
                               ).pack(side="left", padx=4)

        ctk.CTkLabel(r1, text="Price").pack(side="left", padx=(10, 2))
        mode_var = ctk.StringVar(value="Wholesale")
        ctk.CTkSegmentedButton(r1, values=["Wholesale", "Retail"],
                               variable=mode_var,
                               command=lambda v: self._on_mode_change(tab, v)
                               ).pack(side="left", padx=4)

        ctk.CTkLabel(r1, text="Bill disc. \u20b9").pack(side="left", padx=(10, 2))
        disc_e = ctk.CTkEntry(r1, width=90)
        disc_e.insert(0, f"{tab.bill_discount:g}" if tab.bill_discount else "")
        disc_e.pack(side="left", padx=4)
        disc_e.bind("<KeyRelease>",
                    lambda e: self._on_disc_change(tab, disc_e, w))

        def pick_customer():
            SearchPicker(
                frame, "Choose customer",
                lambda q: self.db.list_customers(q),
                lambda c: (f"{c['name']}  \u2014 {c['phone']}"
                           + ("  [wholesale]" if c["is_wholesale"] else "  [retail]")
                           + (f"  \u2014 dues {money(c['balance'])}"
                              if c["balance"] > 0 else "")),
                lambda c: self._set_customer(tab, c, w))

        cust_btn.configure(command=pick_customer)

        # Row 2: product search-as-you-type + qty + line discount + add
        r2 = ctk.CTkFrame(frame, fg_color="transparent")
        r2.pack(fill="x", pady=4)
        ctk.CTkLabel(r2, text="Product").pack(side="left", padx=(4, 2))
        prod_e = ctk.CTkEntry(r2, placeholder_text="Type product name or SKU...",
                              width=280)
        prod_e.pack(side="left", padx=4)
        ctk.CTkLabel(r2, text="Qty").pack(side="left", padx=(6, 2))
        qty_e = ctk.CTkEntry(r2, width=80)
        qty_e.insert(0, "1")
        qty_e.pack(side="left", padx=4)
        ctk.CTkLabel(r2, text="Line disc. \u20b9").pack(side="left", padx=(6, 2))
        ldisc_e = ctk.CTkEntry(r2, width=80)
        ldisc_e.pack(side="left", padx=4)
        add_btn = ctk.CTkButton(r2, text="Add line (Enter)",
                                command=lambda: self.add_line(tab, w))
        add_btn.pack(side="left", padx=8)

        # Suggestion popup under the product entry
        suggest = ctk.CTkScrollableFrame(r2, width=280, height=150)
        suggest.place_forget()

        def on_type(event):
            q = prod_e.get().strip()
            for ch in suggest.winfo_children():
                ch.destroy()
            if len(q) < 1:
                suggest.place_forget()
                return
            matches = self.db.list_products(q)[:8]
            if not matches:
                suggest.place_forget()
                return
            for p in matches:
                price = (p["wholesale_price"] if tab.price_mode == "wholesale"
                         else p["retail_price"])
                ctk.CTkButton(
                    suggest,
                    text=f"{p['name']} \u2014 {money(price)}/{p['unit']} "
                         f"(stock {p['stock']:g})",
                    anchor="w", fg_color="transparent",
                    text_color=("black", "white"),
                    command=lambda pp=p: (prod_e.delete(0, "end"),
                                          prod_e.insert(0, pp["name"]),
                                          w.update({"picked": pp}),
                                          suggest.place_forget(),
                                          qty_e.focus_set(),
                                          qty_e.select_range(0, "end"))
                ).pack(fill="x", pady=1)
            # Position popup under the entry
            x = prod_e.winfo_x()
            y = prod_e.winfo_y() + prod_e.winfo_height() + 4
            suggest.place(x=x, y=y)
            suggest.lift()

        prod_e.bind("<KeyRelease>", on_type)
        prod_e.bind("<Return>", lambda e: self.add_line(tab, w))
        qty_e.bind("<Return>", lambda e: self.add_line(tab, w))
        ldisc_e.bind("<Return>", lambda e: self.add_line(tab, w))
        w.update({"picked": None})

        # Items table
        fr, tv = tree(frame, ("Item", "Qty", "Rate", "Disc.", "GST%", "Amount"),
                      widths=(260, 80, 90, 80, 60, 110), height=13)
        fr.pack(fill="both", expand=True, pady=6)
        tv.bind("<Double-1>", lambda e: self.edit_line(tab, w))

        r3 = ctk.CTkFrame(frame, fg_color="transparent")
        r3.pack(fill="x", pady=2)
        ctk.CTkButton(r3, text="Remove line",
                      command=lambda: self.remove_line(tab, w)).pack(
                          side="left", padx=4)
        ctk.CTkButton(r3, text="Edit line (double-click)",
                      command=lambda: self.edit_line(tab, w)).pack(
                          side="left", padx=4)

        # Totals
        tot = ctk.CTkFrame(frame)
        tot.pack(fill="x", pady=6)
        tot_lbl = ctk.CTkLabel(tot, text="", justify="left",
                               font=ctk.CTkFont(size=14))
        tot_lbl.pack(side="left", padx=12, pady=8)
        grand_lbl = ctk.CTkLabel(tot, text="", font=ctk.CTkFont(
            size=22, weight="bold"))
        grand_lbl.pack(side="right", padx=12, pady=8)

        # Bottom actions
        r4 = ctk.CTkFrame(frame, fg_color="transparent")
        r4.pack(fill="x", pady=4)
        fin_label = ("Save changes (Ctrl+S)" if tab.edit_bill_id
                     else "Finalize bill (Ctrl+S)")
        ctk.CTkButton(r4, text=fin_label, fg_color="#1f6f43",
                      hover_color="#175733",
                      command=lambda: self.finalize_current()).pack(
                          side="left", padx=4)
        ctk.CTkButton(r4, text="Print / Preview (Ctrl+P)",
                      command=lambda: self.print_current()).pack(
                          side="left", padx=4)
        ctk.CTkButton(r4, text="Discard tab", fg_color="#b3261e",
                      hover_color="#8f1d17",
                      command=lambda: self.close_tab(tab.name)).pack(
                          side="right", padx=4)
        ctk.CTkLabel(r4, text="Shortcuts: F2 new tab \u00b7 Enter add line \u00b7 "
                              "Ctrl+S finalize \u00b7 Ctrl+P print",
                     text_color="gray").pack(side="right", padx=10)

        w.update({"cust_btn": cust_btn, "pay_var": pay_var,
                  "mode_var": mode_var, "disc_e": disc_e, "prod_e": prod_e,
                  "qty_e": qty_e, "ldisc_e": ldisc_e, "tv": tv,
                  "tot_lbl": tot_lbl, "grand_lbl": grand_lbl,
                  "suggest": suggest, "frame": frame})
        self._refresh_customer_btn(tab, w)
        return w

    # -- tab behaviour ---------------------------------------------------------
    def _set_customer(self, tab, c, w):
        tab.customer = c
        # Auto price mode from customer type
        tab.price_mode = "wholesale" if c["is_wholesale"] else "retail"
        w["mode_var"].set("Wholesale" if tab.price_mode == "wholesale"
                          else "Retail")
        self._refresh_customer_btn(tab, w)
        w["prod_e"].focus_set()

    def _refresh_customer_btn(self, tab, w):
        if tab.customer:
            c = tab.customer
            dues = f" \u00b7 dues {money(c['balance'])}" if c["balance"] > 0 else ""
            w["cust_btn"].configure(
                text=f"{c['name']}{dues}")
        else:
            w["cust_btn"].configure(text="Walk-in \u2014 click to choose")

    def _on_pay_change(self, tab, pay_var, w):
        tab.payment_type = pay_var.get()

    def _on_mode_change(self, tab, value):
        tab.price_mode = value.lower()

    def _on_disc_change(self, tab, disc_e, w):
        tab.bill_discount = fnum(disc_e)
        self._refresh_totals(tab.name)

    def new_customer_dialog(self, tab, w):
        win = ctk.CTkToplevel(self)
        win.title("New customer")
        win.geometry("400x360")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="Name *").pack(anchor="w", padx=14, pady=(10, 0))
        n_e = ctk.CTkEntry(win)
        n_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Phone").pack(anchor="w", padx=14, pady=(6, 0))
        p_e = ctk.CTkEntry(win)
        p_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Address").pack(anchor="w", padx=14, pady=(6, 0))
        a_e = ctk.CTkEntry(win)
        a_e.pack(fill="x", padx=14)
        ws_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(win, text="Wholesale customer (wholesale prices)",
                        variable=ws_var).pack(anchor="w", padx=14, pady=10)

        def save():
            name = n_e.get().strip()
            if not name:
                messagebox.showerror("Customer", "Name is required.")
                return
            cid = self.db.add_customer(name, p_e.get().strip(),
                                       a_e.get().strip(), ws_var.get())
            self._set_customer(tab, self.db.get_customer(cid), w)
            win.destroy()

        ctk.CTkButton(win, text="Save & select", command=save).pack(pady=12)

    def add_line(self, tab, w):
        name = w["prod_e"].get().strip()
        if not name:
            return
        picked = w.get("picked")
        # If the typed text exactly matches the picked product keep it,
        # otherwise resolve by name/SKU lookup.
        p = None
        if picked and picked["name"].lower() == name.lower():
            p = self.db.get_product(picked["id"])
        else:
            rows = self.db.list_products(name)
            exact = [r for r in rows if r["name"].lower() == name.lower()
                     or r["sku"].lower() == name.lower()]
            p = exact[0] if exact else (rows[0] if rows else None)
        if not p:
            messagebox.showerror("Billing",
                                 f"No product found for '{name}'.")
            return
        try:
            qty = float(w["qty_e"].get())
            assert qty > 0
        except (ValueError, AssertionError):
            messagebox.showerror("Billing", "Enter a valid quantity.")
            w["qty_e"].focus_set()
            return
        if qty > p["stock"] and not messagebox.askyesno(
                "Billing",
                f"Only {p['stock']:g} {p['unit']} of '{p['name']}' in stock. "
                f"Bill {qty:g} anyway?"):
            return
        price = (p["wholesale_price"] if tab.price_mode == "wholesale"
                 else p["retail_price"])
        tab.items.append({
            "product_id": p["id"], "name": p["name"], "unit": p["unit"],
            "qty": qty, "price": price,
            "line_discount": fnum(w["ldisc_e"]), "gst_percent": p["gst_percent"],
            "sku": p["sku"]})
        w["prod_e"].delete(0, "end")
        w["qty_e"].delete(0, "end")
        w["qty_e"].insert(0, "1")
        w["ldisc_e"].delete(0, "end")
        w["picked"] = None
        w["suggest"].place_forget()
        self._refresh_totals(tab.name)
        w["prod_e"].focus_set()

    def edit_line(self, tab, w):
        sel = w["tv"].selection()
        if not sel:
            return
        idx = w["tv"].index(sel[0])
        it = tab.items[idx]
        win = ctk.CTkToplevel(self)
        win.title("Edit line")
        win.geometry("340x340")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text=it["name"],
                     font=ctk.CTkFont(weight="bold")).pack(pady=10)
        ents = {}
        for label, key in (("Quantity", "qty"), ("Rate (\u20b9)", "price"),
                           ("Line discount (\u20b9)", "line_discount"),
                           ("GST %", "gst_percent")):
            ctk.CTkLabel(win, text=label).pack(anchor="w", padx=14, pady=(6, 0))
            e = ctk.CTkEntry(win)
            e.insert(0, f"{it[key]:g}")
            e.pack(fill="x", padx=14)
            ents[key] = e

        def save():
            try:
                it["qty"] = float(ents["qty"].get())
                it["price"] = float(ents["price"].get())
                it["line_discount"] = float(ents["line_discount"].get() or 0)
                it["gst_percent"] = float(ents["gst_percent"].get() or 0)
                assert it["qty"] > 0 and it["price"] >= 0
            except (ValueError, AssertionError):
                messagebox.showerror("Billing", "Enter valid numbers.")
                return
            win.destroy()
            self._refresh_totals(tab.name)

        ctk.CTkButton(win, text="Save", command=save).pack(pady=14)

    def remove_line(self, tab, w):
        sel = w["tv"].selection()
        if not sel:
            return
        idx = w["tv"].index(sel[0])
        del tab.items[idx]
        self._refresh_totals(tab.name)

    def _refresh_totals(self, name):
        if name not in self.tabs:
            return
        tab, w = self.tabs[name]
        for r in w["tv"].get_children():
            w["tv"].delete(r)
        for it in tab.items:
            taxable = max(it["qty"] * it["price"] - it["line_discount"], 0)
            amt = taxable * (1 + it["gst_percent"] / 100)
            w["tv"].insert("", "end", values=(
                it["name"], f"{it['qty']:g} {it['unit']}", money(it["price"]),
                money(it["line_discount"]) if it["line_discount"] else "\u2014",
                f"{it['gst_percent']:g}%", money(amt)))
        t = tab.totals(self.db)
        w["tot_lbl"].configure(
            text=f"Subtotal {money(t['subtotal'])}   \u00b7   "
                 f"GST {money(t['gst_total'])}   \u00b7   "
                 f"Bill disc. {money(t['discount'])}   \u00b7   "
                 f"Round-off {money(t['round_off'])}")
        w["grand_lbl"].configure(text=f"Total  {money(t['grand_total'])}")

    # -- finalize / print ------------------------------------------------------
    def _validate(self, tab):
        if not tab.items:
            messagebox.showerror("Billing", "Add at least one item.")
            return False
        if not tab.payment_type:
            messagebox.showerror("Billing",
                                 "Choose a payment type (Cash / UPI / Credit).")
            return False
        return True

    def finalize_current(self):
        cur = self.current()
        if not cur:
            return
        tab, w = cur
        if not self._validate(tab):
            return
        if tab.edit_bill_id:
            # Re-finalize an edited bill
            totals = self.db.update_bill(tab.edit_bill_id, tab.items,
                                         tab.bill_discount)
            bill_id = tab.edit_bill_id
            msg = (f"Bill updated. New total {money(totals['grand_total'])}.\n"
                   f"Print the corrected bill?")
        else:
            cid = tab.customer["id"] if tab.customer else None
            bill_id = self.db.create_bill(cid, tab.payment_type, tab.items,
                                          tab.bill_discount)
            bill = self.db.get_bill(bill_id)
            msg = (f"Bill {bill['bill_no']} saved \u2014 "
                   f"{money(bill['grand_total'])}.\nPrint now?")
        name = tab.name
        self.close_tab(name)
        if messagebox.askyesno("Bill saved", msg):
            invoices.print_bill(bill_id)
        self.app.show("dashboard")

    def _tab_bill_preview(self, tab):
        """Build (bill_dict, items) in DB-row shape for the print preview.
        Items always come from the tab (including unsaved edits); the header
        comes from the saved bill when editing, else a DRAFT placeholder."""
        t = tab.totals(self.db)
        if tab.edit_bill_id:
            bill = self.db.get_bill(tab.edit_bill_id)
        else:
            bill = {"bill_no": "DRAFT", "date": today_iso(),
                    "payment_type": tab.payment_type or "Cash",
                    "subtotal": t["subtotal"], "discount": t["discount"],
                    "gst_total": t["gst_total"], "round_off": t["round_off"],
                    "grand_total": t["grand_total"],
                    "customer_name": (tab.customer["name"]
                                      if tab.customer else "Walk-in"),
                    "customer_phone": (tab.customer["phone"]
                                       if tab.customer else ""),
                    "customer_address": (tab.customer["address"]
                                         if tab.customer else "")}
        return bill, tab.items

    def print_current(self):
        cur = self.current()
        if not cur:
            return
        tab, w = cur
        if tab.edit_bill_id:
            bill, items = self._tab_bill_preview(tab)
        else:
            if not self._validate(tab):
                return
            bill, items = self._tab_bill_preview(tab)
        PrintDialog(self, self.db, bill, items)


# ---------------------------------------------------------------------------
# 5. Print dialog — customization with live preview
# ---------------------------------------------------------------------------
ACCENTS = {"Green": "#1f6f43", "Blue": "#0b5fa5", "Maroon": "#8f1d17",
           "Orange": "#b26a00", "Purple": "#5b2d8e", "Black": "#222222"}


class PrintDialog(ctk.CTkToplevel):
    """Choose what the bill shows, tweak notes/colors/paper, live preview,
    then open the final HTML in the browser (Ctrl+P to print)."""

    def __init__(self, master, db, bill, items):
        super().__init__(master)
        self.db = db
        self.bill = bill
        self.items = items
        prefs = db.print_prefs()
        self.title(f"Print {bill['bill_no']}")
        self.geometry("980x700")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left: preferences
        left = ctk.CTkScrollableFrame(self, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        ctk.CTkLabel(left, text="Print settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        self.vars = {}
        for key, label in (("show_gstin", "Show shop GSTIN"),
                           ("show_item_codes", "Show item codes / SKU"),
                           ("show_discounts", "Show discount column")):
            v = ctk.BooleanVar(value=prefs[key])
            ctk.CTkCheckBox(left, text=label, variable=v,
                            command=self.render_preview).pack(
                                anchor="w", pady=4, padx=4)
            self.vars[key] = v

        ctk.CTkLabel(left, text="Accent color").pack(anchor="w", pady=(10, 2),
                                                    padx=4)
        inv = {v: k for k, v in ACCENTS.items()}
        self.accent_var = ctk.StringVar(
            value=inv.get(prefs["accent"], "Green"))
        ctk.CTkOptionMenu(left, values=list(ACCENTS.keys()),
                          variable=self.accent_var,
                          command=lambda v: self.render_preview()).pack(
                              fill="x", padx=4)

        ctk.CTkLabel(left, text="Paper size").pack(anchor="w", pady=(10, 2),
                                                  padx=4)
        self.paper_var = ctk.StringVar(
            value="Thermal 80mm" if prefs["paper"] == "thermal" else "A4")
        ctk.CTkSegmentedButton(left, values=["A4", "Thermal 80mm"],
                               variable=self.paper_var,
                               command=lambda v: self.render_preview()).pack(
                                   fill="x", padx=4)

        ctk.CTkLabel(left, text="Header note").pack(anchor="w", pady=(10, 2),
                                                   padx=4)
        self.header_e = ctk.CTkEntry(left)
        self.header_e.insert(0, prefs["header_note"])
        self.header_e.pack(fill="x", padx=4)
        self.header_e.bind("<KeyRelease>", lambda e: self.render_preview())
        ctk.CTkLabel(left, text="Footer note").pack(anchor="w", pady=(8, 2),
                                                   padx=4)
        self.footer_e = ctk.CTkEntry(left)
        self.footer_e.insert(0, prefs["footer_note"])
        self.footer_e.pack(fill="x", padx=4)
        self.footer_e.bind("<KeyRelease>", lambda e: self.render_preview())

        ctk.CTkButton(left, text="Save as defaults",
                      command=self.save_defaults).pack(fill="x", padx=4,
                                                       pady=(14, 4))
        ctk.CTkButton(left, text="Open in browser \u2014 Ctrl+P to print",
                      fg_color="#1f6f43", hover_color="#175733",
                      command=self.do_print).pack(fill="x", padx=4, pady=4)

        # Right: live preview
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        ctk.CTkLabel(right, text="Live preview",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
                         anchor="w", padx=10, pady=(8, 2))
        self.preview = ctk.CTkScrollableFrame(right, fg_color="white")
        self.preview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.render_preview()

    def current_prefs(self):
        return {
            "accent": ACCENTS[self.accent_var.get()],
            "paper": "thermal" if self.paper_var.get() == "Thermal 80mm"
                     else "A4",
            "show_gstin": self.vars["show_gstin"].get(),
            "show_item_codes": self.vars["show_item_codes"].get(),
            "show_discounts": self.vars["show_discounts"].get(),
            "header_note": self.header_e.get(),
            "footer_note": self.footer_e.get(),
        }

    def render_preview(self):
        """Rebuild the preview from the current preference widgets."""
        prefs = self.current_prefs()
        prof = self.db.shop_profile()
        for ch in self.preview.winfo_children():
            ch.destroy()
        accent = prefs["accent"]
        fg = "black"
        narrow = prefs["paper"] == "thermal"

        head = ctk.CTkFrame(self.preview, fg_color="white")
        head.pack(fill="x", pady=4)
        ctk.CTkLabel(head, text=prof.get("shop_name") or "Your Shop Name",
                     text_color=accent, fg_color="white",
                     font=ctk.CTkFont(size=18 if not narrow else 13,
                                       weight="bold")).pack()
        if prof.get("shop_address"):
            ctk.CTkLabel(head, text=prof["shop_address"], text_color="gray",
                         fg_color="white", font=ctk.CTkFont(size=11)).pack()
        if prefs["show_gstin"] and prof.get("shop_gstin"):
            ctk.CTkLabel(head, text=f"GSTIN: {prof['shop_gstin']}",
                         text_color="gray", fg_color="white",
                         font=ctk.CTkFont(size=11)).pack()
        if prefs["header_note"]:
            ctk.CTkLabel(head, text=prefs["header_note"], text_color=fg,
                         fg_color="white", font=ctk.CTkFont(size=11)).pack()
        ctk.CTkFrame(self.preview, height=3, fg_color=accent).pack(fill="x",
                                                                   pady=4)

        b = self.bill
        ctk.CTkLabel(self.preview,
                     text=f"Bill {b['bill_no']}  \u00b7  {b['date']}  \u00b7  "
                          f"{b.get('payment_type', '')}",
                     text_color=fg, fg_color="white",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self.preview,
                     text=f"Customer: {b.get('customer_name') or 'Walk-in'}",
                     text_color=fg, fg_color="white",
                     font=ctk.CTkFont(size=12)).pack(anchor="w")

        # Item lines
        cols = ["Item", "Qty", "Rate"]
        if prefs["show_discounts"]:
            cols.append("Disc.")
        cols += ["GST", "Amount"]
        grid = ctk.CTkFrame(self.preview, fg_color="white")
        grid.pack(fill="x", pady=6)
        for j, c in enumerate(cols):
            ctk.CTkLabel(grid, text=c, text_color="white", fg_color=accent,
                         font=ctk.CTkFont(size=11, weight="bold")).grid(
                             row=0, column=j, sticky="ew", padx=1)
            grid.grid_columnconfigure(j, weight=1)
        for i, it in enumerate(self.items, 1):
            vals = [it["name"] + (f"\n{it.get('sku', '')}"
                                  if prefs["show_item_codes"]
                                  and it.get("sku") else ""),
                    f"{it['qty']:g}", f"{money(it['price'])}"]
            if prefs["show_discounts"]:
                vals.append(money(it.get("line_discount", 0))
                            if it.get("line_discount") else "\u2014")
            taxable = max(it["qty"] * it["price"]
                          - it.get("line_discount", 0), 0)
            vals += [f"{it.get('gst_percent', 0):g}%",
                     money(taxable * (1 + it.get("gst_percent", 0) / 100))]
            for j, v in enumerate(vals):
                ctk.CTkLabel(grid, text=v, text_color=fg, fg_color="white",
                             font=ctk.CTkFont(size=11)).grid(
                                 row=i, column=j, sticky="w", padx=2, pady=2)

        tot = ctk.CTkFrame(self.preview, fg_color="white")
        tot.pack(fill="x", pady=6)
        for label, val in (("Subtotal", money(b["subtotal"])),
                           ("GST", money(b["gst_total"])),
                           ("Discount", money(b["discount"])),
                           ("Round off", money(b["round_off"]))):
            r = ctk.CTkFrame(tot, fg_color="white")
            r.pack(fill="x")
            ctk.CTkLabel(r, text=label, text_color=fg,
                         fg_color="white").pack(side="left")
            ctk.CTkLabel(r, text=val, text_color=fg,
                         fg_color="white").pack(side="right")
        r = ctk.CTkFrame(tot, fg_color="white")
        r.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(r, text="Grand Total", text_color=accent, fg_color="white",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkLabel(r, text=money(b["grand_total"]), text_color=accent,
                     fg_color="white",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="right")
        if prefs["footer_note"]:
            ctk.CTkLabel(self.preview, text=prefs["footer_note"],
                         text_color="gray", fg_color="white",
                         font=ctk.CTkFont(size=11)).pack(pady=8)

    def save_defaults(self):
        p = self.current_prefs()
        self.db.set_setting("print_accent", p["accent"])
        self.db.set_setting("print_paper", p["paper"])
        for k in ("show_gstin", "show_item_codes", "show_discounts"):
            self.db.set_setting(f"print_{k}", "1" if p[k] else "0")
        self.db.set_setting("print_header_note", p["header_note"])
        self.db.set_setting("print_footer_note", p["footer_note"])
        messagebox.showinfo("Print", "Print defaults saved.")

    def do_print(self):
        p = self.current_prefs()
        path = invoices.write_invoice_file(self.bill, self.items,
                                           self.db.shop_profile(), p)
        webbrowser.open(path.as_uri())
        self.destroy()


# ---------------------------------------------------------------------------
# 6. Customers — khata ledger
# ---------------------------------------------------------------------------
class CustomersFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Customer ledger (khata)",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=4)
        self.search = ctk.CTkEntry(top, placeholder_text="Search customers...",
                                   width=260)
        self.search.pack(side="left", padx=4)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkButton(top, text="Add customer",
                      command=self.add_dialog).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Record payment received", fg_color="#1f6f43",
                      hover_color="#175733",
                      command=self.payment_dialog).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Statement",
                      command=self.statement_dialog).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Delete",
                      fg_color="#b3261e", hover_color="#8f1d17",
                      command=self.delete_selected).pack(side="right", padx=4)
        self.dues_lbl = ctk.CTkLabel(top, text="",
                                     font=ctk.CTkFont(weight="bold"))
        self.dues_lbl.pack(side="right", padx=12)

        fr, self.tv = tree(self, ("Name", "Phone", "Type", "Dues \u20b9"),
                           widths=(220, 130, 90, 110), height=18)
        fr.pack(fill="both", expand=True, pady=6)
        self.tv.bind("<Double-1>", lambda e: self.statement_dialog())
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children():
            self.tv.delete(r)
        for c in self.db.list_customers(self.search.get().strip()):
            self.tv.insert("", "end", iid=c["id"], values=(
                c["name"], c["phone"],
                "Wholesale" if c["is_wholesale"] else "Retail",
                f"{c['balance']:.2f}"))
        self.dues_lbl.configure(
            text=f"Total dues: {money(self.db.total_dues())}")

    def selected_id(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Customers", "Select a customer first.")
            return None
        return int(sel[0])

    def add_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("Add customer")
        win.geometry("380x340")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="Name *").pack(anchor="w", padx=14, pady=(10, 0))
        n_e = ctk.CTkEntry(win)
        n_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Phone").pack(anchor="w", padx=14, pady=(6, 0))
        p_e = ctk.CTkEntry(win)
        p_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Address").pack(anchor="w", padx=14, pady=(6, 0))
        a_e = ctk.CTkEntry(win)
        a_e.pack(fill="x", padx=14)
        ws = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(win, text="Wholesale customer", variable=ws).pack(
            anchor="w", padx=14, pady=10)

        def save():
            if not n_e.get().strip():
                messagebox.showerror("Customers", "Name is required.")
                return
            self.db.add_customer(n_e.get().strip(), p_e.get().strip(),
                                 a_e.get().strip(), ws.get())
            win.destroy()
            self.refresh()

        ctk.CTkButton(win, text="Save", command=save).pack(pady=12)

    def payment_dialog(self):
        cid = self.selected_id()
        if cid is None:
            return
        c = self.db.get_customer(cid)
        win = ctk.CTkToplevel(self)
        win.title("Record payment")
        win.geometry("360x300")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text=f"{c['name']} \u2014 dues {money(c['balance'])}",
                     font=ctk.CTkFont(weight="bold")).pack(pady=10)
        ctk.CTkLabel(win, text="Amount received (\u20b9) *").pack(
            anchor="w", padx=14)
        amt_e = ctk.CTkEntry(win)
        amt_e.pack(fill="x", padx=14)
        ctk.CTkLabel(win, text="Note").pack(anchor="w", padx=14, pady=(6, 0))
        note_e = ctk.CTkEntry(win, placeholder_text="e.g. UPI, partial payment")
        note_e.pack(fill="x", padx=14)

        def save():
            try:
                amt = float(amt_e.get())
                assert amt > 0
            except (ValueError, AssertionError):
                messagebox.showerror("Payment", "Enter a valid amount.")
                return
            self.db.record_payment(cid, amt, note_e.get().strip())
            win.destroy()
            self.refresh()
            messagebox.showinfo(
                "Payment",
                f"Recorded {money(amt)} from {c['name']}.")

        ctk.CTkButton(win, text="Record", command=save).pack(pady=14)

    def statement_dialog(self):
        cid = self.selected_id()
        if cid is None:
            return
        c = self.db.get_customer(cid)
        win = ctk.CTkToplevel(self)
        win.title(f"Statement \u2014 {c['name']}")
        win.geometry("640x520")
        win.transient(self)

        ctk.CTkLabel(win, text=f"{c['name']}  \u00b7  {c['phone']}",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
                         anchor="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(win, text=f"Outstanding dues: {money(c['balance'])}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#b3261e").pack(anchor="w", padx=12, pady=4)

        tabs = ctk.CTkTabview(win)
        tabs.pack(fill="both", expand=True, padx=10, pady=8)
        tabs.add("Bills")
        tabs.add("Payments")
        fr, tv = tree(tabs.tab("Bills"),
                      ("Bill No", "Date", "Payment", "Total"),
                      widths=(90, 100, 90, 110), height=10)
        fr.pack(fill="both", expand=True, padx=8, pady=8)
        for b in self.db.customer_bills(cid):
            tv.insert("", "end", values=(b["bill_no"], b["date"],
                                         b["payment_type"],
                                         money(b["grand_total"])))
        fr2, tv2 = tree(tabs.tab("Payments"),
                        ("Date", "Amount", "Note"),
                        widths=(110, 100, 250), height=10)
        fr2.pack(fill="both", expand=True, padx=8, pady=8)
        for p in self.db.customer_payments(cid):
            tv2.insert("", "end", values=(p["date"], money(p["amount"]),
                                          p["note"]))

    def delete_selected(self):
        cid = self.selected_id()
        if cid is None:
            return
        c = self.db.get_customer(cid)
        if not messagebox.askyesno("Delete", f"Delete '{c['name']}'?"):
            return
        if not self.db.delete_customer(cid):
            messagebox.showerror("Delete",
                                 "This customer has bills on record and "
                                 "cannot be deleted.")
        self.refresh()


# ---------------------------------------------------------------------------
# 7. Invoices — past bills: reprint, edit, delete
# ---------------------------------------------------------------------------
class InvoicesFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Invoices \u2014 past bills",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=4)
        self.search = ctk.CTkEntry(top, placeholder_text="Search bill no / customer...",
                                   width=280)
        self.search.pack(side="left", padx=4)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkLabel(top, text="Date").pack(side="left", padx=(10, 2))
        self.date_e = ctk.CTkEntry(top, width=110,
                                   placeholder_text="YYYY-MM-DD")
        self.date_e.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Today",
                      command=lambda: (self.date_e.delete(0, "end"),
                                       self.date_e.insert(0, today_iso()),
                                       self.refresh())).pack(side="left",
                                                              padx=2)
        ctk.CTkButton(top, text="Clear",
                      command=lambda: (self.date_e.delete(0, "end"),
                                       self.search.delete(0, "end"),
                                       self.refresh())).pack(side="left",
                                                              padx=2)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=4)
        ctk.CTkButton(btns, text="Reprint", command=self.reprint).pack(
            side="left", padx=4)
        ctk.CTkButton(btns, text="View items / history",
                      command=self.view_detail).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Edit bill (reopen)",
                      command=self.edit_bill).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete bill", fg_color="#b3261e",
                      hover_color="#8f1d17",
                      command=self.delete_bill).pack(side="right", padx=4)

        fr, self.tv = tree(self, ("Bill No", "Date", "Customer", "Payment",
                                  "Items", "Total"),
                           widths=(90, 100, 220, 90, 60, 120), height=20)
        fr.pack(fill="both", expand=True, pady=6)
        self.tv.bind("<Double-1>", lambda e: self.view_detail())
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children():
            self.tv.delete(r)
        day = self.date_e.get().strip() or None
        for b in self.db.list_bills(self.search.get().strip(), day=day):
            n_items = len(self.db.bill_items(b["id"]))
            self.tv.insert("", "end", iid=b["id"], values=(
                b["bill_no"], b["date"], b["customer_name"] or "Walk-in",
                b["payment_type"], n_items, money(b["grand_total"])))

    def selected_id(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Invoices", "Select a bill first.")
            return None
        return int(sel[0])

    def reprint(self):
        bid = self.selected_id()
        if bid is None:
            return
        invoices.print_bill(bid)
        messagebox.showinfo("Reprint", "Invoice opened in your browser.")

    def view_detail(self):
        bid = self.selected_id()
        if bid is None:
            return
        b = self.db.get_bill(bid)
        items = self.db.bill_items(bid)
        hist = self.db.bill_history(bid)
        win = ctk.CTkToplevel(self)
        win.title(f"Bill {b['bill_no']}")
        win.geometry("620x560")
        win.transient(self)
        ctk.CTkLabel(win,
                     text=f"{b['bill_no']}  \u00b7  {b['date']}  \u00b7  "
                          f"{b.get('customer_name') or 'Walk-in'}  \u00b7  "
                          f"{b['payment_type']}",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
                         anchor="w", padx=12, pady=8)
        fr, tv = tree(win, ("Item", "Qty", "Rate", "Disc.", "GST%", "Amount"),
                      widths=(220, 70, 80, 70, 55, 100), height=10)
        fr.pack(fill="both", expand=True, padx=12, pady=4)
        for it in items:
            tv.insert("", "end", values=(
                it["name"], f"{it['qty']:g} {it['unit']}", money(it["price"]),
                money(it["line_discount"]) if it["line_discount"] else "\u2014",
                f"{it['gst_percent']:g}%", money(it["line_total"])))
        ctk.CTkLabel(win,
                     text=f"Subtotal {money(b['subtotal'])}  \u00b7  "
                          f"GST {money(b['gst_total'])}  \u00b7  "
                          f"Disc. {money(b['discount'])}  \u00b7  "
                          f"Round-off {money(b['round_off'])}",
                     ).pack(anchor="w", padx=12, pady=4)
        ctk.CTkLabel(win, text=f"Grand total: {money(b['grand_total'])}",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
                         anchor="w", padx=12, pady=2)
        ctk.CTkLabel(win, text="Bill history",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w",
                                                           padx=12, pady=(8, 2))
        box = ctk.CTkTextbox(win, height=110)
        box.pack(fill="x", padx=12, pady=(0, 12))
        for h in hist:
            box.insert("end", f"{h['date']} \u2014 {h['action']}: {h['details']}\n")
        box.configure(state="disabled")

    def edit_bill(self):
        bid = self.selected_id()
        if bid is None:
            return
        b = self.db.get_bill(bid)
        if not messagebox.askyesno(
                "Edit bill",
                f"Reopen {b['bill_no']} for editing?\n\n"
                "Stock will be reversed and re-applied, and the edit is "
                "recorded in the bill history."):
            return
        self.app.open_billing_tab(edit_bill_id=bid)

    def delete_bill(self):
        bid = self.selected_id()
        if bid is None:
            return
        b = self.db.get_bill(bid)
        if not messagebox.askyesno(
                "Delete bill",
                f"Delete {b['bill_no']} ({money(b['grand_total'])})?\n\n"
                "Stock and customer dues will be reversed. This cannot be undone."):
            return
        self.db.delete_bill(bid)
        self.refresh()
        messagebox.showinfo("Invoices", f"Bill {b['bill_no']} deleted.")


# ---------------------------------------------------------------------------
# 8. Reports
# ---------------------------------------------------------------------------
class ReportsFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Reports",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=4)
        ctk.CTkLabel(top, text="From").pack(side="left", padx=(4, 2))
        self.from_e = ctk.CTkEntry(top, width=110)
        self.from_e.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="To").pack(side="left", padx=(4, 2))
        self.to_e = ctk.CTkEntry(top, width=110)
        self.to_e.pack(side="left", padx=4)

        def set_range(days):
            end = date.today()
            start = end - timedelta(days=days - 1)
            self.from_e.delete(0, "end")
            self.from_e.insert(0, start.isoformat())
            self.to_e.delete(0, "end")
            self.to_e.insert(0, end.isoformat())
            self.refresh()

        ctk.CTkButton(top, text="Today", width=70,
                      command=lambda: set_range(1)).pack(side="left", padx=2)
        ctk.CTkButton(top, text="7 days", width=70,
                      command=lambda: set_range(7)).pack(side="left", padx=2)
        ctk.CTkButton(top, text="30 days", width=70,
                      command=lambda: set_range(30)).pack(side="left", padx=2)
        ctk.CTkButton(top, text="Refresh", command=self.refresh).pack(
            side="left", padx=8)

        self.cards = ctk.CTkFrame(self, fg_color="transparent")
        self.cards.pack(fill="x", pady=6)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, pady=6)
        tabs.add("Day-wise sales")
        tabs.add("GST summary")
        tabs.add("Top products")

        fr, self.tv_day = tree(tabs.tab("Day-wise sales"),
                               ("Date", "Bills", "Sales", "GST collected"),
                               widths=(120, 70, 130, 130), height=12)
        fr.pack(fill="both", expand=True, padx=8, pady=8)
        fr2, self.tv_gst = tree(tabs.tab("GST summary"),
                                ("GST slab", "Taxable value", "CGST", "SGST",
                                 "Total GST"),
                                widths=(90, 130, 110, 110, 130), height=12)
        fr2.pack(fill="both", expand=True, padx=8, pady=8)
        fr3, self.tv_top = tree(tabs.tab("Top products"),
                                ("Product", "Qty sold", "Amount"),
                                widths=(260, 100, 140), height=12)
        fr3.pack(fill="both", expand=True, padx=8, pady=8)
        set_range(30)  # fills the date boxes and renders everything

    def refresh(self):
        start = self.from_e.get().strip() or "2000-01-01"
        end = self.to_e.get().strip() or today_iso()
        s = self.db.sales_between(start, end)
        profit = self.db.profit_estimate(start, end)

        for ch in self.cards.winfo_children():
            ch.destroy()
        for title, value, color in [
                ("Bills", str(s["n"]), "#0b5fa5"),
                ("Total sales", money(s["t"]), "#1f6f43"),
                ("Discount given", money(s["d"]), "#b26a00"),
                ("GST collected", money(s["g"]), "#5b2d8e"),
                ("Profit estimate*", money(profit), "#1f6f43")]:
            card = ctk.CTkFrame(self.cards, border_width=2, border_color=color)
            card.pack(side="left", fill="x", expand=True, padx=6)
            ctk.CTkLabel(card, text=title, text_color="gray").pack(
                anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=value,
                         font=ctk.CTkFont(size=16, weight="bold")).pack(
                             anchor="w", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.cards,
                     text="* Profit = sale price \u2212 purchase price per line; "
                          "approx, ignores overheads.",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(
                         side="left", padx=8)

        for tv in (self.tv_day, self.tv_gst, self.tv_top):
            for r in tv.get_children():
                tv.delete(r)
        for d in self.db.daywise_sales(start, end):
            self.tv_day.insert("", "end", values=(d["date"], d["n"],
                                                  money(d["t"]), money(d["g"])))
        for g in self.db.gst_summary(start, end):
            taxable, gst = g["taxable"], g["gst"]
            self.tv_gst.insert("", "end", values=(
                f"{g['gst_percent']:g}%", money(taxable), money(gst / 2),
                money(gst / 2), money(gst)))
        for t in self.db.top_products(start, end, limit=50):
            self.tv_top.insert("", "end", values=(
                t["name"], f"{t['qty']:g} {t['unit']}", money(t["total"])))


# ---------------------------------------------------------------------------
# 9. Backup / restore
# ---------------------------------------------------------------------------
class BackupFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Backup & restore",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        info = ctk.CTkFrame(self)
        info.pack(fill="x", pady=8)
        p = self.db.path
        size_kb = p.stat().st_size / 1024 if p.exists() else 0
        ctk.CTkLabel(info, text=f"Data file: {p}\nSize: {size_kb:.1f} KB",
                     justify="left").pack(anchor="w", padx=12, pady=10)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=8)
        ctk.CTkButton(btns, text="Backup now (one click)", fg_color="#1f6f43",
                      hover_color="#175733", height=44,
                      command=self.backup).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Restore from file...", height=44,
                      command=self.restore).pack(side="left", padx=4)
        self.status = ctk.CTkLabel(btns, text="", text_color="gray")
        self.status.pack(side="left", padx=12)

        ctk.CTkLabel(self, text="Tip: back up daily to a pen drive or Google "
                                "Drive folder so a PC crash never loses your "
                                "bills and khata.",
                     text_color="gray", wraplength=700,
                     justify="left").pack(anchor="w", pady=12)

    def backup(self):
        folder = filedialog.askdirectory(title="Choose backup folder")
        if not folder:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = Path(folder) / f"billbook_backup_{stamp}.db"
        self.db.backup_to(dest)
        self.status.configure(text=f"Backed up to {dest.name}")
        messagebox.showinfo("Backup", f"Backup saved:\n{dest}")

    def restore(self):
        path = filedialog.askopenfilename(
            filetypes=[("SQLite DB", "*.db")], title="Choose backup file")
        if not path:
            return
        if not messagebox.askyesno(
                "Restore",
                "Replace ALL current data with this backup?\n"
                "Current bills, stock and khata will be overwritten."):
            return
        # Validate it looks like a BillBook database before overwriting
        import sqlite3
        try:
            probe = sqlite3.connect(path)
            tables = {r[0] for r in probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            probe.close()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Restore", f"Not a readable database: {e}")
            return
        if not {"products", "bills", "customers"} <= tables:
            messagebox.showerror("Restore",
                                 "This file is not a BillBook backup.")
            return
        self.db.close()
        shutil.copy2(path, self.db.path)
        messagebox.showinfo("Restore",
                            "Backup restored. The app will now restart its "
                            "database connection \u2014 please close and "
                            "reopen BillBook.")


# ---------------------------------------------------------------------------
# 10. Settings — shop profile + print defaults
# ---------------------------------------------------------------------------
class SettingsFrame(ctk.CTkFrame):
    def __init__(self, parent, db, app):
        super().__init__(parent, fg_color="transparent")
        self.db, self.app = db, app
        ctk.CTkLabel(self, text="Settings",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
                         anchor="w", pady=(4, 8))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, pady=6)

        ctk.CTkLabel(scroll, text="Shop profile \u2014 printed on every bill",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
                         anchor="w", pady=(4, 6))
        self.entries = {}
        for key, label in (("shop_name", "Shop / company name *"),
                           ("shop_tagline", "Tagline"),
                           ("shop_address", "Address"),
                           ("shop_phone", "Phone"),
                           ("shop_gstin", "GSTIN")):
            ctk.CTkLabel(scroll, text=label).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(scroll, width=420)
            e.insert(0, db.get_setting(key))
            e.pack(anchor="w", padx=4, pady=(0, 6), fill="x")
            self.entries[key] = e

        ctk.CTkLabel(scroll, text="Bill print defaults",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
                         anchor="w", pady=(12, 6))
        ctk.CTkLabel(scroll, text="Accent color").pack(anchor="w", padx=4)
        # Preselect the currently saved accent
        cur = db.get_setting("print_accent")
        cur_name = next((n for n, c in ACCENTS.items()
                         if c.lower() == cur.lower()), "Green")
        self.accent_var = ctk.StringVar(value=cur_name)
        ctk.CTkOptionMenu(scroll, values=list(ACCENTS.keys()),
                          variable=self.accent_var).pack(anchor="w", padx=4,
                                                         pady=(0, 6))

        ctk.CTkLabel(scroll, text="Paper size").pack(anchor="w", padx=4)
        self.paper_var = ctk.StringVar(
            value="Thermal 80mm"
            if db.get_setting("print_paper") == "thermal" else "A4")
        ctk.CTkSegmentedButton(scroll, values=["A4", "Thermal 80mm"],
                               variable=self.paper_var).pack(anchor="w",
                                                             padx=4,
                                                             pady=(0, 6))

        self.toggles = {}
        for key, label in (("print_show_gstin", "Show shop GSTIN on bills"),
                           ("print_show_item_codes", "Show item codes / SKU"),
                           ("print_show_discounts", "Show discount column")):
            v = ctk.BooleanVar(value=db.get_setting(key) == "1")
            ctk.CTkCheckBox(scroll, text=label, variable=v).pack(
                anchor="w", padx=4, pady=2)
            self.toggles[key] = v

        for key, label in (("print_header_note", "Header note"),
                           ("print_footer_note", "Footer note")):
            ctk.CTkLabel(scroll, text=label).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(scroll, width=420)
            e.insert(0, db.get_setting(key))
            e.pack(anchor="w", padx=4, pady=(0, 6), fill="x")
            self.entries[key] = e

        ctk.CTkButton(scroll, text="Save settings", fg_color="#1f6f43",
                      hover_color="#175733",
                      command=self.save).pack(anchor="w", padx=4, pady=14)

    def save(self):
        for key, e in self.entries.items():
            self.db.set_setting(key, e.get().strip())
        self.db.set_setting("print_accent", ACCENTS[self.accent_var.get()])
        self.db.set_setting("print_paper", "thermal"
                            if self.paper_var.get() == "Thermal 80mm"
                            else "A4")
        for key, v in self.toggles.items():
            self.db.set_setting(key, "1" if v.get() else "0")
        messagebox.showinfo("Settings", "Settings saved.")
        # Refresh sidebar shop name
        self.app.show("settings")
