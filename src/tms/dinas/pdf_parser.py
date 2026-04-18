"""
Dinas PDF parser — ERKA invoice format.

Supported templates:
  erka_standard   — standard ERKA Rechnung/Invoice (NimbusMono, tabular layout)
  erka_correction — correction/cancellation variant (Referenz-Erka: body format)

Usage::

    from tms.dinas.pdf_parser import parse_pdf, parse_all

    records = parse_pdf("path/to/RECHNUNG01234567.pdf")
    df = parse_all([
        "data/extracted/sika_ssc/Dinas SSC/",
        "data/extracted/v1/Noerpel AI/SIka/Rechnungen/Rechnungen DINAS/",
    ])
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd

from tms.dinas._erka_helpers import (
    all_page_spans,
    group_rows,
    is_charge_row,
    is_correction_entry_row,
    is_entry_marker_row,
    parse_amount,
    parse_charge_row,
    parse_date_de,
    parse_plz_land,
    row_first,
    row_joined,
    row_tokens,
    _FRACHT_RE,
    _MAUT_RE,
    _DIESEL_RE,
)
from tms.dinas.models import Charge, ShipmentRecord

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template detection
# ---------------------------------------------------------------------------

def _detect_template(doc: fitz.Document) -> str:
    text = "".join(doc[i].get_text() for i in range(min(2, len(doc))))
    if "Sendungsnummer" in text:
        return "erka_standard"
    if "Referenz-Erka" in text:
        return "erka_correction"
    return "unknown"


# ---------------------------------------------------------------------------
# Invoice header (shared by both templates)
# ---------------------------------------------------------------------------

_RECHNUNG_NR_RE = re.compile(r"^\d{5,9}$")
_DATE_RE        = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def _parse_invoice_header(doc: fitz.Document) -> dict:
    """
    Extract header fields from the first page.

    Returns dict with keys: rechnung_nr, erka_kundennr,
    rechnung_date, buchungs_date  (all may be None).
    """
    h: dict = {
        "rechnung_nr": None,
        "erka_kundennr": None,
        "rechnung_date": None,
        "buchungs_date": None,
    }
    page = doc[0]
    rows = group_rows(all_page_spans(page))

    for row in rows:
        texts = [s["text"] for s in row]
        texts_set = set(texts)

        # Rechnung-Nr. → first digit-only token right of x=440
        if "Rechnung-Nr.:" in texts_set:
            v = row_first(row, min_x=440)
            if v and _RECHNUNG_NR_RE.match(v):
                h["rechnung_nr"] = v

        # ERKA-Nummer / Erkanummer → value at x > 540
        if any(t.lower().replace("-", "").replace(":", "") == "erkanummer"
               for t in texts_set):
            v = row_first(row, min_x=540)
            if v and v.isdigit():
                h["erka_kundennr"] = v

        # Rechnungsdatum: row with "den" → date at x > 510
        if "den" in texts_set:
            for s in row:
                if s["x"] > 510 and _DATE_RE.match(s["text"]):
                    h["rechnung_date"] = parse_date_de(s["text"])
                    break

        # Buchungsdatum: first occurrence
        if "Buchungsdatum" in texts_set and h["buchungs_date"] is None:
            v = row_first(row, min_x=510)
            if v and _DATE_RE.match(v):
                h["buchungs_date"] = parse_date_de(v)

    return h


# ---------------------------------------------------------------------------
# Standard template parser
# ---------------------------------------------------------------------------

_SENDNR_RE   = re.compile(r"^\((\d{6,10})\)$")  # "(32811468)"
_DATE_SHORT  = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")  # "04.12.24"
_DATE_LONG   = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")  # "04.12.2024"
_ENTRY_NR_RE = re.compile(r"^(\d+)\)$")
_STP_RE      = re.compile(r"^([\d.,]+)$")   # numeric Stp count
_WEIGHT_RE   = re.compile(r"^=?(\d+)$")     # "=22226" or "22226"
_NUMERIC_RE  = re.compile(r"^[\d.,]+$")


def _parse_abs_empf_row(row: list[dict]) -> dict:
    """Parse 'Abs.: ... Empf.: ... XX,XX Stp =YYYY kg' row."""
    result: dict = {
        "abs_name": None, "abs_plz": None, "abs_city": None, "abs_land": "DE",
        "empf_name": None, "empf_plz": None, "empf_city": None, "empf_land": None,
        "stp": None, "gewicht_kg": None,
    }
    # Separator: "Empf.:" token
    empf_x = next((s["x"] for s in row if s["text"] == "Empf.:"), None)
    stp_x  = next((s["x"] for s in row if s["text"] == "Stp"), None)

    abs_end  = empf_x if empf_x else 246.0
    empf_end = stp_x  if stp_x  else 460.0

    abs_tokens  = row_tokens(row, min_x=60, max_x=abs_end)
    empf_tokens = row_tokens(row, min_x=empf_x + 6 if empf_x else 252, max_x=empf_end)

    # Filter labels
    abs_name  = " ".join(t for t in abs_tokens  if t not in ("Abs.:", "Empf.:"))
    empf_name = " ".join(t for t in empf_tokens if t not in ("Abs.:", "Empf.:"))
    result["abs_name"]  = abs_name  or None
    result["empf_name"] = empf_name or None

    # Stellplätze: token just before "Stp"
    if stp_x:
        stp_candidates = [s for s in row if s["x"] < stp_x and _STP_RE.match(s["text"])]
        if stp_candidates:
            raw = stp_candidates[-1]["text"].replace(",", ".")
            try:
                result["stp"] = float(raw)
            except ValueError:
                pass

    # Weight: token after "Stp" (may be "=22226" or separate "=" + "22226")
    if stp_x:
        after_stp = [s for s in sorted(row, key=lambda s: s["x"])
                     if s["x"] > stp_x and s["text"] not in ("Stp", "kg", "=")]
        for s in after_stp:
            m = _WEIGHT_RE.match(s["text"])
            if m:
                try:
                    result["gewicht_kg"] = float(m.group(1))
                    break
                except ValueError:
                    pass

    return result


def _parse_plz_row(row: list[dict], abs_end: float = 246.0) -> dict:
    """Parse PLZ/city row: abs side (x<246) and empf side (x>=246)."""
    result: dict = {
        "abs_plz": None, "abs_city": None, "abs_land": "DE",
        "empf_plz": None, "empf_city": None, "empf_land": None,
    }
    abs_tokens  = row_tokens(row, min_x=60,  max_x=abs_end)
    empf_tokens = row_tokens(row, min_x=abs_end)

    if abs_tokens:
        land, plz = parse_plz_land(abs_tokens[0])
        result["abs_land"] = land or "DE"
        result["abs_plz"]  = plz
        result["abs_city"] = " ".join(abs_tokens[1:]) or None

    if empf_tokens:
        land, plz = parse_plz_land(empf_tokens[0])
        result["empf_land"] = land or None
        result["empf_plz"]  = plz
        result["empf_city"] = " ".join(empf_tokens[1:]) or None

    return result


def _parse_position_row(row: list[dict]) -> dict:
    """Parse bordero + 'NN EW inhalt ...' row."""
    result: dict = {"bordero_nr": None, "anz_vp": None, "inhalt": None}
    tokens = row_tokens(row, min_x=40, max_x=470)
    if not tokens:
        return result
    # First token at x<130 is typically the bordero number
    left = row_tokens(row, min_x=40, max_x=130)
    if left:
        result["bordero_nr"] = left[0]
    # Find "EW" token; the token before it is the count
    try:
        ew_idx = tokens.index("EW")
        if ew_idx > 0:
            try:
                result["anz_vp"] = int(tokens[ew_idx - 1])
            except ValueError:
                pass
        result["inhalt"] = " ".join(tokens[ew_idx + 1:]) or None
    except ValueError:
        pass
    return result


def _parse_standard_entry(entry_rows: list[list[dict]]) -> dict:
    """
    Parse one shipment entry block (list of rows from marker to next marker).
    Returns a dict matching ShipmentRecord fields (minus invoice-level fields).
    """
    e: dict = {
        "sendungsnummer": None, "leistung_date": None, "frankatur": None,
        "abs_name": None, "abs_plz": None, "abs_city": None, "abs_land": "DE",
        "empf_name": None, "empf_plz": None, "empf_city": None, "empf_land": None,
        "stp": None, "gewicht_kg": None, "lm": None,
        "bordero_nr": None, "anz_vp": None, "inhalt": None,
        "fracht": None, "fracht_currency": "EUR",
        "maut": None, "diesel": None,
        "sonstige": [], "sendungssumme": None,
    }

    saw_abs_empf = False
    saw_plz      = False
    saw_ref      = False

    for row in entry_rows:
        texts = [s["text"] for s in row]
        texts_set = set(texts)

        # ── Row 0: entry marker → date + sendungsnummer ───────────────
        if is_entry_marker_row(row):
            # date at x≈60
            for s in row:
                if 50 < s["x"] < 120:
                    d = parse_date_de(s["text"])
                    if d:
                        e["leistung_date"] = d
                        break
            # sendungsnummer: "(XXXXXXXX)" at x≈150
            for s in row:
                if 120 < s["x"] < 200:
                    m = _SENDNR_RE.match(s["text"])
                    if m:
                        e["sendungsnummer"] = m.group(1)
                        break
            continue

        # ── Frankatur ─────────────────────────────────────────────────
        if "Frankatur:" in texts_set:
            e["frankatur"] = row_joined(row, min_x=120, max_x=450) or None
            continue

        # ── Abs./Empf. row ────────────────────────────────────────────
        if "Abs.:" in texts_set and not saw_abs_empf:
            data = _parse_abs_empf_row(row)
            e.update({k: v for k, v in data.items() if v is not None})
            if data.get("abs_land"):
                e["abs_land"] = data["abs_land"]
            saw_abs_empf = True
            continue

        # ── PLZ row (immediately after Abs./Empf.) ────────────────────
        if saw_abs_empf and not saw_plz and not saw_ref:
            # check it's not another known label row
            if not any(t in texts_set for t in ("Ref.:", "Frankatur:", "FRACHT",
                                                  "MAUT", "DIESEL", "Abs.:")):
                data = _parse_plz_row(row)
                e.update({k: v for k, v in data.items() if v is not None})
                if data.get("abs_land"):
                    e["abs_land"] = data["abs_land"]
                saw_plz = True
                continue

        # ── Ref. row ──────────────────────────────────────────────────
        if "Ref.:" in texts_set:
            v = row_first(row, min_x=80)
            if v:
                e["bordero_nr"] = v
            saw_ref = True
            continue

        # ── Position row: bordero + NN EW inhalt ─────────────────────
        if "EW" in texts_set and e.get("bordero_nr") and not is_charge_row(row):
            data = _parse_position_row(row)
            for k, v in data.items():
                if v is not None and e[k] is None:
                    e[k] = v
            continue

        # ── Sendungssumme ─────────────────────────────────────────────
        if any("Sendungssumme" in t for t in texts):
            v = parse_amount(row_first(row, min_x=490) or "")
            if v is not None:
                e["sendungssumme"] = v
            continue

        # ── Charge rows ───────────────────────────────────────────────
        if is_charge_row(row):
            label, amt, cur, detail = parse_charge_row(row)
            if amt is None:
                continue
            label_up = label.upper()
            if _FRACHT_RE.search(label_up):
                e["fracht"] = amt
                e["fracht_currency"] = cur
            elif _MAUT_RE.search(label_up):
                e["maut"] = amt
            elif _DIESEL_RE.search(label_up):
                e["diesel"] = amt
            else:
                e["sonstige"].append(Charge(label=label, amount=amt,
                                            currency=cur, detail=detail))
            continue

        # ── LM (Lademeter) anywhere ───────────────────────────────────
        if "LM" in texts_set:
            for i, s in enumerate(row):
                if s["text"] == "LM" and i + 1 < len(row):
                    v = parse_amount(row[i + 1]["text"])
                    if v is not None:
                        e["lm"] = float(v)
                    break

    return e


def _parse_erka_standard(doc: fitz.Document, path: str,
                          header: dict) -> list[ShipmentRecord]:
    records: list[ShipmentRecord] = []
    eintrag_nr = 0

    for page in doc:
        spans = all_page_spans(page)
        rows  = group_rows(spans)

        # Find entry marker rows (skip header and column-header rows)
        marker_indices = [i for i, row in enumerate(rows) if is_entry_marker_row(row)]
        if not marker_indices:
            continue

        for k, start in enumerate(marker_indices):
            end = marker_indices[k + 1] if k + 1 < len(marker_indices) else len(rows)
            entry_rows = rows[start:end]
            eintrag_nr += 1
            e = _parse_standard_entry(entry_rows)

            records.append(ShipmentRecord(
                pdf_path=path,
                rechnung_nr=header["rechnung_nr"] or "",
                erka_kundennr=header["erka_kundennr"],
                rechnung_date=header["rechnung_date"],
                buchungs_date=header["buchungs_date"],
                eintrag_nr=eintrag_nr,
                sendungsnummer=e["sendungsnummer"],
                leistung_date=e["leistung_date"],
                frankatur=e["frankatur"],
                abs_name=e["abs_name"],
                abs_plz=e["abs_plz"],
                abs_city=e["abs_city"],
                abs_land=e["abs_land"],
                empf_name=e["empf_name"],
                empf_plz=e["empf_plz"],
                empf_city=e["empf_city"],
                empf_land=e["empf_land"],
                stp=e["stp"],
                gewicht_kg=e["gewicht_kg"],
                lm=e["lm"],
                bordero_nr=e["bordero_nr"],
                anz_vp=e["anz_vp"],
                inhalt=e["inhalt"],
                fracht=e["fracht"],
                fracht_currency=e["fracht_currency"],
                maut=e["maut"],
                diesel=e["diesel"],
                sonstige=e["sonstige"],
                sendungssumme=e["sendungssumme"],
                template="erka_standard",
            ))

    return records


# ---------------------------------------------------------------------------
# Correction template parser
# ---------------------------------------------------------------------------

def _parse_correction_entry(entry_rows: list[list[dict]]) -> dict:
    """
    Parse a single correction entry block.
    Entry rows span from Referenz-Erka row to the next one (or end of page).
    The charge amount is on the Abs/ship row (right side).
    """
    e: dict = {
        "sendungsnummer": None, "leistung_date": None,
        "abs_name": None, "abs_plz": None, "abs_city": None, "abs_land": "DE",
        "empf_name": None, "empf_plz": None, "empf_city": None, "empf_land": None,
        "stp": None, "gewicht_kg": None, "lm": None,
        "bordero_nr": None, "anz_vp": None, "inhalt": None,
        "fracht": None, "fracht_currency": "EUR",
        "maut": None, "diesel": None,
        "sonstige": [], "sendungssumme": None, "frankatur": None,
    }

    for row in entry_rows:
        texts     = [s["text"] for s in row]
        texts_set = set(texts)

        # ── Referenz-Erka row: date (x<55) + erka_ref (x≈186) ────────
        if is_correction_entry_row(row):
            for s in row:
                if s["x"] < 55 and (
                    _DATE_SHORT.match(s["text"]) or _DATE_LONG.match(s["text"])
                ):
                    e["leistung_date"] = parse_date_de(s["text"])
                elif s["x"] > 170 and s["text"].isdigit() and len(s["text"]) >= 6:
                    e["sendungsnummer"] = s["text"]
            continue

        # ── Abs/ship row ──────────────────────────────────────────────
        if "Abs/ship:" in texts_set:
            # Name tokens: x=168 to ~300
            name_parts = row_tokens(row, min_x=168, max_x=295)
            e["abs_name"] = " ".join(name_parts) or None
            # PLZ+city: first token in x=295-420 range (may include land prefix)
            plz_tokens = row_tokens(row, min_x=295, max_x=420)
            if plz_tokens:
                land, plz = parse_plz_land(plz_tokens[0])
                e["abs_land"] = land or "DE"
                e["abs_plz"]  = plz
                e["abs_city"] = " ".join(plz_tokens[1:]) or None
            # Charge amount on this row (right side)
            amt = parse_amount(row_first(row, min_x=490) or "")
            if amt is not None:
                e["fracht"]          = amt
                cur_tok = row_first(row, min_x=555)
                e["fracht_currency"] = cur_tok if cur_tok in ("EUR", "CHF") else "EUR"
            continue

        # ── Emp/cons row ──────────────────────────────────────────────
        if "Emp/cons:" in texts_set:
            name_parts = row_tokens(row, min_x=168, max_x=295)
            e["empf_name"] = " ".join(name_parts) or None
            plz_tokens = row_tokens(row, min_x=295, max_x=420)
            if plz_tokens:
                land, plz = parse_plz_land(plz_tokens[0])
                e["empf_land"] = land or None
                e["empf_plz"]  = plz
                e["empf_city"] = " ".join(plz_tokens[1:]) or None
            continue

        # ── Gew/weight row ────────────────────────────────────────────
        if "Gew/weight:" in texts_set:
            # weight in kg at x≈180
            wt = row_first(row, min_x=170, max_x=220)
            if wt:
                try:
                    e["gewicht_kg"] = float(wt.replace(",", "."))
                except ValueError:
                    pass
            # LM at x≈366 or 384
            if "LM" in texts_set:
                for i, s in enumerate(sorted(row, key=lambda s: s["x"])):
                    if s["text"] == "LM" and i + 1 < len(row):
                        nxt = sorted(row, key=lambda s: s["x"])[i + 1]
                        v = parse_amount(nxt["text"])
                        if v is not None:
                            e["lm"] = float(v)
                        break
            continue

        # ── Ref. row ──────────────────────────────────────────────────
        if "Ref.:" in texts_set:
            v = row_first(row, min_x=130)
            if v:
                e["bordero_nr"] = v
            continue

        # ── Position (EW) row ─────────────────────────────────────────
        if "EW" in texts_set:
            data = _parse_position_row(row)
            for k, v in data.items():
                if v is not None and e[k] is None:
                    e[k] = v
            continue

        # ── Regular charge rows (FRACHT, MAUT, etc.) ─────────────────
        if is_charge_row(row):
            label, amt, cur, detail = parse_charge_row(row)
            if amt is None:
                continue
            label_up = label.upper()
            if _FRACHT_RE.search(label_up):
                e["fracht"] = amt
                e["fracht_currency"] = cur
            elif _MAUT_RE.search(label_up):
                e["maut"] = amt
            elif _DIESEL_RE.search(label_up):
                e["diesel"] = amt
            else:
                e["sonstige"].append(Charge(label=label, amount=amt,
                                            currency=cur, detail=detail))

    return e


def _parse_erka_correction(doc: fitz.Document, path: str,
                            header: dict) -> list[ShipmentRecord]:
    records: list[ShipmentRecord] = []
    eintrag_nr = 0

    for page in doc:
        spans = all_page_spans(page)
        rows  = group_rows(spans)

        # Find correction entry rows
        marker_indices = [i for i, row in enumerate(rows)
                          if is_correction_entry_row(row)]
        if not marker_indices:
            continue

        # The date may appear on the same row as the first Referenz-Erka
        # or on a preceding row (x<55, date format).  We use header date as fallback.
        fallback_date = header.get("buchungs_date") or header.get("rechnung_date")

        for k, start in enumerate(marker_indices):
            end = marker_indices[k + 1] if k + 1 < len(marker_indices) else len(rows)
            entry_rows = rows[start:end]
            eintrag_nr += 1
            e = _parse_correction_entry(entry_rows)

            # Fall back to page-level date for subsequent entries
            if e["leistung_date"] is None:
                e["leistung_date"] = fallback_date

            records.append(ShipmentRecord(
                pdf_path=path,
                rechnung_nr=header["rechnung_nr"] or "",
                erka_kundennr=header["erka_kundennr"],
                rechnung_date=header["rechnung_date"],
                buchungs_date=header["buchungs_date"],
                eintrag_nr=eintrag_nr,
                sendungsnummer=e["sendungsnummer"],
                leistung_date=e["leistung_date"],
                frankatur=e["frankatur"],
                abs_name=e["abs_name"],
                abs_plz=e["abs_plz"],
                abs_city=e["abs_city"],
                abs_land=e["abs_land"],
                empf_name=e["empf_name"],
                empf_plz=e["empf_plz"],
                empf_city=e["empf_city"],
                empf_land=e["empf_land"],
                stp=e["stp"],
                gewicht_kg=e["gewicht_kg"],
                lm=e["lm"],
                bordero_nr=e["bordero_nr"],
                anz_vp=e["anz_vp"],
                inhalt=e["inhalt"],
                fracht=e["fracht"],
                fracht_currency=e["fracht_currency"],
                maut=e["maut"],
                diesel=e["diesel"],
                sonstige=e["sonstige"],
                sendungssumme=e["sendungssumme"],
                template="erka_correction",
            ))

    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_pdf(path: str | Path) -> list[ShipmentRecord]:
    """Parse a single Dinas PDF and return a list of ShipmentRecord objects."""
    path = str(path)
    try:
        doc = fitz.open(path)
    except Exception as exc:
        log.warning("Cannot open %s: %s", path, exc)
        return []

    template = _detect_template(doc)
    header   = _parse_invoice_header(doc)

    try:
        if template == "erka_standard":
            records = _parse_erka_standard(doc, path, header)
        elif template == "erka_correction":
            records = _parse_erka_correction(doc, path, header)
        else:
            log.warning("Unknown template in %s — skipped", path)
            records = []
    except Exception as exc:
        log.error("Error parsing %s: %s", path, exc, exc_info=True)
        records = []
    finally:
        doc.close()

    return records


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_all(
    dirs: list[str | Path],
    deduplicate: bool = True,
    glob: str = "*.pdf",
) -> pd.DataFrame:
    """
    Parse all PDFs in the given directories, optionally deduplicating by
    MD5 hash.  Returns a DataFrame with one row per shipment entry.

    Args:
        dirs:        Directories to scan (recursed one level for *.pdf).
        deduplicate: Skip files whose MD5 was already processed.
        glob:        File glob pattern (case-insensitive on Linux).
    """
    seen_md5: set[str] = set()
    all_records: list[ShipmentRecord] = []

    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            log.warning("Directory not found: %s", d)
            continue
        pdfs = sorted(
            p for p in d.iterdir()
            if p.suffix.lower() == ".pdf"
        )
        log.info("Scanning %s — %d PDFs", d, len(pdfs))

        for pdf_path in pdfs:
            if deduplicate:
                h = _md5(str(pdf_path))
                if h in seen_md5:
                    log.debug("Duplicate skipped: %s", pdf_path.name)
                    continue
                seen_md5.add(h)

            records = parse_pdf(pdf_path)
            all_records.extend(records)

    if not all_records:
        return pd.DataFrame()

    rows = []
    for r in all_records:
        d = asdict(r)
        # Flatten sonstige charges into JSON-like string for Parquet
        d["sonstige"] = str([
            {"label": c["label"], "amount": str(c["amount"]),
             "currency": c["currency"], "detail": c["detail"]}
            for c in d["sonstige"]
        ])
        # Convert Decimal to float for Parquet compatibility
        for col in ("fracht", "maut", "diesel", "sendungssumme"):
            if d[col] is not None:
                d[col] = float(d[col])
        rows.append(d)

    return pd.DataFrame(rows)
