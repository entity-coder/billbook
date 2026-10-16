"""
BillBook — wholesale billing app
db.py — SQLite storage layer (stdlib sqlite3 only)

Tables:
  products        product catalog
  customers       saved customers + khata balances
  bills           bill headers
  bill_items      one row per line on a bill
  payments        payments received from customers (khata)
  stock_movements stock in/out log (audit trail)
  bill_history    edit log for finalized bills
  settings        key/value store: shop profile + print preferences
"""

import sqlite3
import sys
import os
from datetime import date, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def app_dir() -> Path:
    """Folder the app runs from. When frozen by PyInstaller, this is the folder
    containing BillBook.exe; otherwise the folder containing this file."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    d = app_dir() / "billbook_data"
    d.mkdir(exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "billbook.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    sku                TEXT DEFAULT '',
    purchase_price     REAL NOT NULL DEFAULT 0,
    wholesale_price    REAL NOT NULL DEFAULT 0,
    retail_price       REAL NOT NULL DEFAULT 0,
    unit               TEXT NOT NULL DEFAULT 'pcs',
    gst_percent        REAL NOT NULL DEFAULT 0,
    stock              REAL NOT NULL DEFAULT 0,
    low_stock_threshold REAL NOT NULL DEFAULT 5,
    supplier           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT DEFAULT '',
    address     TEXT DEFAULT '',
    is_wholesale INTEGER NOT NULL DEFAULT 1,
    balance     REAL NOT NULL DEFAULT 0   -- outstanding dues (khata)
);

CREATE TABLE IF NOT EXISTS bills (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no      TEXT NOT NULL UNIQUE,
    date         TEXT NOT NULL,              -- YYYY-MM-DD
    customer_id  INTEGER,
    payment_type TEXT NOT NULL DEFAULT 'Cash',   -- Cash / UPI / Credit
    subtotal     REAL NOT NULL DEFAULT 0,     -- pre-GST after line discounts
    discount     REAL NOT NULL DEFAULT 0,     -- flat bill-level discount (post-GST)
    gst_total    REAL NOT NULL DEFAULT 0,
    round_off    REAL NOT NULL DEFAULT 0,
    grand_total  REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'draft',  -- draft / final
    created_at   TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS bill_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id       INTEGER NOT NULL,
    product_id    INTEGER,
    name          TEXT NOT NULL,
    qty           REAL NOT NULL,
    unit          TEXT NOT NULL DEFAULT 'pcs',
    price         REAL NOT NULL,             -- unit price actually charged
    line_discount REAL NOT NULL DEFAULT 0,   -- pre-GST discount on this line
    gst_percent   REAL NOT NULL DEFAULT 0,
    line_total    REAL NOT NULL,             -- (qty*price - line_discount) + GST
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    amount      REAL NOT NULL,
    date        TEXT NOT NULL,
    note        TEXT DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    qty_change REAL NOT NULL,      -- +in / -out
    reason     TEXT NOT NULL,      -- 'stock-in', 'stock-out', 'bill', 'bill-edit', 'import'
    date       TEXT NOT NULL,
    note       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bill_history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    action  TEXT NOT NULL,         -- 'created', 'edited', 'reprinted'
    details TEXT DEFAULT '',
    date    TEXT NOT NULL,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    phone   TEXT DEFAULT '',
    address TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS purchases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    date        TEXT NOT NULL,              -- YYYY-MM-DD
    ref_no      TEXT DEFAULT '',            -- supplier invoice / ref number
    subtotal    REAL NOT NULL DEFAULT 0,    -- pre-GST
    gst_total   REAL NOT NULL DEFAULT 0,
    grand_total REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id  INTEGER,
    name        TEXT NOT NULL,
    qty         REAL NOT NULL,
    unit        TEXT NOT NULL DEFAULT 'pcs',
    cost        REAL NOT NULL,              -- purchase cost per unit
    gst_percent REAL NOT NULL DEFAULT 0,
    line_total  REAL NOT NULL,              -- (qty*cost) + GST
    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS returns (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id        INTEGER NOT NULL,
    credit_note_no TEXT NOT NULL UNIQUE,
    date           TEXT NOT NULL,
    customer_id    INTEGER,
    subtotal       REAL NOT NULL DEFAULT 0,
    gst_total      REAL NOT NULL DEFAULT 0,
    total          REAL NOT NULL DEFAULT 0,  -- credit amount incl. GST
    note           TEXT DEFAULT '',
    created_at     TEXT NOT NULL,
    FOREIGN KEY (bill_id) REFERENCES bills(id)
);

CREATE TABLE IF NOT EXISTS return_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id     INTEGER NOT NULL,
    bill_item_id  INTEGER NOT NULL,
    product_id    INTEGER,
    name          TEXT NOT NULL,
    sku           TEXT DEFAULT '',
    qty           REAL NOT NULL,
    unit          TEXT NOT NULL DEFAULT 'pcs',
    price         REAL NOT NULL,             -- unit price originally charged
    line_discount REAL NOT NULL DEFAULT 0,
    gst_percent   REAL NOT NULL DEFAULT 0,
    line_total    REAL NOT NULL,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE
);
"""

DEFAULT_SETTINGS = {
    # Shop profile (printed on every bill)
    "shop_name": "",
    "shop_tagline": "",
    "shop_address": "",
    "shop_phone": "",
    "shop_gstin": "",
    # Print preferences
    "print_accent": "#1f6f43",
    "print_paper": "A4",            # A4 / thermal
    "print_show_gstin": "1",
    "print_show_item_codes": "1",
    "print_show_discounts": "1",
    "print_header_note": "",
    "print_footer_note": "",   # terms & conditions / notes (below totals)
    # Print flow
    "print_on_save": "ask",        # ask / print / preview / skip
    "print_printer": "",           # "" = OS default printer
    "print_copies": "1",
    # Invoice design (customizable invoice)
    "invoice_title": "TAX INVOICE",
    "invoice_font_size": "standard",  # compact / standard / large
    "invoice_show_tagline": "1",
    "invoice_show_address": "1",
    "invoice_show_phone": "1",
    "invoice_show_gst_table": "1",
    "invoice_show_hsn": "0",          # HSN column (uses SKU as the value)
    "invoice_show_roundoff": "1",
    "invoice_show_customer_address": "1",
    "invoice_show_payment_badge": "1",
    "invoice_show_signature": "1",
    "invoice_show_thankyou": "1",
    "invoice_thankyou_text": "Thank you for your business!",
    "invoice_logo_path": "",
    "invoice_number_prefix": "BB-",
    # Automatic backup on app exit
    "auto_backup_on_exit": "1",   # "1" = back up every time the app closes
    "auto_backup_folder": "",     # "" = default billbook_data/backups/
    # Bill numbering
    "bill_counter": "1",
    # Credit-note numbering (sales returns)
    "credit_note_counter": "1",
    # Theme
    "theme": "dark",
}


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------
class DB:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else db_path()
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        for k, v in DEFAULT_SETTINGS.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )
        self.conn.commit()

    def _migrate(self):
        """Additive schema upgrades for databases created by older builds."""
        try:
            cols = [r["name"] for r in
                    self.conn.execute("PRAGMA table_info(payments)").fetchall()]
            if "mode" not in cols:
                self.conn.execute(
                    "ALTER TABLE payments ADD COLUMN mode TEXT DEFAULT 'Cash'")
            self.conn.commit()
        except Exception:
            pass

    # -- generic helpers ----------------------------------------------------
    def _rows(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _one(self, sql, params=()):
        r = self.conn.execute(sql, params).fetchone()
        return dict(r) if r else None

    # -- settings -----------------------------------------------------------
    def get_setting(self, key, default=""):
        r = self._one("SELECT value FROM settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def shop_profile(self):
        return {k: self.get_setting(k) for k in
                ("shop_name", "shop_tagline", "shop_address",
                 "shop_phone", "shop_gstin")}

    def print_prefs(self):
        """All invoice/print preferences. Missing keys fall back to the
        defaults in DEFAULT_SETTINGS so old databases keep working."""
        def flag(key, default="1"):
            return self.get_setting(key, default) == "1"

        return {
            "accent": self.get_setting("print_accent") or "#1f6f43",
            "paper": self.get_setting("print_paper") or "A4",
            "show_gstin": flag("print_show_gstin"),
            "show_item_codes": flag("print_show_item_codes"),
            "show_discounts": flag("print_show_discounts"),
            "header_note": self.get_setting("print_header_note"),
            "footer_note": self.get_setting("print_footer_note"),
            # Invoice design
            "invoice_title": (self.get_setting("invoice_title", "TAX INVOICE")
                              or "TAX INVOICE"),
            "font_size": (self.get_setting("invoice_font_size", "standard")
                          or "standard"),
            "show_tagline": flag("invoice_show_tagline"),
            "show_address": flag("invoice_show_address"),
            "show_phone": flag("invoice_show_phone"),
            "show_gst_table": flag("invoice_show_gst_table"),
            "show_hsn": flag("invoice_show_hsn", "0"),
            "show_roundoff": flag("invoice_show_roundoff"),
            "show_customer_address": flag("invoice_show_customer_address"),
            "show_payment_badge": flag("invoice_show_payment_badge"),
            "show_signature": flag("invoice_show_signature"),
            "show_thankyou": flag("invoice_show_thankyou"),
            "thankyou_text": (self.get_setting(
                "invoice_thankyou_text", "Thank you for your business!")),
            "logo_path": self.get_setting("invoice_logo_path"),
            "number_prefix": (self.get_setting("invoice_number_prefix", "BB-")
                              or "BB-"),
        }

    def invoice_logo_file(self):
        """Absolute path of the stored invoice logo, or None."""
        p = self.get_setting("invoice_logo_path") or ""
        if p and os.path.isfile(p):
            return p
        return None

    # -- products -----------------------------------------------------------
    def list_products(self, search=""):
        if search:
            like = f"%{search}%"
            return self._rows(
                "SELECT * FROM products WHERE name LIKE ? OR sku LIKE ? "
                "OR supplier LIKE ? ORDER BY name", (like, like, like))
        return self._rows("SELECT * FROM products ORDER BY name")

    def get_product(self, pid):
        return self._one("SELECT * FROM products WHERE id=?", (pid,))

    def add_product(self, **kw):
        cols = ("name", "sku", "purchase_price", "wholesale_price",
                "retail_price", "unit", "gst_percent", "stock",
                "low_stock_threshold", "supplier")
        vals = [kw.get(c, 0 if c not in ("name", "sku", "unit", "supplier") else
                       ("" if c != "unit" else "pcs")) for c in cols]
        cur = self.conn.execute(
            f"INSERT INTO products ({', '.join(cols)}) VALUES "
            f"({', '.join('?' * len(cols))})", vals)
        pid = cur.lastrowid
        if kw.get("stock"):
            self.log_stock(pid, kw["stock"], "stock-in", "Opening stock")
        self.conn.commit()
        return pid

    def update_product(self, pid, **kw):
        allowed = ("name", "sku", "purchase_price", "wholesale_price",
                   "retail_price", "unit", "gst_percent", "stock",
                   "low_stock_threshold", "supplier")
        sets = [f"{c}=?" for c in allowed if c in kw]
        if sets:
            self.conn.execute(
                f"UPDATE products SET {', '.join(sets)} WHERE id=?",
                [kw[c] for c in allowed if c in kw] + [pid])
            self.conn.commit()

    def delete_product(self, pid):
        # Never delete a product that appears on a bill — keep invoice history.
        used = self._one("SELECT COUNT(*) c FROM bill_items WHERE product_id=?",
                         (pid,))["c"]
        if used:
            return False
        self.conn.execute("DELETE FROM products WHERE id=?", (pid,))
        self.conn.commit()
        return True

    def low_stock_products(self):
        return self._rows(
            "SELECT * FROM products WHERE stock <= low_stock_threshold "
            "ORDER BY stock ASC")

    def stock_value(self):
        r = self._one("SELECT COALESCE(SUM(purchase_price * stock), 0) v "
                      "FROM products")
        return r["v"]

    # -- stock movements ----------------------------------------------------
    def log_stock(self, product_id, qty_change, reason, note=""):
        self.conn.execute(
            "INSERT INTO stock_movements (product_id, qty_change, reason, date, note)"
            " VALUES (?, ?, ?, ?, ?)",
            (product_id, qty_change, reason,
             datetime.now().strftime("%Y-%m-%d %H:%M"), note))
        self.conn.commit()

    def adjust_stock(self, product_id, qty_change, reason, note=""):
        """Change stock and write the movement log. qty_change signed."""
        self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?",
                          (qty_change, product_id))
        self.log_stock(product_id, qty_change, reason, note)

    def stock_movements(self, product_id=None, limit=200):
        if product_id:
            return self._rows(
                "SELECT m.*, p.name FROM stock_movements m "
                "LEFT JOIN products p ON p.id=m.product_id "
                "WHERE m.product_id=? ORDER BY m.id DESC LIMIT ?",
                (product_id, limit))
        return self._rows(
            "SELECT m.*, p.name FROM stock_movements m "
            "LEFT JOIN products p ON p.id=m.product_id "
            "ORDER BY m.id DESC LIMIT ?", (limit,))

    # -- customers / khata --------------------------------------------------
    def list_customers(self, search=""):
        if search:
            like = f"%{search}%"
            return self._rows(
                "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? "
                "ORDER BY name", (like, like))
        return self._rows("SELECT * FROM customers ORDER BY name")

    def get_customer(self, cid):
        return self._one("SELECT * FROM customers WHERE id=?", (cid,))

    def add_customer(self, name, phone="", address="", is_wholesale=True):
        cur = self.conn.execute(
            "INSERT INTO customers (name, phone, address, is_wholesale) "
            "VALUES (?, ?, ?, ?)", (name, phone, address,
                                    1 if is_wholesale else 0))
        self.conn.commit()
        return cur.lastrowid

    def update_customer(self, cid, **kw):
        allowed = ("name", "phone", "address", "is_wholesale")
        sets = [f"{c}=?" for c in allowed if c in kw]
        if sets:
            self.conn.execute(
                f"UPDATE customers SET {', '.join(sets)} WHERE id=?",
                [kw[c] for c in allowed if c in kw] + [cid])
            self.conn.commit()

    def delete_customer(self, cid):
        if self._one("SELECT COUNT(*) c FROM bills WHERE customer_id=?",
                     (cid,))["c"]:
            return False
        self.conn.execute("DELETE FROM customers WHERE id=?", (cid,))
        self.conn.commit()
        return True

    def record_payment(self, customer_id, amount, note="", mode="Cash",
                       pay_date=None):
        """Payment RECEIVED from customer — reduces their khata balance."""
        self.conn.execute(
            "INSERT INTO payments (customer_id, amount, date, mode, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer_id, amount, pay_date or date.today().isoformat(),
             mode or "Cash", note))
        self.conn.execute("UPDATE customers SET balance = balance - ? "
                          "WHERE id=?", (amount, customer_id))
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def customer_outstanding(self, customer_id):
        """Outstanding dues = the running khata balance, which is kept
        consistent by construction: credit bills add to it, payments and
        credit notes subtract from it."""
        c = self.get_customer(customer_id)
        return float(c["balance"]) if c else 0.0

    def dues_list(self):
        return self._rows("SELECT * FROM customers WHERE balance > 0.004 "
                          "ORDER BY balance DESC")

    def total_dues(self):
        r = self._one("SELECT COALESCE(SUM(balance), 0) t FROM customers "
                      "WHERE balance > 0")
        return r["t"]

    def customer_bills(self, cid, limit=100):
        return self._rows("SELECT * FROM bills WHERE customer_id=? "
                          "ORDER BY id DESC LIMIT ?", (cid, limit))

    def customer_payments(self, cid, limit=100):
        return self._rows("SELECT * FROM payments WHERE customer_id=? "
                          "ORDER BY id DESC LIMIT ?", (cid, limit))

    # -- bills --------------------------------------------------------------
    def next_bill_no(self):
        n = int(self.get_setting("bill_counter", "1"))
        self.set_setting("bill_counter", str(n + 1))
        prefix = self.get_setting("invoice_number_prefix", "BB-") or "BB-"
        return f"{prefix}{n:04d}"

    @staticmethod
    def compute_totals(items, bill_discount=0.0):
        """items: list of dicts with qty, price, line_discount, gst_percent.
        Line discounts are pre-GST; the flat bill discount applies post-GST;
        round_off rounds the payable to the nearest rupee."""
        subtotal = 0.0
        gst_total = 0.0
        gst_breakup = {}  # gst_percent -> taxable amount
        for it in items:
            taxable = float(it["qty"]) * float(it["price"]) - float(
                it.get("line_discount", 0))
            taxable = max(taxable, 0.0)
            gst = taxable * float(it.get("gst_percent", 0)) / 100.0
            subtotal += taxable
            gst_total += gst
            slab = float(it.get("gst_percent", 0))
            gst_breakup[slab] = gst_breakup.get(slab, 0.0) + taxable
        bill_discount = min(float(bill_discount), subtotal + gst_total)
        payable = subtotal + gst_total - bill_discount
        rounded = round(payable)
        return {
            "subtotal": round(subtotal, 2),
            "discount": round(bill_discount, 2),
            "gst_total": round(gst_total, 2),
            "round_off": round(rounded - payable, 2),
            "grand_total": round(rounded, 2),
            "gst_breakup": {k: round(v, 2) for k, v in gst_breakup.items()},
        }

    def _write_totals(self, bill_id, totals):
        self.conn.execute(
            "UPDATE bills SET subtotal=?, discount=?, gst_total=?, "
            "round_off=?, grand_total=? WHERE id=?",
            (totals["subtotal"], totals["discount"], totals["gst_total"],
             totals["round_off"], totals["grand_total"], bill_id))

    def create_bill(self, customer_id, payment_type, items,
                    bill_discount=0.0, bill_date=None, bill_no=None):
        """Finalize a bill: insert header+lines, decrement stock,
        add to customer balance when payment_type == 'Credit'."""
        totals = self.compute_totals(items, bill_discount)
        bdate = bill_date or date.today().isoformat()
        bno = bill_no or self.next_bill_no()
        cur = self.conn.execute(
            "INSERT INTO bills (bill_no, date, customer_id, payment_type, "
            "subtotal, discount, gst_total, round_off, grand_total, status, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'final', ?)",
            (bno, bdate, customer_id, payment_type, totals["subtotal"],
             totals["discount"], totals["gst_total"], totals["round_off"],
             totals["grand_total"], datetime.now().strftime("%Y-%m-%d %H:%M")))
        bill_id = cur.lastrowid
        for it in items:
            self.conn.execute(
                "INSERT INTO bill_items (bill_id, product_id, name, qty, unit,"
                " price, line_discount, gst_percent, line_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (bill_id, it.get("product_id"), it["name"], it["qty"],
                 it.get("unit", "pcs"), it["price"],
                 it.get("line_discount", 0), it.get("gst_percent", 0),
                 self._line_total(it)))
        if payment_type == "Credit" and customer_id:
            self.conn.execute("UPDATE customers SET balance = balance + ? "
                              "WHERE id=?", (totals["grand_total"], customer_id))
        for it in items:
            if it.get("product_id"):
                self.adjust_stock(it["product_id"], -float(it["qty"]),
                                  "bill", f"Bill {bno}")
        self.conn.execute(
            "INSERT INTO bill_history (bill_id, action, details, date) "
            "VALUES (?, 'created', ?, ?)",
            (bill_id, f"Bill {bno} finalized ({payment_type})",
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.conn.commit()
        return bill_id

    @staticmethod
    def _line_total(it):
        taxable = max(float(it["qty"]) * float(it["price"])
                      - float(it.get("line_discount", 0)), 0.0)
        return round(taxable * (1 + float(it.get("gst_percent", 0)) / 100), 2)

    def update_bill(self, bill_id, items, bill_discount=0.0):
        """Re-finalize an edited bill: reverse old stock, write new lines,
        re-apply credit balance delta, log history."""
        old = self.get_bill(bill_id)
        old_items = self.bill_items(bill_id)
        old_total = old["grand_total"]
        # Reverse old stock movements
        for it in old_items:
            if it["product_id"]:
                self.adjust_stock(it["product_id"], float(it["qty"]),
                                  "bill-edit",
                                  f"Reversal before editing bill {old['bill_no']}")
        # Replace lines
        self.conn.execute("DELETE FROM bill_items WHERE bill_id=?", (bill_id,))
        totals = self.compute_totals(items, bill_discount)
        for it in items:
            self.conn.execute(
                "INSERT INTO bill_items (bill_id, product_id, name, qty, unit,"
                " price, line_discount, gst_percent, line_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (bill_id, it.get("product_id"), it["name"], it["qty"],
                 it.get("unit", "pcs"), it["price"],
                 it.get("line_discount", 0), it.get("gst_percent", 0),
                 self._line_total(it)))
            if it.get("product_id"):
                self.adjust_stock(it["product_id"], -float(it["qty"]),
                                  "bill", f"Bill {old['bill_no']} (edited)")
        # Fix customer balance for credit bills
        if old["payment_type"] == "Credit" and old["customer_id"]:
            delta = totals["grand_total"] - old_total
            self.conn.execute("UPDATE customers SET balance = balance + ? "
                              "WHERE id=?", (delta, old["customer_id"]))
        self._write_totals(bill_id, totals)
        self.conn.execute(
            "INSERT INTO bill_history (bill_id, action, details, date) "
            "VALUES (?, 'edited', ?, ?)",
            (bill_id,
             f"Total changed {old_total:.2f} → {totals['grand_total']:.2f}",
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.conn.commit()
        return totals

    def get_bill(self, bill_id):
        b = self._one("SELECT b.*, c.name AS customer_name, c.phone AS "
                      "customer_phone, c.address AS customer_address, "
                      "c.is_wholesale AS customer_is_wholesale FROM bills b "
                      "LEFT JOIN customers c ON c.id=b.customer_id "
                      "WHERE b.id=?", (bill_id,))
        return b

    def bill_items(self, bill_id):
        return self._rows("SELECT * FROM bill_items WHERE bill_id=? "
                          "ORDER BY id", (bill_id,))

    def list_bills(self, search="", day=None, limit=300):
        sql = ("SELECT b.*, c.name AS customer_name FROM bills b "
               "LEFT JOIN customers c ON c.id=b.customer_id")
        params, conds = [], []
        if day:
            conds.append("b.date=?")
            params.append(day)
        if search:
            conds.append("(b.bill_no LIKE ? OR c.name LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY b.id DESC LIMIT ?"
        params.append(limit)
        return self._rows(sql, params)

    def delete_bill(self, bill_id):
        """Delete a bill (used for mistakes): reverse stock + credit balance."""
        b = self.get_bill(bill_id)
        if not b:
            return False
        for it in self.bill_items(bill_id):
            if it["product_id"]:
                self.adjust_stock(it["product_id"], float(it["qty"]),
                                  "bill-edit",
                                  f"Reversal for deleted bill {b['bill_no']}")
        if b["payment_type"] == "Credit" and b["customer_id"]:
            self.conn.execute("UPDATE customers SET balance = balance - ? "
                              "WHERE id=?", (b["grand_total"], b["customer_id"]))
        self.conn.execute("DELETE FROM bills WHERE id=?", (bill_id,))
        self.conn.commit()
        return True

    def bill_history(self, bill_id):
        return self._rows("SELECT * FROM bill_history WHERE bill_id=? "
                          "ORDER BY id DESC", (bill_id,))

    def log_bill_action(self, bill_id, action, details=""):
        self.conn.execute(
            "INSERT INTO bill_history (bill_id, action, details, date) "
            "VALUES (?, ?, ?, ?)",
            (bill_id, action, details,
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.conn.commit()

    # -- suppliers / purchases (stock in) -----------------------------------
    def list_suppliers(self, search=""):
        if search:
            like = f"%{search}%"
            return self._rows(
                "SELECT * FROM suppliers WHERE name LIKE ? OR phone LIKE ? "
                "ORDER BY name", (like, like))
        return self._rows("SELECT * FROM suppliers ORDER BY name")

    def get_supplier(self, sid):
        return self._one("SELECT * FROM suppliers WHERE id=?", (sid,))

    def add_supplier(self, name, phone="", address=""):
        cur = self.conn.execute(
            "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
            (name, phone, address))
        self.conn.commit()
        return cur.lastrowid

    def find_by_sku(self, sku):
        """Exact barcode/SKU match (case-insensitive). Used by the billing
        scanner fast-path: a USB scanner types the barcode + Enter."""
        s = (sku or "").strip()
        if not s:
            return None
        return self._one("SELECT * FROM products WHERE LOWER(sku)=LOWER(?)",
                         (s,))

    def create_purchase(self, supplier_id, date_str, ref_no, items):
        """Record a stock purchase: stock increases, purchase price becomes
        the weighted average of old stock and the new lot, movement logged."""
        for it in items:
            q = float(it["qty"])
            c = float(it["cost"])
            if q <= 0:
                raise ValueError(f"Quantity must be > 0 for '{it['name']}'.")
            if c < 0:
                raise ValueError(f"Cost cannot be negative for '{it['name']}'.")
        subtotal = sum(float(it["qty"]) * float(it["cost"]) for it in items)
        gst_total = sum(float(it["qty"]) * float(it["cost"])
                        * float(it.get("gst_percent", 0)) / 100.0
                        for it in items)
        grand = round(subtotal + gst_total, 2)
        cur = self.conn.execute(
            "INSERT INTO purchases (supplier_id, date, ref_no, subtotal, "
            "gst_total, grand_total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (supplier_id, date_str, ref_no or "", round(subtotal, 2),
             round(gst_total, 2), grand,
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        pid = cur.lastrowid
        for it in items:
            q, c = float(it["qty"]), float(it["cost"])
            gst = float(it.get("gst_percent", 0))
            line_total = round(q * c * (1 + gst / 100.0), 2)
            self.conn.execute(
                "INSERT INTO purchase_items (purchase_id, product_id, name, "
                "qty, unit, cost, gst_percent, line_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (pid, it.get("product_id"), it["name"], q,
                 it.get("unit", "pcs"), c, gst, line_total))
            if it.get("product_id"):
                p = self.get_product(it["product_id"])
                old_stock = float(p["stock"])
                old_cost = float(p["purchase_price"] or 0)
                new_stock = old_stock + q
                avg = ((old_stock * old_cost + q * c) / new_stock
                       if new_stock > 0 else c)
                self.conn.execute(
                    "UPDATE products SET purchase_price=?, gst_percent=? "
                    "WHERE id=?", (round(avg, 2), gst, it["product_id"]))
                self.adjust_stock(it["product_id"], q, "purchase",
                                  f"Purchase #{pid} {ref_no or ''}".strip())
        self.conn.commit()
        return pid

    def list_purchases(self, limit=200):
        return self._rows(
            "SELECT p.*, s.name AS supplier_name FROM purchases p "
            "LEFT JOIN suppliers s ON s.id=p.supplier_id "
            "ORDER BY p.id DESC LIMIT ?", (limit,))

    def get_purchase(self, pid):
        return self._one(
            "SELECT p.*, s.name AS supplier_name, s.phone AS supplier_phone "
            "FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier_id "
            "WHERE p.id=?", (pid,))

    def purchase_items(self, pid):
        return self._rows("SELECT * FROM purchase_items WHERE purchase_id=? "
                          "ORDER BY id", (pid,))

    def delete_purchase(self, pid):
        """Delete a purchase record and reverse its stock. The weighted
        purchase price is left as-is (reversing it exactly would need full
        lot history); stock is what matters for billing."""
        pur = self.get_purchase(pid)
        if not pur:
            return False
        for it in self.purchase_items(pid):
            if it["product_id"]:
                self.adjust_stock(it["product_id"], -float(it["qty"]),
                                  "purchase-reversal",
                                  f"Reversal of deleted purchase #{pid}")
        self.conn.execute("DELETE FROM purchases WHERE id=?", (pid,))
        self.conn.commit()
        return True

    # -- sales returns / credit notes ---------------------------------------
    def next_credit_note_no(self):
        n = int(self.get_setting("credit_note_counter", "1"))
        self.set_setting("credit_note_counter", str(n + 1))
        return f"CN-{n:04d}"

    def returned_qty(self, bill_item_id):
        r = self._one("SELECT COALESCE(SUM(qty), 0) q FROM return_items "
                      "WHERE bill_item_id=?", (bill_item_id,))
        return float(r["q"])

    def create_return(self, bill_id, items, note=""):
        """Record a sales return. items: list of dicts with bill_item_id and
        qty. Stock goes back up; a credit note is issued; for credit bills
        the customer's khata balance is reduced."""
        bill = self.get_bill(bill_id)
        if not bill:
            raise ValueError("Bill not found.")
        lines = []
        for it in items:
            bi = self._one("SELECT * FROM bill_items WHERE id=?",
                           (it["bill_item_id"],))
            if not bi or bi["bill_id"] != bill_id:
                raise ValueError("Return item does not belong to this bill.")
            q = float(it["qty"])
            if q <= 0:
                raise ValueError(f"Return qty must be > 0 for '{bi['name']}'.")
            max_q = float(bi["qty"]) - self.returned_qty(bi["id"])
            if q - max_q > 0.0001:
                raise ValueError(
                    f"Only {max_q:g} of '{bi['name']}' can still be returned.")
            taxable = max(q * float(bi["price"])
                          - float(bi["line_discount"] or 0), 0.0)
            gst = taxable * float(bi["gst_percent"] or 0) / 100.0
            lines.append((bi, q, taxable, gst))
        if not lines:
            raise ValueError("Nothing to return.")
        subtotal = round(sum(t for _, _, t, _ in lines), 2)
        gst_total = round(sum(g for _, _, _, g in lines), 2)
        total = round(subtotal + gst_total, 2)
        cn_no = self.next_credit_note_no()
        cur = self.conn.execute(
            "INSERT INTO returns (bill_id, credit_note_no, date, customer_id,"
            " subtotal, gst_total, total, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bill_id, cn_no, date.today().isoformat(), bill["customer_id"],
             subtotal, gst_total, total, note or "",
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        rid = cur.lastrowid
        for bi, q, taxable, gst in lines:
            line_total = round(taxable + gst, 2)
            p = (self.get_product(bi["product_id"])
                 if bi["product_id"] else None)
            self.conn.execute(
                "INSERT INTO return_items (return_id, bill_item_id, "
                "product_id, name, sku, qty, unit, price, line_discount, "
                "gst_percent, line_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?)",
                (rid, bi["id"], bi["product_id"], bi["name"],
                 (p or {}).get("sku", ""), q, bi["unit"], bi["price"],
                 bi["line_discount"], bi["gst_percent"], line_total))
            if bi["product_id"]:
                self.adjust_stock(bi["product_id"], q, "return",
                                  f"Credit note {cn_no} (bill {bill['bill_no']})")
        if bill["payment_type"] == "Credit" and bill["customer_id"]:
            self.conn.execute("UPDATE customers SET balance = balance - ? "
                              "WHERE id=?", (total, bill["customer_id"]))
        self.log_bill_action(
            bill_id, "returned",
            f"Credit note {cn_no}: {total:.2f} credited "
            f"({len(lines)} line(s))")
        self.conn.commit()
        return rid

    def list_returns(self, limit=200):
        return self._rows(
            "SELECT r.*, b.bill_no, c.name AS customer_name FROM returns r "
            "LEFT JOIN bills b ON b.id=r.bill_id "
            "LEFT JOIN customers c ON c.id=r.customer_id "
            "ORDER BY r.id DESC LIMIT ?", (limit,))

    def get_return(self, rid):
        return self._one(
            "SELECT r.*, b.bill_no, b.date AS bill_date, "
            "c.name AS customer_name, c.phone AS customer_phone, "
            "c.address AS customer_address FROM returns r "
            "LEFT JOIN bills b ON b.id=r.bill_id "
            "LEFT JOIN customers c ON c.id=r.customer_id "
            "WHERE r.id=?", (rid,))

    def return_items(self, rid):
        return self._rows("SELECT * FROM return_items WHERE return_id=? "
                          "ORDER BY id", (rid,))

    # -- dashboard / reports ------------------------------------------------
    def sales_on(self, day):
        r = self._one("SELECT COUNT(*) n, COALESCE(SUM(grand_total),0) t "
                      "FROM bills WHERE date=?", (day,))
        return r["n"], r["t"]

    def sales_between(self, start, end):
        r = self._one("SELECT COUNT(*) n, COALESCE(SUM(grand_total),0) t, "
                      "COALESCE(SUM(discount),0) d, COALESCE(SUM(gst_total),0) g"
                      " FROM bills WHERE date BETWEEN ? AND ?", (start, end))
        return r

    def daywise_sales(self, start, end):
        return self._rows(
            "SELECT date, COUNT(*) n, SUM(grand_total) t, SUM(gst_total) g "
            "FROM bills WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
            (start, end))

    def gst_summary(self, start, end):
        rows = self._rows(
            "SELECT bi.gst_percent, SUM(bi.qty*bi.price - bi.line_discount) taxable,"
            " SUM(bi.line_total - (bi.qty*bi.price - bi.line_discount)) gst "
            "FROM bill_items bi JOIN bills b ON b.id=bi.bill_id "
            "WHERE b.date BETWEEN ? AND ? GROUP BY bi.gst_percent "
            "ORDER BY bi.gst_percent", (start, end))
        return rows

    def top_products(self, start, end, limit=10):
        return self._rows(
            "SELECT bi.name, bi.unit, SUM(bi.qty) qty, SUM(bi.line_total) total "
            "FROM bill_items bi JOIN bills b ON b.id=bi.bill_id "
            "WHERE b.date BETWEEN ? AND ? GROUP BY bi.product_id, bi.name "
            "ORDER BY qty DESC LIMIT ?", (start, end, limit))

    def profit_estimate(self, start, end):
        """Sale price minus purchase price per line (approx; ignores stock
        timing and discounts beyond line totals)."""
        rows = self._rows(
            "SELECT bi.qty, bi.price, bi.line_discount, p.purchase_price "
            "FROM bill_items bi JOIN bills b ON b.id=bi.bill_id "
            "LEFT JOIN products p ON p.id=bi.product_id "
            "WHERE b.date BETWEEN ? AND ?", (start, end))
        profit = 0.0
        for r in rows:
            sold = float(r["qty"]) * float(r["price"]) - float(r["line_discount"])
            cost = float(r["qty"]) * (float(r["purchase_price"] or 0))
            profit += sold - cost
        return profit

    def backup_to(self, dest: Path):
        """Copy the live DB file to dest (one-click backup)."""
        import shutil
        dest = Path(dest)
        self.conn.commit()
        shutil.copy2(self.path, dest)
        return dest

    def close(self):
        self.conn.close()
