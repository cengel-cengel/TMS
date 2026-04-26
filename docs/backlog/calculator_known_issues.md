# Calculator Known Issues

**Stand:** 2026-04-26 | **Pflege:** nach jedem Kunden-Onboarding aktualisieren

---

## EBM (KNR 410844) — EBMCalculator

### Issue EBM-1: `shipment_date`-Parameter fehlt in `calculate()`

**Datei:** `src/tms/tariff/calculators/ebm.py`
**Priorität:** Niedrig (kein aktueller Impact)

`EBMCalculator.calculate()` hat keinen `shipment_date`-Parameter.
DLV-Auswahl (2025-DLV vs. 2026-DLV) liegt beim Aufrufer. Die v1.9.4-Pipeline hat
ausschließlich die 2026-DLV verwendet.

**Heutiger Impact:** Keiner — alle Raten sind identisch zwischen 2025- und 2026-DLV
(IE, SK, PL, EE, HR, SI). Geprüft 2026-04-26 (Anhang F in EBM Cluster-Report).

**Fix vor:** Etappe 10, falls 2027-DLV abweichende Raten enthält.

**Fix:** `calculate()` um `shipment_date: date | None = None` erweitern.
Interner DLV-Switch auf Basis der Validity-Konstanten:
```python
if shipment_date and shipment_date <= _VALID_2025_TO:
    self._dlv_file = _DLV_2025_FILE
else:
    self._dlv_file = _DLV_FILE
```

---

### Issue EBM-2: `_lookup()` first-match-wins ohne Sender-PLZ-Disambiguierung

**Datei:** `src/tms/tariff/calculators/ebm.py`, Methode `_lookup()`
**Priorität:** Niedrig (AX ist korrekt, Audit-Artefakt erklärt)

Die 2026-DLV enthält zwei Einträge für SK-905 01 (n=31–33):
- Eintrag 1: 960 EUR (74673-Mulfingen-Standard)
- Eintrag 2: 1.100 EUR (PLZ-1380-Override)

`_lookup()` iteriert `self._tariff_rows` und gibt den **ersten Treffer** zurück.
Für Sendungen ab PLZ 1380 liefert die Methode 960 EUR statt 1.100 EUR.

**Impact:** EBM Cluster-Report v1.9.4 wies +2.021 EUR als Mx-DQ aus —
tatsächlich ein Audit-Artefakt. AX fakturiert korrekt 1.100 EUR.
Kein Rückforderungsanspruch. Operatives-Followup-Memo obsolet.

**Fix:** `_lookup()` um optionalen `sender_plz: str | None = None`-Parameter erweitern.
Wenn `sender_plz` gesetzt und mehrere Rows für denselben Empfänger-PLZ vorhanden,
Zeile mit sender-spezifischem Override priorisieren (oder beide zurückgeben für
manuelle Entscheidung).

---

## Fischerwerke (KNR 409480) — FischerwerkeCalculator

### GEFIXT 2026-04-26, Commit `ef3f03c`

| Bug | Beschreibung | Fix |
|-----|-------------|-----|
| Bug A | `_parse_dlv_file()` suchte "Ab frei geladen" nur in Spalte 0; 2026-Dateien haben den Header in Spalte 2 | Alle-Spalten-Suche + `col_offset` Tracking |
| Bug B | `"Stellplatz"` (Singular) nicht als Tabellen-Header erkannt | `_STPL_HEADERS` Frozenset mit allen Varianten |
| Bonus | Keine Jahres-basierte Gültigkeitsinferenz → 2025- und 2026-DLV kollidierten | Parent-Verzeichnis-Jahr als Fallback |

**Geprüfte Lanes:** IE (2025/2026), BE (2025/2026), AT-5280 (2025/2026), GR (2025), IT (2025/2026), DK (2025/2026)

---

## Andere Calculators — Offene Prüfung

### TODO: Beim Onboarding jedes neuen Kunden prüfen

| Calculator | Prüfung | Status |
|-----------|---------|--------|
| GEZECalculator | shipment_date, multi-DLV, validity parsing | Ausstehend (Etappe 9b) |
| CHTCalculator (alle 5 Länder) | shipment_date, DLV-Jahresauswahl | Ausstehend (Etappe 9c) |
| HERMACalculator | wie Fischerwerke: col_offset, header-variants, validity | Ausstehend (Etappe 9e/10) |
| BitzerCalculator | tbd | Ausstehend |
| GrozBeckertCalculator | tbd | Ausstehend |

**Checkliste für neuen Calculator:**
1. Hat `calculate()` einen `shipment_date`-Parameter?
2. Wird bei mehrjährigen Audits das richtige DLV-Jahr gewählt?
3. Hat `_load_sheet()` / Äquivalent einen `col_offset`-Mechanismus?
4. Sind alle Header-Varianten (Singular/Plural, Umlaute/ASCII) abgedeckt?
5. Gibt es `_lookup()` first-match-wins Risiken bei mehrfachen Einträgen pro PLZ?
