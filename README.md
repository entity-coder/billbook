# BillBook — Wholesale Billing App

A desktop billing application for a small Indian wholesale shop: fast counter
billing with a saved product catalog, GST invoices you can print, customer
khata (ledger), stock management, and sales reports — all offline.

Built with **Python + CustomTkinter** (dark mode default, light toggle) and
**SQLite** (Python stdlib, no server needed). Printing works through
generated HTML invoices opened in your default browser (Ctrl+P to print).

> **Shop PC note:** this repo ships source code plus a one-click
> `build_exe.bat`. Run that batch file **once on a Windows PC** to compile
> `BillBook.exe`. A Windows `.exe` can only be built on Windows — it was
> **not** compiled or tested on Windows during development (the author works
> on Linux).

## Features

- **Dashboard** — today's sales (bill count + total), pending dues, low-stock
  alerts, top-selling products of the last 7 days, total stock value.
- **Billing (multi-bill tabs)** — open several bills at once: park one
  customer's bill, serve the next, switch tabs freely. Each tab keeps its own
  customer, items, and totals until finalized or discarded.
  - Customer (required — pick from saved customers or create new) and payment
    type (**Cash / UPI / Credit**, required) are chosen first.
  - Search-as-you-type product picker, quantity, per-line discount, per-bill
    discount.
  - **Wholesale/Retail toggle** — wholesale price or retail price is applied
    automatically (defaults from the customer's type).
  - Per-line GST breakup, round-off to the nearest rupee, sequential bill
    numbers (`BB-0001`, `BB-0002`, …).
  - Keyboard shortcuts for fast counters: **F2** new bill tab, **Enter**
    adds a line, **Ctrl+S** finalize, **Ctrl+P** print/preview.
- **Product catalog** — name, SKU/barcode, purchase / wholesale / retail
  price, unit (pcs, kg, bag, box, litre…), GST %, stock, low-stock threshold,
  supplier. Add/edit/delete, search, **bulk import/export via CSV**
  (`sample_products.csv` included with 14 realistic FMCG rows).
- **Stock management** — dedicated Stock IN screen (qty received, note for
  supplier) and Stock OUT (damage/returns), low-stock alerts, total stock
  value, and a full movement log (audit trail).
- **Customer ledger (khata)** — per-customer outstanding dues, record
  payments received (reduces dues), dues reminder view, per-customer
  statement (bills + payments).
- **Invoices** — proper GST invoice layout as printable HTML with GST slab
  breakup (CGST/SGST), shop header, and signature lines. Reprint any past
  bill. **Bills stay editable after finalizing**: reopen a completed bill,
  change items/quantities/discounts, print the corrected bill — stock and
  khata are reversed and re-applied, and the edit is recorded in bill history.
- **Print customization** — show/hide GSTIN, item codes, discount column;
  header/footer notes; accent color; **A4 or thermal 80mm** paper; **live
  preview** before printing.
- **Reports** — day-wise / monthly sales totals, GST summary by slab, profit
  estimate (sale price − purchase price per line), top products.
- **Backup/restore** — one-click backup of the database file; restore from a
  backup with a safety check that it is a BillBook database.
- **Shop profile** — one-time setup for shop name, tagline, address, phone,
  GSTIN — printed on every bill header.

## How to run (developers)

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python main.py
```

Data is stored in `billbook_data/billbook.db` next to the source (or next to
`BillBook.exe` in the packaged build). To try it instantly: open **Products**
→ **Import CSV** → choose `sample_products.csv`, then open **Billing**.

## Build the Windows .exe (shop PC)

1. On the **Windows** shop PC, install Python 3.10+ from python.org (tick
   **"Add python.exe to PATH"** during setup).
2. Copy this project folder to the shop PC and double-click **`build_exe.bat`**.
   It installs `customtkinter` + `pyinstaller` and compiles the app —
   takes a few minutes.
3. Done: `dist\BillBook.exe` is the standalone app. Copy it to the Desktop.
   Afterwards the shop PC **never needs Python again**.
4. Keep the `billbook_data` folder next to the `.exe` — that is your data.
   Use the in-app **Backup** screen regularly (pen drive / Drive folder).

## Project structure

| File | What it does |
|---|---|
| `main.py` | Entry point — loads theme, opens the app window |
| `db.py` | SQLite schema + all data access: products, customers/khata, bills, bill items, payments, stock movements, bill history, settings; billing math (`compute_totals`) |
| `invoices.py` | Generates the printable GST invoice as standalone HTML honoring shop profile + print preferences; opens it in the default browser |
| `ui.py` | All CustomTkinter screens: dashboard, billing (multi-tab), products, stock, customers, invoices, reports, backup, settings, print dialog |
| `sample_products.csv` | 14 realistic Indian wholesale FMCG rows for demo import |
| `build_exe.bat` | One-click Windows build (PyInstaller) |
| `requirements.txt` | `customtkinter` — the only third-party dependency |

## How billing math works

- **Line total** = (qty × rate − line discount) + GST on that amount.
  Line discounts are pre-GST (standard practice).
- **Bill discount** is a flat ₹ amount applied *after* GST, then the payable
  is rounded to the nearest rupee (round-off line shown on the bill).
- **Credit** bills add the grand total to the customer's khata balance;
  recording a payment reduces it.
- Finalizing a bill decrements stock and writes stock movements; editing a
  finalized bill reverses the old stock/credit effect first, then re-applies
  the new one, logging everything to bill history.

## Limitations (honest)

- No barcode-scanner integration yet — SKU is a text field; a USB scanner
  that types digits works with the search box, but there's no camera scanning.
- Invoices print via the browser (Ctrl+P), not direct thermal-printer ESC/POS
  commands — fine for A4 and for 80mm paper through the browser's paper-size
  setting, but no raw-printer control.
- Single-user, single-PC: SQLite lives in one file; no multi-counter sync.
- Profit estimate is sale − purchase per line only; it ignores overheads,
  wastage, and purchase-price changes over time.
- Customer "Walk-in" bills (no saved customer) can't go on credit tracking —
  dues need a saved customer.

## Interview notes

**What is this project?** BillBook is an offline-first desktop billing app
for a wholesale shop: product catalog, fast multi-tab billing with GST,
customer khata, stock management, printable GST invoices, reports, and
one-click backup — packaged as a single Windows `.exe` so a non-technical
shop owner can run it with zero setup.

**Why CustomTkinter instead of Tkinter/PyQt/Electron?** Plain Tkinter looks
dated and styling it is painful; PyQt licensing is murky for a sellable app
(PyQt is GPL/commercial, PySide is LGPL but heavier); Electron would mean
shipping a whole browser for a local CRUD app. CustomTkinter gives a modern
dark/light UI on top of stdlib Tkinter with one `pip install`, and
PyInstaller bundles it into a single `.exe` — the shop PC installs nothing.

**Why SQLite instead of MySQL/Postgres?** The shop has one PC and no IT
staff. SQLite is a single file: zero server setup, zero maintenance, and
backup is literally copying a file. The trade-off is no multi-user sync —
accepted deliberately, because the requirement is one billing counter, and
complexity that the user can't maintain is a liability, not a feature.

**Why generate invoices as HTML opened in the browser instead of printing
directly?** Talking to printers from Python (especially thermal printers)
is platform-specific and fragile. Every PC already has a browser with a
mature print dialog (margins, paper size, preview). Generating a
self-contained HTML file with print CSS gives a pixel-faithful GST invoice
on A4 *and* 80mm thermal with ~60 lines of code and zero driver headaches.
The honest limitation: no raw ESC/POS control.

**Key design decisions in the code:**
- *Billing math lives in one place* (`DB.compute_totals`): line discounts
  pre-GST, flat bill discount post-GST, round to nearest rupee. Every screen
  (billing tab, edit flow, invoice) uses the same function, so totals can't
  drift between screens.
- *Draft bill tabs are in-memory; only finalized bills touch the DB.* This
  makes "park a bill, serve the next customer" trivial and discard free —
  nothing half-written pollutes stock or khata.
- *Editing a finalized bill reverses then re-applies.* Stock and credit
  balance are undone from the old version before the new version is written,
  and each step is logged to `bill_history` — so the audit trail survives
  corrections instead of being silently rewritten.
- *Settings are a key/value table*, not a config file: the shop owner edits
  them in the Settings screen and they apply immediately, including print
  preferences with a live preview.

**Trade-offs / what I'd do differently:** I'd add a proper migration system
if the schema ever changes (currently `CREATE TABLE IF NOT EXISTS` only);
I'd move invoice templates to user-editable files for shops that want
custom layouts; and for multiple counters I'd replace SQLite with a small
local server (e.g. FastAPI + SQLite/Postgres) rather than bolting sync onto
a file.

**How I'd extend it:** barcode-scanner input mode (USB scanners act as
keyboards, so it's mostly a "scan → instant add" UX), UPI QR code on the
invoice for the grand total, per-day cash-register closing (denomination
count), supplier purchase ledger mirroring the customer khata, and GST
filing export (GSTR-1 style CSV of outward supplies by slab — the
`gst_summary` query already computes the needed numbers).
