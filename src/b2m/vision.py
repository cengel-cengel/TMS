"""Claude Vision API wrapper for B2M invoice page extraction."""
import base64
import json
import os
import time
from pathlib import Path

import anthropic

from .schema import PageResult

_CLIENT: anthropic.Anthropic | None = None


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        api_key    = os.environ.get("ANTHROPIC_API_KEY", "")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        if api_key:
            _CLIENT = anthropic.Anthropic(api_key=api_key)
        elif auth_token:
            _CLIENT = anthropic.Anthropic(auth_token=auth_token)
        else:
            raise RuntimeError("Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")
    return _CLIENT


_SYSTEM = """\
You extract structured data from B2Mobility GmbH fuel/energy invoices (multi-country).
Respond with valid JSON only — no markdown fences, no commentary.
All numeric values in your OUTPUT use DOT as decimal separator (e.g. 1234.56).
If a value is absent or not applicable, use null.
Negative amounts are valid (Nachlass/discount): output as e.g. -2.82.
"""

_PROMPT_TEMPLATE = """\
This is page {seite} of {total} from file "{filename}".

ORIENTATION: Middle pages are landscape invoices (wide × tall); pages 1 and last are portrait.

══════════════════════════════════════════════════════════════
STEP 1 — DETECT DOCUMENT FORMAT from title/language/keywords:

  de-aral : "RECHNUNG" (German) + "Karte:" lines + comma-decimal (1.234,56)
  de-bp   : "DEBIT NOTE" (English) + "CARD:" lines + dot-decimal
  at      : "RECHNUNG" (German) + "LENKER" keyword + dot-decimal
  ch      : "DEBIT NOTE" + CHF currency + dot-decimal
  it      : "FATTURA" (Italian) + "CARTA:" lines + dot-decimal
  be      : "FAKTUUR" (Dutch) + "KRT.NR:" lines + dot-decimal
  zusammenstellung : summary/settlement page

STEP 2 — EXTRACT per-card positions using the matching field labels:

  de-aral → header: "Karte: <KARTENNUMMER> <KENNZEICHEN>"
             total row: "SUMME KARTE/KFZ" → Netto EUR · USt-Betrag EUR · Brutto EUR
             artikel: dominant type (LKWDiesel / Diesel / Strom / Maut / etc.)
             warengruppe: from transaction context (nullable for fees/Nachlass)

  de-bp   → header: "CARD: <KARTENNUMMER>  <CARDHOLDER>"
             total row: per-card TOTAL → EXCL.VAT · VAT AMOUNT · INCL.VAT (EUR)
             kennzeichen: CARDHOLDER name   kartennummer: card number

  at      → header: "KARTEN: <KARTENNUMMER>" + "LENKER: <NAME>"
             total row: "KARTEN TOTAL" → TOTAL EXKL.MWST · MWST BETRAG · INKL.MWST (EUR)
             kennzeichen: LENKER name
             rechnung_netto/ust/brutto: always null on rechnung pages — AT has no per-page
             subtotals. The RECHNUNGSSUMME row is an invoice total, not a page total.

  ch      → header: "CARD: <KARTENNUMMER>  <CARDHOLDER>"
             total row: per-card → TOTAL EXCL.VAT (AFTER REBATE — not BASE PRICE) · VAT · INCL.VAT
             netto/ust/brutto: CHF amounts (use CHF column, not EUR)
             kennzeichen: CARDHOLDER name

  it      → header: "CARTA: <KARTENNUMMER>  <INTESTATARIO>"
             total row: "TOTALE CARTA" → IMPONIBILE · IVA · TOTALE IMPORTO (EUR)
             kennzeichen: INTESTATARIO

  be      → header: "KRT.NR: <KARTENNUMMER>  <KAARTREFERENTIE>"
             total row: per-card → TOTAAL EXKL.BTW · BTW BEDRAG · INKL.BTW (EUR)
             kennzeichen: KAARTREFERENTIE

══════════════════════════════════════════════════════════════
NEGATIVE AMOUNTS: "2,82-" or "3,36-" means -2.82 / -3.36. Output as negative.

SKIP THESE ROWS as positions (intermediate subtotals — NEVER add to positionen[]):
  Summe Kraftstoffe · Summe Lieferungen · Summe Gebühren · sonst. Kfz Waren/Die
  KARTEN TOTAL · CARD TOTAL · TOTALE CARTA · TOTAAL KAART
  KOSTENSTELLEN-SUMME · KOSTENSTELLEN-SUMME 1 · KOSTENSTELLEN-SUMME 2 · COST CENTRE SUBTOTAL
  RIEPILOGO · PRODUKT/BTW OVERZICHT · BTW OVERZICHT · Zwischensumme · Subtotal · GESAMT

⚠ de-aral SUMME KARTE/KFZ — control field (NOT a position):
  For de-aral format only: when the "SUMME KARTE/KFZ" total row is visible for a card
  block on THIS page, capture its values in kz_summen[kennzeichen]:
    kz_summen["<kennzeichen>"] = {{"netto": X, "ust": Y, "brutto": Z}}
  The SUMME KARTE/KFZ row values also populate the card's position netto/ust/brutto.
  If "SUMME KARTE/KFZ" is NOT visible (block continues on next page): netto=null and
  do NOT add an entry to kz_summen for that card.
  For all non-de-aral formats: kz_summen = {{}} always.

⚠ AT FORMAT (at): KOSTENSTELLEN-SUMME rows always appear with a number suffix
  (e.g. "KOSTENSTELLEN-SUMME 1:", "KOSTENSTELLEN-SUMME 2:"). NEVER extract these
  as positions — not even with blank kennzeichen. They are cost-center subtotals.
  Only extract a position when a KARTEN: card header is visible on this page.

⚠ If a card block starts on this page but its total row is NOT visible (block
  continues on next page): set netto=null, ust=null, brutto=null for that card.
  Do NOT use any sub-total row as a substitute.

══════════════════════════════════════════════════════════════
PAGE TYPE RULES:
  abrechnungsbrief → positionen=[], extract gesamtbetrag AND manifest table (see below)
  zusammenstellung → positionen=[], fill rechnung_netto/ust/brutto from GESAMT row
  rechnung         → extract per-card positions as above

For ABRECHNUNGSBRIEF pages: extract the invoice list table where each row has
  Land (country) | Rechnungsnummer | Datum | Währung | Betrag-LW | Betrag-EUR
Return it as "manifest" array.

══════════════════════════════════════════════════════════════
Return EXACTLY this JSON (all numeric OUTPUT in dot-decimal):
{{
  "seiten_typ": "<abrechnungsbrief | rechnung | zusammenstellung>",
  "format": "<de-aral | de-bp | at | ch | it | be | unbekannt>",
  "rechnungsnummer": "<RN from page header, or null>",
  "positionen": [
    {{
      "kartennummer": "<card number>",
      "kennzeichen": "<license plate / cardholder / Lenker>",
      "warengruppe": "<product group or null>",
      "artikel": "<dominant article or description>",
      "netto": "<Netto/EXCL.VAT amount, dot-decimal, or null>",
      "ust":   "<VAT/USt amount, dot-decimal, or null>",
      "brutto":"<Brutto/INCL.VAT amount, dot-decimal, or null>"
    }}
  ],
  "kz_summen": {{
    "<kennzeichen>": {{"netto": "<dot-decimal>", "ust": "<dot-decimal>", "brutto": "<dot-decimal>"}}
  }},
  "rechnung_netto":  "<page-level Netto total, dot-decimal, or null>",
  "rechnung_ust":    "<page-level USt/VAT total, dot-decimal, or null>",
  "rechnung_brutto": "<page-level Brutto total, dot-decimal, or null>",
  "gesamtbetrag":    "<Gesamtbetrag from ABRECHNUNGSBRIEF cover only, or null>",
  "manifest": [
    {{
      "land": "<DE|AT|CH|IT|BE>",
      "rechnungsnummer": "<RN>",
      "datum": "<date as shown>",
      "waehrung": "<EUR|CHF>",
      "betrag_lw": "<local-currency amount, dot-decimal, or null if same as EUR>",
      "betrag_eur": "<EUR amount, dot-decimal>"
    }}
  ]
}}
(manifest is null for all non-abrechnungsbrief pages)
"""


_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def extract_page(
    img_path: Path,
    seite: int,
    total: int,
    pdf_name: str,
    retries: int = 3,
) -> PageResult:
    """Send one page image to Claude claude-opus-4-7 and parse the JSON response."""
    raw_bytes = img_path.read_bytes()
    image_b64 = base64.standard_b64encode(raw_bytes).decode()
    media_type = _MEDIA_TYPES.get(img_path.suffix.lower(), "image/jpeg")
    prompt = _PROMPT_TEMPLATE.format(seite=seite, total=total, filename=pdf_name)

    last_err = None
    for attempt in range(retries):
        try:
            msg = _client().messages.create(
                model="claude-opus-4-7",
                max_tokens=2048,
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            raw_text = msg.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            d = json.loads(raw_text)
            return PageResult.from_dict(pdf_name, seite, d)

        except (json.JSONDecodeError, anthropic.APIError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/{retries}] {e} — wait {wait}s")
            time.sleep(wait)

    result = PageResult.from_dict(pdf_name, seite, {"seiten_typ": "fehler"})
    result.flags.append(f"vision_failed: {last_err}")
    return result


_RECOVERY_PROMPT = """\
A vehicle's transaction block is split across the page(s) shown.
The "SUMME KARTE/KFZ" total row (or equivalent per-card total) may not be visible — that is OK.

Target vehicle Kennzeichen / Cardholder: {kz}

Find EVERY individual transaction row on these page(s) that belongs to this card/vehicle.
Each row shows amounts — sum them:
  Sum all Netto/EXCL.VAT values → total netto
  Sum all USt/VAT values → total ust
  Dominant article type → artikel
  Negative amounts (Nachlass/discount) are VALID — include them in the sum.

Return ONLY this JSON (dot as decimal separator, no markdown):
{{
  "kennzeichen": "{kz}",
  "artikel": "<dominant article>",
  "netto": "<sum of netto, dot-decimal>",
  "ust":   "<sum of ust, dot-decimal>",
  "brutto":"<netto + ust, dot-decimal>"
}}

If you find zero rows for this vehicle/card, return null for all numeric fields.
"""


def recover_split_kz(
    img_paths: list[Path],
    kz: str,
    retries: int = 3,
) -> dict | None:
    """3rd-pass targeted recovery: sum individual transaction rows for one KZ.

    Used when SUMME KARTE/KFZ is not visible on any page (split-block miss).
    Returns dict with kennzeichen/artikel/netto/ust/brutto, or None on failure.
    """
    prompt = _RECOVERY_PROMPT.format(kz=kz)
    content = []
    for img_path in img_paths:
        raw_bytes = img_path.read_bytes()
        image_b64 = base64.standard_b64encode(raw_bytes).decode()
        media_type = _MEDIA_TYPES.get(img_path.suffix.lower(), "image/jpeg")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_b64},
        })
    content.append({"type": "text", "text": prompt})

    last_err = None
    for attempt in range(retries):
        try:
            msg = _client().messages.create(
                model="claude-opus-4-7",
                max_tokens=512,
                system=_SYSTEM,
                messages=[{"role": "user", "content": content}],
            )
            raw_text = msg.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            return json.loads(raw_text)
        except (json.JSONDecodeError, anthropic.APIError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/{retries}] {e} — wait {wait}s")
            time.sleep(wait)
    print(f"    recovery_failed: {last_err}")
    return None
