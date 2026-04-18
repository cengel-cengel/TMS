"""Low-level utilities for ERKA Dinas PDF parsing."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Country prefix → ISO 3166-1 alpha-2
# ---------------------------------------------------------------------------

_LAND_PREFIX: dict[str, str] = {
    "I": "IT", "E": "ES", "F": "FR", "P": "PT",
    "IRL": "IE", "CH": "CH", "A": "AT", "B": "BE",
    "NL": "NL", "DK": "DK", "S": "SE", "SE": "SE",
    "PL": "PL", "CZ": "CZ", "SK": "SK",
    "H": "HU", "HU": "HU", "RO": "RO",
    "SRB": "RS", "RS": "RS", "HR": "HR",
    "SI": "SI", "LUX": "LU", "LU": "LU",
    "GB": "GB", "GR": "GR", "D": "DE",
    "TR": "TR", "MA": "MA", "DZ": "DZ",
}

# Charge labels whose fracht/maut/diesel field should be set explicitly
_FRACHT_RE = re.compile(r"^FRACHT", re.I)
_MAUT_RE   = re.compile(r"^MAUT",   re.I)
_DIESEL_RE = re.compile(r"DIESEL",  re.I)


# ---------------------------------------------------------------------------
# Span → row helpers
# ---------------------------------------------------------------------------

def all_page_spans(page) -> list[dict]:
    """Return all non-empty spans from a PyMuPDF page, sorted by (y, x)."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if t:
                    spans.append({
                        "text": t,
                        "x": span["origin"][0],
                        "y": span["origin"][1],
                    })
    spans.sort(key=lambda s: (round(s["y"], 1), s["x"]))
    return spans


def group_rows(spans: list[dict], tol: float = 2.5) -> list[list[dict]]:
    """Group spans into rows by y-coordinate proximity."""
    if not spans:
        return []
    rows: list[list[dict]] = []
    cur_y = spans[0]["y"]
    cur: list[dict] = []
    for s in spans:
        if abs(s["y"] - cur_y) <= tol:
            cur.append(s)
        else:
            rows.append(cur)
            cur_y = s["y"]
            cur = [s]
    if cur:
        rows.append(cur)
    return rows


def row_tokens(row: list[dict], min_x: float = 0.0, max_x: float = 9999.0) -> list[str]:
    return [s["text"] for s in row if min_x <= s["x"] < max_x]


def row_first(row: list[dict], min_x: float = 0.0, max_x: float = 9999.0) -> str | None:
    for s in sorted(row, key=lambda s: s["x"]):
        if min_x <= s["x"] < max_x:
            return s["text"]
    return None


def row_joined(row: list[dict], min_x: float = 0.0, max_x: float = 9999.0) -> str:
    return " ".join(row_tokens(row, min_x, max_x))


# ---------------------------------------------------------------------------
# Value parsers
# ---------------------------------------------------------------------------

def parse_amount(s: str) -> Decimal | None:
    """Parse German decimal: '1.599,25' or '33,60' → Decimal."""
    s = s.strip().lstrip("=").replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date_de(s: str) -> date | None:
    """Parse 'DD.MM.YYYY' or 'DD.MM.YY'."""
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def parse_plz_land(token: str) -> tuple[str, str]:
    """
    Decompose a PLZ/address token into (land_iso2, cleaned_plz).

    'I-41049'   → ('IT', '41049')
    'IRL-DUB'   → ('IE', 'DUB')
    'CH-6060'   → ('CH', '6060')
    'E-08190'   → ('ES', '08190')
    '70499'     → ('DE', '70499')
    'GB-SW1A'   → ('GB', 'SW1A')
    """
    token = token.strip()
    m = re.match(r"^([A-Z]{1,4})-(.+)$", token)
    if m:
        prefix, rest = m.group(1), m.group(2)
        return (_LAND_PREFIX.get(prefix, prefix), rest)
    if token[:1].isdigit():
        return ("DE", token)
    return ("", token)


# ---------------------------------------------------------------------------
# Row-type detection
# ---------------------------------------------------------------------------

_ENTRY_MARKER_RE = re.compile(r"^\d+\)$")


def is_entry_marker_row(row: list[dict]) -> bool:
    """Row starts a shipment entry: 'N)' at x < 55."""
    return any(
        s["x"] < 55 and _ENTRY_MARKER_RE.match(s["text"])
        for s in row
    )


def is_correction_entry_row(row: list[dict]) -> bool:
    """Row starts a correction entry: contains 'Referenz-Erka'."""
    return any("Referenz-Erka" in s["text"] for s in row)


def is_charge_row(row: list[dict]) -> bool:
    """Row contains a charge label on left + amount + currency on right."""
    labels = row_tokens(row, 0, 350)
    currencies = {s["text"] for s in row if s["x"] > 550}
    if not (currencies & {"EUR", "CHF", "USD"}):
        return False
    label_text = " ".join(labels).upper()
    return any(
        kw in label_text
        for kw in ("FRACHT", "MAUT", "DIESEL", "GEFAHRGUT", "THERMO",
                   "ZUSCHLAG", "NACHNAHME", "STORNO", "AUSLAGEN",
                   "EXPRESS", "LEERGU", "GEBUEHR", "GEBÜHR")
    )


def parse_charge_row(row: list[dict]) -> tuple[str, Decimal | None, str, str | None]:
    """
    Extract (label, amount, currency, detail) from a charge row.

    'detail' captures an extra numeric token between the label and the
    amount (e.g. diesel base price "1038" in DIESELZUSCHLAG rows).
    """
    label_parts: list[str] = []
    mid_tokens: list[str] = []
    amount: Decimal | None = None
    currency = "EUR"
    detail: str | None = None

    amount_candidates: list[tuple[float, Decimal]] = []

    for s in sorted(row, key=lambda s: s["x"]):
        x, t = s["x"], s["text"]
        if t in ("EUR", "CHF", "USD"):
            currency = t
        elif x < 350:
            label_parts.append(t)
        elif x >= 350:
            v = parse_amount(t)
            if v is not None:
                amount_candidates.append((x, v))
            else:
                mid_tokens.append(t)

    if amount_candidates:
        # rightmost candidate = main amount
        amount_candidates.sort(key=lambda p: p[0])
        amount = amount_candidates[-1][1]
        # any earlier numeric token = detail (e.g. diesel base)
        if len(amount_candidates) > 1:
            detail = str(int(amount_candidates[0][1]))

    label = " ".join(label_parts)
    return label, amount, currency, detail
