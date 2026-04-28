# Bitzer FR-13400 Aubagne — Tarifwahl-Klärung (H1-Fix + Rückfrage)

Stand: 2026-04-28  
Betroffener Kunde: Bitzer Kühlmaschinenbau GmbH (KNR 406345)  
Kategorie: Calculator-Bug-Fix + Offene Vertragsklärung

---

## Befund

PLZ **13400 (Aubagne)** hat ein eigenes Sonderziel-DLV als **per-Sendung FTL-Vertrag**:

| DLV | Gültigkeit | Minimum | bis 5000 kg | FTL |
|---|---|---|---|---|
| 2025: 20241213_Bitzer_Export FR-13400 Aubagne.xlsx | 01.01.2025–31.12.2025 | 697.50 EUR/Sendung | 697.50 EUR/Sendung | 1 772.60 EUR |
| 2026: 2026_Bitzer_Export FR-13400 Aubagne.xlsx | 01.02.2026–31.01.2027 | 711.45 EUR/Sendung | 711.45 EUR/Sendung | 1 808.05 EUR |

**Titelzeile des DLV:** *„Ab frei geladen DE-72108 Rottenburg bis frei Haus **Profoid**, FR-13400 Aubagne"*  
→ Das DLV ist explizit für Lieferungen an die Firma **Profoid** in Aubagne ausgestellt.

---

## Tatsächliche Abrechnung

13 BI-Zeilen für PLZ 13400 (POST-Periode, ef > 0) wurden **nicht** über das per-Sendung-DLV
abgerechnet, sondern über den **allgemeinen FR-Zonentarif Zone 9**:

| Tonnage | billing_kg | Erlöse Fracht | FR Zone 9 LTL | Abweichung |
|---:|---:|---:|---:|---:|
| 23.9 kg | 100 | 46.30 EUR | 46.30 (min) | 0.00 EUR |
| 500.0 kg | 500 | 142.00 EUR | 28.4 × 5 = 142.00 | 0.00 EUR |
| 800.0 kg | 800 | 176.00 EUR | Zone 9 800-Band | ~0.00 EUR |

FR Zone 9 Minimum (2025-DLV): 46.30 EUR → **exakter Match** mit BI-Werten.  
Das Sonderziel-DLV (697.50 EUR Minimum) wird in **keiner** BI-Zeile angewendet.

---

## Hypothesen-Prüfung

| Hypothese | Ergebnis |
|---|---|
| **H1: Calculator-Bug** — Selektor wählt fälschlich per-Sendung-DLV für LTL | **Bestätigt** — alle 13 Rows werden über Zone 9 abgerechnet |
| H2: Beide DLVs valide, AX hat LTL-Wahlentscheidung getroffen | Möglich für LTL-Teilladungen an Profoid |
| H3: DLV veraltet/obsolet | Offen — 2026-Version existiert, also aktiv gehalten |

---

## Fix implementiert (2026-04-28)

`FR-13400` wurde aus `_SPECIAL_DEST_PATHS["FR"]` in `bitzer.py` entfernt.  
PLZ 13xxx wird jetzt über den allgemeinen FR-Zonentarif geroutet → **Zone 9**.

**Auswirkung:**
- Vor Fix: 13 Rows × ≈ −623 EUR = **−8 109 EUR** (fälschlich M2)
- Nach Fix: 13 Rows × +0.46 EUR = **+6 EUR** (M1, korrekt)

---

## Offene Klärung mit Noerpel (ERKA)

> Bitzer-Sendungen nach FR-13400 Aubagne werden aktuell über den allgemeinen
> FR-Zonentarif Zone 9 abgerechnet (min. 46.30 EUR LTL). Es existiert ein separates
> Sonderziel-DLV für „Profoid, FR-13400 Aubagne" (min. 697.50 EUR/Sendung).
>
> **Klärungsbedarf:**
> 1. Gilt das Sonderziel-DLV für **alle** Bitzer-Sendungen nach PLZ 13400,
>    oder nur für dedizierte Direktfahrten an Profoid?
> 2. Welches Kriterium entscheidet (Lademeter-Schwelle? Stückzahl? Kundenwunsch)?
> 3. Sind die 13 LTL-Sendungen korrekt zu Zone 9 abgerechnet worden?

---

## Nächste Schritte

1. **ERKA-Anfrage stellen** (Noerpel Kundenbetreuer Bitzer)
2. **Nach Bestätigung Zone 9 = korrekt:** Fix bleibt, kein weiterer Handlungsbedarf
3. **Falls Profoid-DLV gilt:** `_SPECIAL_DEST_PATHS` wieder aktivieren;
   Kriterium (Lademeter o.ä.) als Filter-Parameter ergänzen
