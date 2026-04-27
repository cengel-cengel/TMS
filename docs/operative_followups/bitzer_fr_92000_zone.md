# ERKA-Anfrage: Bitzer FR PLZ 92000 (Hauts-de-Seine) — Zonenzuordnung fehlt

Stand: 2026-04-27  
Betroffener Kunde: Bitzer Kühlmaschinenbau GmbH (KNR 406345)  
Kategorie: Operativer Folgeauftrag — Fehlende Zonenzuordnung im FR-DLV

---

## Befund

PLZ-Prefix **92** (Hauts-de-Seine, z. B. 92000 Nanterre) ist in der aktuellen
FR-Zonentabelle des Bitzer-DLV nicht eingetragen. Der Calculator wirft einen
`LookupError` für alle FR-Sendungen mit PLZ 92xxx.

**Betroffene Sendungen (POST-Periode, Erlöse Fracht > 0):**

| Sendungsdatum | Versender PLZ | Empf. PLZ | Erlöse Fracht (EUR) | Tonnage frpfl. |
|---|---|---|---|---|
| POST | 71126 (Rottenburg) | 92000 | 87.00 | 300 kg |
| POST | 71126 (Rottenburg) | 92000 | 58.00 | 200 kg |
| POST | 71126 (Rottenburg) | 92000 | 87.00 | 300 kg |
| POST | 71126 (Rottenburg) | 92000 | 87.00 | 300 kg |
| POST | 04435 (Schkeuditz) | 92000 | 33.50 | 100 kg |
| POST | 04435 (Schkeuditz) | 92000 | 33.50 | 100 kg |
| POST | 04435 (Schkeuditz) | 92000 | 59.20 | 200 kg |

**Gesamt: 7 Sendungen, 445.20 EUR Erlöse Fracht**

---

## Analyse

### Implizite Zonenzuordnung aus BI-Daten

Die abgerechneten Erlöse entsprechen **Zone 4** (Rottenburg-Sendungen):
- 300 kg → billing_kg 300, Zone-4-Rate im Band ≤ 300 kg: 29.0 EUR/100 kg
  → 300 × 29.0 / 100 = **87.00 EUR** ✓
- 200 kg → billing_kg 200, Zone-4-Rate im Band ≤ 300 kg: 29.0 EUR/100 kg
  → 200 × 29.0 / 100 = **58.00 EUR** ✓

Die Schkeuditz-Werte zeigen leichte Abweichungen (33.50 statt 32.80 Minimum,
59.20 statt 58.00 für 200 kg), was auf eine leichte Raten-Anpassung in einer
späteren Tarifversion hindeutet — Grundzone aber ebenfalls Zone 4.

### Geografischer Kontext

PLZ 92 = Hauts-de-Seine (Département 92), Teil der Île-de-France.  
Im DLV bereits erfasste Île-de-France-Prefixe → Zone 4:
- **75** (Paris), **77** (Seine-et-Marne), **78** (Yvelines)
- **91** (Essonne), **95** (Val-d'Oise)

Ebenfalls fehlende Île-de-France-Prefixe zu prüfen:
- **93** (Seine-Saint-Denis), **94** (Val-de-Marne)

Zone 4 ist die geografisch konsistente Zuweisung für PLZ 92000.

---

## Erforderliche Klärung

**ERKA-Anfrage an Noerpel:**

> Bitzer-DLV (FR Zonentarif 2025): PLZ-Prefix 92 (Hauts-de-Seine) fehlt in der
> Zoneneinteilung. Auf Basis der Billing-Historie und der geografischen Nachbarn
> (91, 95 → Zone 4) lautet unsere Erwartung: **Zone 4**.
>
> Bitte bestätigen oder korrigieren Sie die offizielle Zonenzuordnung für:
> - PLZ 92 (Hauts-de-Seine) — erwartet Zone 4
> - PLZ 93 (Seine-Saint-Denis) — noch nicht in Daten, ebenfalls zu klären
> - PLZ 94 (Val-de-Marne) — noch nicht in Daten, ebenfalls zu klären
>
> Alternativ: Bitte aktualisierte Zonentabelle mit allen Île-de-France-Prefixen.

---

## Nächste Schritte

1. **ERKA-Anfrage stellen** (Noerpel Kundenbetreuer oder Tarifabteilung)
2. **Nach Bestätigung:** `_parse_zone_table()` in `bitzer.py` lädt den korrekten
   Zone-4-Eintrag automatisch, sobald das DLV aktualisiert wird.
3. **Interim-Fix (optional):** PLZ 92 als Zone 4 in `_COUNTRY_DLV` hardcoden,
   bis offizielles DLV-Update vorliegt.
4. **EUR-Impact bei Abweichung:** Falls Zone 3 korrekt wäre (Rate 300-Band: 27.7
   statt 29.0), wäre die Differenz 300 × (29.0 − 27.7) / 100 = **3.90 EUR je
   Sendung** — bei 7 Sendungen ca. 27 EUR Gesamt-Δ. Beurteilbar erst nach ERKA.
