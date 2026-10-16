# BillBook — Wholesale Billing App

A desktop billing application for a small Indian wholesale shop: fast counter
billing with a saved product catalog, GST invoices you can print, customer
khata (ledger), stock management, and sales reports — all offline.

Built with **Python + CustomTkinter** (dark mode default, light toggle) and
**SQLite** (Python stdlib, no server needed). Invoices are generated as
proper **PDFs** (reportlab) and printed **directly through Windows' own
print system** — pick any installed printer from a dropdown, no browser and
no Chrome extension needed.

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
  - Keyboard shortcuts for fast counters: **F2** new bill tab, **F3** jump to
    product search, **Enter** adds a line, **+ / −** adjust the selected
    line's quantity, **Esc** clears the entry row, **Ctrl+S** finalize,
    **Ctrl+P** print/preview.
  - **Duplicate products merge** into one line; **low-stock warnings** (⚠)
    appear on lines that would push stock to/below the threshold; inline
    warnings (not popups) flag a missing customer or payment type in the
    sticky totals footer, which always shows subtotal, GST, discount,
    round-off, and the grand total.
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
- **Invoices (PDF)** — proper GST invoice layout as a **PDF** with GST slab
  breakup (CGST/SGST), shop header, and signature lines. Reprint any past
  bill from the Invoices screen. **Bills stay editable after finalizing**:
  reopen a completed bill, change items/quantities/discounts, print the
  corrected bill — stock and khata are reversed and re-applied, and the edit
  is recorded in bill history. PDFs are saved per bill under
  `billbook_data/invoices/<bill_no>_invoice.pdf` for records.
- **Universal printing (no browser, no extension)** — invoices print
  **directly** through Windows' print system:
  - The Print dialog lists **all installed printers** in a dropdown (OS
    default pre-selected) plus a copies field.
  - After every saved bill, a **"Print invoice?"** offer appears (Print /
    Preview / Skip) with a "Remember my choice" option, so the counter can
    auto-print every bill.
  - Print and Preview buttons also live on the billing screen; the Invoices
    screen reprints any past bill with the same flow.
  - On non-Windows (or if printing fails), the app honestly opens the PDF
    for manual printing instead of claiming the job printed.
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

## Run with Docker (optional)

Handy on Linux dev machines or anywhere without a Python install — the
Windows `.exe` above is still the recommended path for the shop PC
(Docker Desktop on Windows needs an extra X server like VcXsrv/X410 for
GUI apps, so the `.exe` is simpler there).

On Linux:

```bash
docker compose build
xhost +local:docker      # allow the container to use your display (per session)
docker compose up        # launches BillBook in a window
```

Data (SQLite db + invoice PDFs) lives in the `billbook_data` Docker volume,
so bills survive container rebuilds. To start fresh, `docker volume rm
billbook_data`. After code changes, rebuild with `docker compose build`.

## Project structure

| File | What it does |
|---|---|
| `main.py` | Entry point — loads theme, opens the app window |
| `db.py` | SQLite schema + all data access: products, customers/khata, bills, bill items, payments, stock movements, bill history, settings; billing math (`compute_totals`) |
| `invoices.py` | Invoice generation as **PDF** (reportlab, A4 + 80mm thermal) + print orchestration: builds the PDF per bill, saves it under `billbook_data/invoices/` |
| `printing.py` | Universal print engine: PDF rendering, printer enumeration (`win32print` on Windows), direct OS printing via `os.startfile(path, "print")`, graceful PDF-only fallback elsewhere |
| `ui.py` | All CustomTkinter screens: dashboard, billing (multi-tab), products, stock, customers, invoices, reports, backup, settings, print dialog |
| `sample_products.csv` | 14 realistic Indian wholesale FMCG rows for demo import |
| `build_exe.bat` | One-click Windows build (PyInstaller) |
| `requirements.txt` | `customtkinter`, `reportlab` (PDF invoices) |

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

- **Direct printing was developed and tested on Linux only** — the print
  pipeline degrades gracefully (saves/opens the PDF) where `win32print` is
  unavailable. On the Windows shop PC it uses the OS print path
  (`os.startfile(path, "print")`), which was **not tested against a real
  printer**; verify with one test print on the shop's printer first.
- No barcode-scanner integration yet — SKU is a text field; a USB scanner
  that types digits works with the search box, but there's no camera scanning.
- Invoices print via the OS print dialog (spooler), not raw thermal-printer
  ESC/POS commands — fine for A4 and 80mm paper, but no raw-printer control.
- Single-user, single-PC: SQLite lives in one file; no multi-counter sync.
- Profit estimate is sale − purchase per line only; it ignores overheads,
  wastage, and purchase-price changes over time.
- Every bill requires a saved customer (walk-in bills must pick one) — dues
  need a customer record to track against.

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

**Why generate invoices as PDF + direct OS printing instead of HTML in the
browser?** The original build opened a self-contained HTML invoice in the
browser for Ctrl+P printing. That worked, but it added a manual step at the
counter and depended on the browser's print dialog every time. The current
flow renders the same invoice (shop header, GST slabs, totals) to PDF with
reportlab — A4 and 80mm thermal layouts — and on Windows hands it to the OS
print spooler via `os.startfile(path, "print")`, with the printer chosen
from `win32print`'s installed-printer list (temporarily set as default so
the call targets the right device, then restored). No browser, no Chrome
extension, no raw ESC/POS driver work. The honest trade-off: direct printing
was only exercised on Linux in "PDF saved" mode — the Windows print path
needs one real test print on the shop's printer. And `print_pdf` never claims
success it didn't get: on failure the app opens the PDF for manual printing.

**Keyboard-first billing UX:** counters bill fast, so the billing screen is
driven by keys — F2 new tab, F3 focus search, Enter add line, +/− adjust
selected-line quantity, Esc clear the entry row, Ctrl+S finalize, Ctrl+P
print. Shortcut hints are printed on the buttons themselves and in a footer
label. Inline warnings (missing customer / payment type) live in the sticky
totals footer instead of popping dialogs mid-flow. Small touches with real
counter value: adding the same product twice merges the line instead of
duplicating it, and a ⚠ marker appears on lines that would push stock to or
below the low-stock threshold.

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
