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
    product search, **F4** choose customer, **Enter** adds a line,
    **Tab** walks entry row → card qty → rate → discount, **Esc** clears the
    entry row (or closes the customer picker), **Ctrl+S** finalize,
    **Ctrl+P** print/preview. Every field is typeable — no mouse needed for
    a full bill.
  - **Autocomplete dropdown** — typing any letter in the product search
    opens a live dropdown under the field, ranked by relevance
    (name-starts-with → name-contains → SKU match), showing name + SKU +
    price. **Up/Down** moves the highlight, **Enter** picks the highlighted
    product, **Esc** closes the dropdown, click also picks. Typing never
    loses focus.
  - **Duplicate products merge** into one line; **low-stock warnings** (⚠)
    appear on lines that would push stock to/below the threshold; inline
    warnings (not popups) flag a missing customer or payment type in the
    sticky totals footer, which always shows subtotal, GST, discount,
    round-off, and the grand total.
  - **Barcode scan → instant add** — a USB scanner types the barcode + Enter.
    If the typed text exactly matches a product's SKU/barcode
    (case-insensitive), the line is added **immediately** with qty 1
    (merging with the existing line if already on the bill) — no dropdown.
    Anything else falls back to the normal autocomplete dropdown.
  - **Repeat last bill** — one button picks a customer and reloads *their*
    most recent bill's items into a fresh tab at **current** prices (qty as
    billed), with a note showing which bill it was loaded from. Handy for
    regular weekly orders.
- **Product catalog** — name, SKU/barcode, purchase / wholesale / retail
  price, unit (pcs, kg, bag, box, litre…), GST %, stock, low-stock threshold,
  supplier. Add/edit/delete (with validation: name required, numeric prices
  and stock; delete is blocked for products on saved bills), search,
  **bulk import/export via CSV** (`sample_products.csv` included with 14
  realistic FMCG rows). The add/edit dialog is keyboard-friendly: it opens
  with the name field focused, **Enter** saves, **Esc** closes.
- **Purchases (stock in)** — wholesale shops buy stock from suppliers, so
  there is a dedicated **Purchases** screen: pick or create a supplier (name,
  phone), enter the date and supplier invoice/ref number, then add items
  (product picker, qty, purchase cost/unit, GST%). Saving **increases
  stock**, logs the movement, and sets each product's purchase price to the
  **weighted average** of old stock and the new lot. Past purchases are
  listed with a view dialog; deleting one **reverses the stock** (with
  confirmation). Validates qty > 0 and cost ≥ 0.
- **Stock management** — dedicated Stock IN screen (qty received, note for
  supplier) and Stock OUT (damage/returns), low-stock alerts, total stock
  value, and a full movement log (audit trail).
- **Customer ledger (khata)** — per-customer outstanding dues, record
  payments received (reduces dues), dues reminder view, per-customer
  statement (bills + payments).
  - **Collect payment** — each customer row shows total outstanding; the
    dialog takes amount, date, mode (**Cash / UPI / Bank**) and a note.
    The amount **cannot exceed the outstanding dues** (partial payments are
    fine). Recording prints a small **payment receipt PDF** (A4 + thermal).
    Outstanding = credit bills − payments received − credit notes, kept
    consistent in the khata balance.
- **Invoices (PDF)** — proper GST invoice layout as a **PDF** with GST slab
  breakup (CGST/SGST), shop header, and signature lines. Reprint any past
  bill from the Invoices screen. **Bills stay editable after finalizing**:
  reopen a completed bill, change items/quantities/discounts, print the
  corrected bill — stock and khata are reversed and re-applied, and the edit
  is recorded in bill history. PDFs are saved per bill under
  `billbook_data/invoices/<bill_no>_invoice.pdf` for records.
- **Sales returns / credit notes** — the Invoices screen has a **Return**
  button per bill: a dialog lists the bill's items with billed qty and
  already-returned qty, and you enter the return qty per line (capped so the
  same item can never be returned twice). Confirming **adds the stock back**,
  creates a numbered **credit note** (`CN-0001`, …), reduces the customer's
  khata dues for credit bills, and generates a printable **credit-note PDF**
  (A4 + thermal, honoring your invoice-design settings).
- **WhatsApp bill share** — the Invoices screen has a **WhatsApp** button per
  bill: it builds a text summary (shop name, bill no/date, item lines with
  qty and amounts, total, payment type, balance due for credit bills) and
  opens `wa.me/<customer-phone>` with the message ready to send. If the
  customer has no phone saved, it prompts to add one first. Indian numbers
  are normalized automatically (10 digits → `91` prefix). No API keys, no
  extra dependencies.
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
- **Invoice Design** (new sidebar screen) — make the invoice fully yours,
  with an instant live preview (renders the real PDF when PyMuPDF is
  available, otherwise a close approximation):
  - **Header**: toggle tagline / address / phone / GSTIN individually, and
    upload a shop **logo** (PNG/JPG — shown on the invoice header; stored
    safely in `billbook_data/logos/`).
  - **Title & text**: editable invoice title ("TAX INVOICE" / "BILL" /
    "RECEIPT"…), Compact / Standard / Large text size, accent color.
  - **Columns & tables**: GST slab breakup table, HSN column (uses the
    product SKU as the HSN value; A4 only — too narrow for thermal),
    discount column, item codes.
  - **Bill details**: round-off line, customer address, CREDIT — due badge,
    signature lines (A4 only).
  - **Footer**: multi-line **terms & conditions**, thank-you message
    (toggle + editable text).
  - **Paper & numbering**: default A4 / thermal 80mm, default copies,
    editable invoice number **prefix** (e.g. `BB-`, `INV/`) — the next bill
    number previews live as you type.
  - Every choice saves to the database and applies to **every invoice from
    then on** — new prints, reprints, and previews. Missing settings fall
    back to the original defaults, so old databases keep working.
- **Reports** — day-wise / monthly sales totals, GST summary by slab, profit
  estimate (sale price − purchase price per line), top products.
- **Backup/restore** — one-click backup writes a timestamped `.zip`
  (`billbook_backup_YYYYMMDD_HHMMSS.zip`) with the database, all saved
  invoice PDFs and the shop logo to any folder you pick (pen drive / Drive).
  Restore accepts a `.zip` or a legacy `.db`, validates it is a BillBook
  database, and always saves a safety copy of the current data first
  (`billbook_data/backups/auto_before_restore_…db`) — then asks you to
  restart the app.
- **Automatic backup on exit** — every time the app closes, it silently
  writes a timestamped backup (`billbook_auto_backup_YYYYMMDD_HHMMSS.zip`,
  same contents as a manual backup) to the auto-backup folder, then closes
  normally. It is ON by default; toggle it or change the folder from the
  **Backup** screen ("Back up automatically every time the app closes" /
  "Choose folder…"). Default folder is `billbook_data/backups/`. Only the
  last **14** automatic backups are kept — older ones are deleted, manual
  backups are never touched.
- **Self-update from GitHub** — on startup the app quietly checks the
  public `entity-coder/billbook` repo for a newer commit (background
  thread; offline or failure = silently skipped, the app runs normally).
  If an update exists, a small non-intrusive **"⬆ Update available"**
  button appears in the sidebar — never forced, never interrupts billing.
  Clicking it asks for confirmation, downloads the new source ZIP, and
  writes an `apply_update.bat` that runs *after the app exits* (Windows
  can't overwrite a running `.exe`): it copies the new files over the app
  folder **excluding `billbook_data/`**, re-runs the PyInstaller build, and
  restarts the app. If the build fails, the old `.exe` is left untouched
  and the log is shown. `version.txt` next to the app records the running
  commit. A manual **"Check for updates"** button lives in Settings. The backup never blocks shutdown: if it fails
  (disk full, folder unreachable) the app still closes quietly.
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
| `db.py` | SQLite schema + all data access: products, customers/khata, bills, bill items, payments, stock movements, bill history, suppliers, purchases, returns/credit notes, settings; billing math (`compute_totals`) |
| `invoices.py` | Invoice generation as **PDF** (reportlab, A4 + 80mm thermal) + print orchestration: builds the PDF per bill, saves it under `billbook_data/invoices/` |
| `printing.py` | Universal print engine: PDF rendering, printer enumeration (`win32print` on Windows), direct OS printing via `os.startfile(path, "print")`, graceful PDF-only fallback elsewhere |
| `ui.py` | Core screens: dashboard, billing (multi-tab), products, stock, customers, invoices, reports, invoice design, backup, settings |
| `print_ui.py` | Print offer dialog, print settings dialog, invoice live preview, accent palette (split out of `ui.py` to keep modules small) |
| `purchases_ui.py` | Purchases screen: supplier picker, purchase entry, purchase history |
| `returns_ui.py` | Sales-return dialog (credit notes) + WhatsApp bill sharing |
| `backup.py` | Backup engine + Backup & restore screen: manual timestamped zips, restore with safety copy, silent auto-backup on exit with 14-backup retention |
| `updater.py` | Self-update from GitHub: background latest-commit check, source-ZIP download + staging, `apply_update.bat` generator (copies new files excluding `billbook_data/`, rebuilds the `.exe` after exit, restarts) |
| `version.txt` | Commit SHA of the running build — written at push/build time; the updater compares it with GitHub's latest |
| `sample_products.csv` | 14 realistic Indian wholesale FMCG rows for demo import |
| `build_exe.bat` | One-click Windows build (PyInstaller) |
| `requirements.txt` | `customtkinter`, `reportlab` (PDF invoices) |

## How billing math works

- **Line total** = (qty × rate − line discount) + GST on that amount.
  Line discounts are pre-GST (standard practice).
- **Bill discount** is a flat ₹ amount applied *after* GST, then the payable
  is rounded to the nearest rupee (round-off line shown on the bill).
- **Credit** bills add the grand total to the customer's khata balance;
  recording a payment reduces it; a credit note (sales return) on a credit
  bill reduces it too. Outstanding = credit bills − payments − credit notes.
- **Purchases** increase stock and re-price inventory to the weighted
  average of old stock and the new lot; deleting a purchase reverses the
  stock (the averaged cost is left as-is).
- Finalizing a bill decrements stock and writes stock movements; editing a
  finalized bill reverses the old stock/credit effect first, then re-applies
  the new one, logging everything to bill history.

## Limitations (honest)

- **Direct printing was developed and tested on Linux only** — the print
  pipeline degrades gracefully (saves/opens the PDF) where `win32print` is
  unavailable. On the Windows shop PC it uses the OS print path
  (`os.startfile(path, "print")`), which was **not tested against a real
  printer**; verify with one test print on the shop's printer first.
- **Barcode scanning** works with any USB scanner that types the barcode +
  Enter (instant-add on exact SKU match). There is no *camera* scanning —
  that would need OpenCV/a camera dependency the shop PC doesn't have.
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
driven by keys — F2 new tab, F3 focus search, F4 customer picker (Esc closes
it), Enter adds a line, Tab walks the entry row then each card's
qty → rate → discount fields, Ctrl+S finalize, Ctrl+P print. The focused
field gets an accent border so the cashier always knows where they are, and
committing a card field (Enter or focus-out) updates the line total in place
without rebuilding the card — focus is never stolen mid-flow. Shortcut hints
are printed on the buttons themselves and in a footer label. Inline warnings
(missing customer / payment type) live in the sticky totals footer instead
of popping dialogs mid-flow. Small touches with real counter value: adding
the same product twice merges the line instead of duplicating it, and a ⚠
marker appears on lines that would push stock to or below the low-stock
threshold.

**Product cards:** each bill line is its own bordered card, not a table row —
product name prominent, SKU/unit muted, a plain typed quantity field (no
+/− steppers), editable rate and line-discount fields right on the card,
bold line total, × remove button, and the low-stock ⚠ badge when relevant.
Clicking a card selects it (accent border); double-click opens the full line
editor; adding a duplicate merges into the existing card and flashes it so
the cashier sees where it went. An empty bill shows a clean "Bill is empty"
placeholder.

**Invoice design system:** every visual/textual part of the invoice is a
database setting, edited in the **Invoice Design** sidebar screen with a
live preview. The preview renders the *actual* PDF via PyMuPDF when it's
installed (zero new hard dependency — it falls back to a widget
approximation, the same renderer the Print dialog uses). Toggles cover
tagline/address/phone/GSTIN, GST slab table, HSN column (SKU doubles as
the HSN value — Indian retail shops commonly print SKU in that column),
round-off line, customer address, the CREDIT — due badge, and signature
lines; text fields cover the invoice title, multi-line terms & conditions,
and the thank-you message; Compact/Standard/Large scale the PDF font
sizes; the logo is uploaded once, copied into `billbook_data/logos/`, and
drawn in the PDF header with graceful fallback if the file goes missing.
The 80mm thermal layout hides what can't fit (HSN column, signature
lines) rather than breaking the layout. Backward compatibility is by
construction: `print_prefs()` fills missing keys with the old defaults, so
an existing `billbook.db` from the shop PC keeps working, and the invoice
number prefix (`invoice_number_prefix`, default `BB-`) only affects newly
generated numbers — old bills keep theirs.

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
- *Bill lines are cards, not table rows.* A ttk Treeview was cheaper, but at a
  busy counter the cashier needs big touch/click targets and per-line editing
  without opening dialogs — so each line is a bordered `CTkFrame` card with
  a typed quantity field (steppers were removed: typing is faster and keeps
  the flow keyboard-only), rate/discount entries (committed on Enter /
  focus-out, with revert-on-invalid and in-place total refresh so focus is
  never stolen), and remove button. Selection state is a plain index in
  the tab's widget dict; merge-flash is a 500 ms `after()` callback guarded
  by `winfo_exists()` so tab switches can't crash it.
- *Automatic on-exit backup.* Closing the window (`WM_DELETE_WINDOW`) runs a
  silent backup first — same zip contents as a manual backup, written to a
  configurable folder (default `billbook_data/backups/`), with a 14-file
  retention policy that only prunes files with the auto-backup filename
  prefix so manual backups are never deleted. The whole path is wrapped so
  it can never block shutdown: no dialogs, commit failures and missing
  folders are caught, and a bad custom folder falls back to the default.
  It's a user setting (`auto_backup_on_exit`), not hardcoded, because the
  shop owner should be able to turn it off — e.g. on a metered machine.
- *Self-update that respects the counter.* A billing PC can't afford a
  surprise restart mid-sale, so the update check runs in a daemon thread
  2.5 s after startup (never blocks the UI; offline = silently skipped)
  and the only UI is a small sidebar badge. Applying it is a two-phase
  dance because Windows can't overwrite a running `.exe`: Python downloads
  + stages the source ZIP and writes `apply_update.bat`, then quits; the
  bat waits on the PID, `robocopy`s the new tree over the app folder
  *excluding* `billbook_data/`, re-runs the exact PyInstaller command, and
  only swaps the exe on build success — a failed build leaves the old
  version working and opens the log. `version.txt` is the whole versioning
  scheme: one SHA, compared against the GitHub API, no auth needed.
- *Autocomplete that doesn't fight the keyboard.* The product search shows
  a live dropdown ranked by relevance (name-starts-with, then contains,
  then SKU) rather than DB order. Arrow keys move a highlight index,
  Enter picks, Esc closes — all handled in widget-level bindings that
  return `"break"` so they never leak into the app-level shortcuts, and
  the dropdown never takes focus away from typing. Keeping "Enter adds
  top match" when the dropdown is closed preserves the old fast path.

**Trade-offs / what I'd do differently:** I'd add a proper migration system
if the schema ever changes (currently `CREATE TABLE IF NOT EXISTS` only);
I'd move invoice templates to user-editable files for shops that want
custom layouts; and for multiple counters I'd replace SQLite with a small
local server (e.g. FastAPI + SQLite/Postgres) rather than bolting sync onto
a file.

**How I'd extend it:** UPI QR code on the invoice for the grand total,
per-day cash-register closing (denomination count), and GST filing export
(GSTR-1 style CSV of outward supplies by slab — the `gst_summary` query
already computes the needed numbers). (Barcode scan-to-add and the supplier
purchase ledger were on this list — both are now built.)

**Shop-floor features (delegated round):** the shop owner asked for "whatever
a shop needs to make billing easy", so six features were added in one round:
(1) *Barcode scan → instant add* — USB scanners act as keyboards (barcode +
Enter), so the billing search checks `find_by_sku()` for an exact
case-insensitive match on Return *before* the autocomplete path and adds
qty 1 immediately (merging with the existing line), clearing the field for
the next scan; non-matches fall through to the dropdown. (2) *Purchases* —
a new screen + `suppliers`/`purchases`/`purchase_items` tables; saving a
purchase increases stock and re-prices inventory to the weighted average of
old and new stock, and deleting a purchase reverses the stock (the averaged
cost is deliberately left as-is — reversing it exactly would need full lot
history). (3) *Sales returns* — `returns`/`return_items` tables; per-line
return qty is capped at billed-minus-already-returned (tracked in
`return_items`), stock goes back up, credit bills reduce the khata balance,
and a numbered credit note (`CN-0001`…) prints via a credit-note PDF that
reuses the invoice Platypus layout with a CREDIT NOTE title. (4) *Dues
collection* — the khata dialog now takes date + mode (Cash/UPI/Bank, stored
in a migrated `payments.mode` column), refuses amounts above the
outstanding dues, and prints a payment-receipt PDF; outstanding stays
consistent by construction (credit bills add, payments and credit notes
subtract). (5) *Repeat last bill* — loads the customer's latest bill into a
fresh tab at current prices with a "loaded from bill X" note, for regular
weekly orders. (6) *WhatsApp share* — builds a text bill summary and opens
`wa.me/<normalized-IN-number>?text=…` via `webbrowser` (no API keys);
missing phone numbers prompt to add one first. To keep `ui.py` under the
push size limit, the print dialogs moved to `print_ui.py`, purchases to
`purchases_ui.py`, and returns/WhatsApp to `returns_ui.py` — pure moves plus
the new code, verified by 25 headless Xvfb tests covering every feature
end-to-end.
