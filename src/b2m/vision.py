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
        api_key   = os.environ.get("ANTHROPIC_API_KEY", "")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        if api_key:
            _CLIENT = anthropic.Anthropic(api_key=api_key)
        elif auth_token:
            _CLIENT = anthropic.Anthropic(auth_token=auth_token)
        else:
            raise RuntimeError("Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")
    return _CLIENT


_SYSTEM = """\
You extract structured data from B2Mobility GmbH fuel/energy invoices (German).
Respond with valid JSON only — no markdown fences, no commentary.
All numeric values use dot as decimal separator (e.g. 1234.56, not 1.234,56).
If a value is absent or not applicable, use null.
"""

_PROMPT_TEMPLATE = """\
This is page {seite} of {total} from file "{filename}".

ORIENTATION NOTE:
- Middle pages (RECHNUNG pages) are landscape invoices, rendered correctly (wide × tall).
- Page 1 (ABRECHNUNGSBRIEF) and last page (ZUSAMMENSTELLUNG) are portrait documents.

Extract EXACTLY this JSON structure:

{{
  "seiten_typ": "<one of: abrechnungsbrief | rechnung | zusammenstellung>",
  "rechnungsnummer": "<8–10 digit number from 'Rechnung - Nr.:' header, or null>",
  "positionen": [
    {{
      "kennzeichen": "<license plate from 'Karte:' line, e.g. DAH-N 902>",
      "artikel": "<dominant article type in this Karte block, e.g. LKWDiesel or Strom>",
      "netto": "<Netto EUR from 'SUMME KARTE/KFZ' row for this Karte, dot-decimal>",
      "ust":   "<USt-Betrag EUR from 'SUMME KARTE/KFZ' row, dot-decimal>",
      "brutto":"<Brutto EUR from 'SUMME KARTE/KFZ' row, dot-decimal>"
    }}
  ],
  "rechnung_netto":  "<total Netto EUR for whole page (SUMME or SUMME KARTEN/KFZ row), dot-decimal, or null>",
  "rechnung_ust":    "<total USt-Betrag EUR for whole page, dot-decimal, or null>",
  "rechnung_brutto": "<total Brutto EUR for whole page, dot-decimal, or null>",
  "gesamtbetrag":    "<Gesamtbetrag from ABRECHNUNGSBRIEF page 1 only, dot-decimal, or null>"
}}

RULES:
- abrechnungsbrief  → positionen=[], fill gesamtbetrag, rechnung_* may be null
- rechnung          → one position per Karte block (use SUMME KARTE/KFZ row values)
                      rechnungsnummer from top-right header
- zusammenstellung  → positionen=[], fill rechnung_netto/ust/brutto from GESAMT row
- Kennzeichen: exact text after the card number on the 'Karte:' line
- Artikel: most common article in that Karte block (LKWDiesel / Diesel / Strom / etc.)
- If a Karte has multiple article types, pick the one with the highest Netto share
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
            # Strip accidental markdown fences
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

    # Return empty result flagged as failed
    result = PageResult.from_dict(pdf_name, seite, {"seiten_typ": "fehler"})
    result.flags.append(f"vision_failed: {last_err}")
    return result
