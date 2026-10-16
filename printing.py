"""
BillBook — printing.py
Universal print system. No browser, no Chrome extension.

Pipeline: invoice data -> reportlab PDF -> the OS's own print path.
* PDF generation works on any OS (A4 + 80mm thermal layouts).
* On Windows, installed printers are enumerated with win32print and the PDF
  is sent to the chosen printer through os.startfile(path, "print") — the
  same "right-click -> Print" action a user can do by hand.
* Anywhere else (or if printing fails), the app saves/opens the PDF instead
  of pretending the job reached a printer. Callers get an honest
  (ok, message) result and can show it to the user.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from db import data_dir, DB


# ---------------------------------------------------------------------------
# Rupees in PDFs
# ---------------------------------------------------------------------------
_FONT_NAME = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_HAS_RUPEE = False


def _register_rupee_font():
    """Try to register a TTF that contains the ₹ glyph (DejaVu / Nirmala).
    Falls back to 'Rs.' text when none is found."""
    global _FONT_NAME, _FONT_BOLD, _HAS_RUPEE
    candidates = [
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        os.path.expanduser("~/.fonts/DejaVuSans.ttf"),
        # Windows
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\DejaVuSans.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    bold_map = {
        "DejaVuSans.ttf": "DejaVuSans-Bold.ttf",
        "Nirmala.ttf": "NirmalaB.ttf",
    }
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont("BillBook", path))
            bold_path = path
            for suffix, bold_suffix in bold_map.items():
                if path.endswith(suffix):
                    cand = path[: -len(suffix)] + bold_suffix
                    if os.path.isfile(cand):
                        bold_path = cand
                    break
            pdfmetrics.registerFont(TTFont("BillBook-Bold", bold_path))
            _FONT_NAME, _FONT_BOLD, _HAS_RUPEE = "BillBook", "BillBook-Bold", True
            return
        except Exception:
            continue


_register_rupee_font()


def money(n):
    """Currency string that always renders in the generated PDF."""
    v = float(n)
    if _HAS_RUPEE:
        return f"\u20b9{v:,.2f}"
    return f"Rs. {v:,.2f}"


# ---------------------------------------------------------------------------
# Printer enumeration (Windows)
# ---------------------------------------------------------------------------
def _win32print():
    """Return the win32print module, or None outside Windows / when
    pywin32 is not installed."""
    if sys.platform != "win32":
        return None
    try:
        import win32print
        return win32print
    except ImportError:
        return None


def list_printers():
    """Names of installed printers. Empty list on non-Windows or on error —
    callers should treat that as 'no printer choice available'."""
    wp = _win32print()
    if wp is None:
        return []
    try:
        flags = wp.PRINTER_ENUM_LOCAL | wp.PRINTER_ENUM_CONNECTIONS
        return sorted(p[2] for p in wp.EnumPrinters(flags) if p[2])
    except Exception:
        return []


def get_default_printer():
    wp = _win32print()
    if wp is None:
        return ""
    try:
        return wp.GetDefaultPrinter()
    except Exception:
        return ""


def print_pdf(pdf_path, printer=None, copies=1):
    """Send a PDF to a printer via the OS.

    Returns (ok, message). On non-Windows, or when pywin32 is missing, or
    when the OS call fails, ok is False and the caller should fall back to
    just opening/saving the PDF — never claim the job printed.
    """
    pdf_path = str(pdf_path)
    wp = _win32print()
    if wp is None or sys.platform != "win32":
        return False, "Direct printing needs Windows. The PDF was saved — open it to print."
    copies = max(int(copies or 1), 1)
    try:
        # Temporarily make the chosen printer the default so
        # os.startfile(path, "print") targets it, then restore.
        restore = None
        if printer:
            try:
                current = wp.GetDefaultPrinter()
            except Exception:
                current = None
            if current and current != printer:
                wp.SetDefaultPrinter(printer)
                restore = current
        try:
            for _ in range(copies):
                os.startfile(pdf_path, "print")
        finally:
            if restore:
                try:
                    wp.SetDefaultPrinter(restore)
                except Exception:
                    pass
        return True, f"Sent to printer '{printer or 'default'}'."
    except Exception as e:
        return False, f"Could not print automatically ({e}). The PDF was saved — open it to print."


def open_pdf(pdf_path):
    """Open the PDF in the default viewer. Returns True on best effort."""
    pdf_path = str(pdf_path)
    try:
        if sys.platform == "win32":
            os.startfile(pdf_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", pdf_path], check=False)
        else:
            subprocess.run(["xdg-open", pdf_path], check=False)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# PDF invoice generation (reportlab)
# ---------------------------------------------------------------------------
def invoices_dir() -> Path:
    d = data_dir() / "invoices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slabs(items):
    """GST breakup: slab -> [taxable, gst]."""
    out = {}
    for it in items:
        slab = float(it.get("gst_percent", 0) or 0)
        taxable = max(float(it["qty"]) * float(it["price"])
                      - float(it.get("line_discount", 0) or 0), 0.0)
        gst = taxable * slab / 100.0
        out.setdefault(slab, [0.0, 0.0])
        out[slab][0] += taxable
        out[slab][1] += gst
    return out


def _story(bill, items, profile, prefs, narrow):
    """Build the Platypus story (shared by A4 + thermal)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (HRFlowable, Paragraph, Spacer, Table,
                                    TableStyle)

    accent = prefs.get("accent", "#1f6f43") or "#1f6f43"
    accent_c = colors.HexColor(accent)
    dark = colors.HexColor("#222222")
    grey = colors.HexColor("#777777")

    fs = 8 if narrow else 10        # base font size
    fs_title = 13 if narrow else 20
    fs_h = 10 if narrow else 12

    def P(text, size=fs, bold=False, color=dark, align=TA_LEFT, space=2):
        return Paragraph(
            text, ParagraphStyle(
                "s", fontName=_FONT_BOLD if bold else _FONT_NAME,
                fontSize=size, leading=size * 1.3, textColor=color,
                alignment=align, spaceAfter=space))

    story = []
    # -- shop header -----------------------------------------------------
    story.append(P(profile.get("shop_name") or "BillBook Shop",
                   size=fs_title, bold=True, color=accent_c,
                   align=TA_CENTER, space=1))
    if profile.get("shop_tagline"):
        story.append(P(profile["shop_tagline"], align=TA_CENTER, space=1))
    if profile.get("shop_address"):
        story.append(P(profile["shop_address"], color=grey, align=TA_CENTER,
                        space=1))
    if profile.get("shop_phone"):
        story.append(P(f"Phone: {profile['shop_phone']}", color=grey,
                       align=TA_CENTER, space=1))
    if prefs.get("show_gstin") and profile.get("shop_gstin"):
        story.append(P(f"GSTIN: {profile['shop_gstin']}", color=grey,
                       align=TA_CENTER, space=1))
    if prefs.get("header_note"):
        story.append(P(prefs["header_note"], align=TA_CENTER, space=1))
    story.append(HRFlowable(width="100%", thickness=2.5, color=accent_c,
                            spaceAfter=6, spaceBefore=4))

    # -- bill meta --------------------------------------------------------
    cust = bill.get("customer_name") or "Walk-in"
    meta = [
        [P(f"<b>Bill No:</b> {bill['bill_no']}", size=fs_h),
         P(f"<b>Customer:</b> {cust}", size=fs_h)],
        [P(f"<b>Date:</b> {bill['date']}", size=fs_h),
         P(f"<b>Phone:</b> {bill.get('customer_phone') or '-'}", size=fs_h)],
        [P(f"<b>Payment:</b> {bill.get('payment_type', '')}"
           + ("  <b><font color='#b3261e'>CREDIT — due</font></b>"
              if bill.get("payment_type") == "Credit" else ""), size=fs_h),
         P(f"<b>Address:</b> {bill.get('customer_address') or '-'}",
           size=fs_h)],
    ]
    story.append(Table(meta, colWidths=["50%", "50%"]))
    story.append(Spacer(1, 8))

    # -- items ------------------------------------------------------------
    show_disc = prefs.get("show_discounts", True)
    show_codes = prefs.get("show_item_codes", True)
    header = ["#", "Item", "Qty", "Rate"]
    if show_disc:
        header.append("Disc.")
    header += ["GST%", "Amount"]
    data = [header]
    for i, it in enumerate(items, 1):
        name = it["name"]
        if show_codes and it.get("sku"):
            name = f"{name}<br/><font color='#777777' size={fs - 1}>{it['sku']}</font>"
        disc = money(it.get("line_discount", 0)) if it.get("line_discount") else "-"
        row = [str(i), Paragraph(name, ParagraphStyle(
            "n", fontName=_FONT_NAME, fontSize=fs, leading=fs * 1.3)),
               f"{float(it['qty']):g} {it.get('unit', '')}",
               money(it["price"])]
        if show_disc:
            row.append(disc)
        taxable = max(float(it["qty"]) * float(it["price"])
                      - float(it.get("line_discount", 0) or 0), 0.0)
        row += [f"{float(it.get('gst_percent', 0) or 0):g}%",
                money(taxable * (1 + float(it.get("gst_percent", 0) or 0) / 100))]
        data.append(row)

    if narrow:
        # 80mm thermal: tight columns in points; Item takes the remainder.
        widths = [12, None, 24, 36, 30, 26, 44]
        if not show_disc:
            widths.pop(4)
    else:
        widths = [22, None, 52, 62, 62, 44, 78]
        if not show_disc:
            widths.pop(4)
    # Resolve the flexible Item column
    total_w = _usable_width(narrow)
    fixed = sum(w for w in widths if w is not None)
    widths = [total_w - fixed if w is None else w for w in widths]

    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), accent_c),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
             ("FONTSIZE", (0, 0), (-1, -1), fs),
             ("FONTNAME", (0, 1), (-1, -1), _FONT_NAME),
             ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1),
              [colors.white, colors.HexColor("#f7f7f7")])]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 8))

    # -- GST breakup -------------------------------------------------------
    slabs = _slabs(items)
    gdata = [["Slab", "Taxable", "CGST", "SGST", "GST"]]
    for slab in sorted(slabs):
        taxable, gst = slabs[slab]
        gdata.append([f"{slab:g}%", money(taxable), money(gst / 2),
                      money(gst / 2), money(gst)])
    gt = Table(gdata, colWidths=[total_w * w for w in
                                 (0.16, 0.24, 0.2, 0.2, 0.2)])
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), fs - 1 if narrow else fs),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
    ]))
    story.append(gt)
    story.append(Spacer(1, 8))

    # -- totals ------------------------------------------------------------
    tdata = [["Subtotal", money(bill["subtotal"])],
             ["Total GST", money(bill["gst_total"])]]
    if float(bill.get("discount", 0) or 0):
        tdata.append(["Discount", f"- {money(bill['discount'])}"])
    tdata.append(["Round off", money(bill.get("round_off", 0) or 0)])
    tdata.append(["Grand Total", money(bill["grand_total"])])
    tw = total_w * (0.75 if narrow else 0.46)
    tt = Table(tdata, colWidths=[tw * 0.55, tw * 0.45])
    tt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
        ("FONTNAME", (0, -1), (-1, -1), _FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -2), fs),
        ("FONTSIZE", (0, -1), (-1, -1), fs + (2 if not narrow else 1)),
        ("TEXTCOLOR", (0, -1), (-1, -1), accent_c),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 2, accent_c),
    ]))
    story.append(Table([[Spacer(1, 1), tt]],
                       colWidths=[total_w - tw, tw]))
    story.append(Spacer(1, 10))

    # -- footer ------------------------------------------------------------
    if prefs.get("footer_note"):
        story.append(P(prefs["footer_note"], align=TA_CENTER,
                       color=grey, space=6))
    story.append(Table(
        [[P("Customer signature", color=grey),
          P(f"For {profile.get('shop_name') or 'Shop'}", color=grey,
            align=TA_RIGHT)]],
        colWidths=["50%", "50%"]))
    now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    story.append(P(f"Generated by BillBook — {now}", size=fs - 1,
                   color=grey, align=TA_CENTER, space=2))
    return story


def _usable_width(narrow):
    from reportlab.lib.units import mm
    return (80 * mm - 4 * mm) if narrow else (210 * mm - 24 * mm)


def generate_invoice_pdf(bill, items, profile, prefs, dest_path=None):
    """Render the invoice as a PDF (A4 or 80mm thermal per prefs).
    Returns the Path of the written file."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    narrow = prefs.get("paper") == "thermal"
    if dest_path is None:
        safe = str(bill["bill_no"]).replace("/", "-")
        dest_path = invoices_dir() / f"{safe}_invoice.pdf"
    else:
        dest_path = Path(dest_path)

    if narrow:
        width = 80 * mm
        # Thermal rolls print as one long receipt; over-estimate generously
        # so everything lands on a single page (unused space is harmless).
        height = 150 * mm + len(items) * 10 * mm
        pagesize = (width, height)
        margins = dict(leftMargin=2 * mm, rightMargin=2 * mm,
                       topMargin=3 * mm, bottomMargin=3 * mm)
    else:
        pagesize = A4
        margins = dict(leftMargin=12 * mm, rightMargin=12 * mm,
                       topMargin=12 * mm, bottomMargin=12 * mm)

    doc = SimpleDocTemplate(str(dest_path), pagesize=pagesize,
                            title=f"Invoice {bill['bill_no']}",
                            author=profile.get("shop_name") or "BillBook",
                            **margins)
    doc.build(_story(bill, items, profile, prefs, narrow))
    return dest_path


# ---------------------------------------------------------------------------
# High-level: build + print one saved bill
# ---------------------------------------------------------------------------
def print_bill_pdf(bill_id, db_path=None, printer=None, copies=1,
                   preview=False):
    """Generate the PDF invoice for a saved bill and either open it
    (preview) or send it to a printer.

    Returns (pdf_path, printed: bool, message: str). printed is True only
    when the OS accepted the print job; callers must not claim otherwise.
    """
    db = DB(db_path) if db_path else DB()
    try:
        bill = db.get_bill(bill_id)
        if not bill:
            raise ValueError("Bill not found")
        items = db.bill_items(bill_id)
        for it in items:  # attach SKU for the item-code toggle
            p = db.get_product(it["product_id"]) if it.get("product_id") else None
            it["sku"] = (p or {}).get("sku", "")
        path = generate_invoice_pdf(bill, items, db.shop_profile(),
                                    db.print_prefs())
        if preview:
            ok = open_pdf(path)
            db.log_bill_action(bill_id, "reprinted",
                               f"Invoice preview opened: {path.name}")
            db.close()
            return path, False, ("Invoice preview opened."
                                 if ok else f"PDF saved at {path}")
        ok, msg = print_pdf(path, printer=printer, copies=copies)
        db.log_bill_action(bill_id, "reprinted",
                           f"Invoice PDF: {path.name} — {msg}")
        db.close()
        if not ok:
            # Printing not possible here: open the PDF so the user can
            # print it by hand instead of losing the flow.
            open_pdf(path)
        return path, ok, msg
    except Exception:
        db.close()
        raise
