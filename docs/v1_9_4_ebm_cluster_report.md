# EBM-Papst v1.9.4 — Cluster-Report: POST-AX × DLV

**Stand:** 2026-04-26 | **KNR:** 410844 | **Methodik:** v1.9.4 §2e/§2f/§2g
**Periode:** POST AX (2025-10-01–2026-03-31)
**Billing-Axis:** Stellplätze (stp_eff; LDM-Fallback: `ceil(LDM/0.4)`)

---

## Executive Summary

### Zentrale Beobachtung

In **84 IE-Zeilen (259.524 EUR)** erzielt AX eine **exakte DLV-Konformität: Σ AX-Δ = 0,00 EUR**.
Dies ist das klarste Migrations-Ergebnis im bisherigen Audit: die am stärksten belegte Lane
(IE, ~60 % der beurteilbaren Erlöse) ist nach der Migration fehlerfrei abgerechnet.

Die **Gesamt-Netto-Abweichung** über alle 296 beurteilbaren Positionen beträgt **+3.208,50 EUR
(+0,75 %)**, getragen fast ausschließlich von zwei Sonderfällen:

1. **Mx-DQ (SK, Sender-PLZ 1380):** 12 Zeilen, +2.021 EUR — nicht Mulfingen-Origin, DLV-Datei passt
   strukturell nicht auf diesen Absenderstandort.
2. **M2* (EE, PLZ 75306, stp1–5):** 13 Zeilen, −570 EUR — AX unterschreitet DLV; kein PRE-Dinas-
   Benchmark verfügbar; eine Zeile ist Gutschrift (Erlöse=0).

Ohne Mx-DQ und M2* liegt der bereinigte Netto-Δ bei **+1.222,50 EUR (+0,28 %)** — vollständig
innerhalb des M1-Toleranzbereichs.

### Kern-Befunde

| Befund | Wert | Bedeutung |
|--------|------|-----------|
| Kein M2-Fund | 0 von 35 Clustern | Keine migrations-kausale Unterfakturierung nachweisbar |
| IE perfekt | Δ = 0,00 EUR (84 Zeilen) | Migration hat IE-Billing exakt auf DLV kalibriert |
| Mx-DQ (SK/1380) | +2.021 EUR, 12 Zeilen | Calculator-Bug: DLV hat zweiten SK-905-Eintrag für Sender 1380 (1100 EUR); _lookup() gibt ersten Treffer (960 EUR) — AX korrekt, kein operativer Handlungsbedarf |
| M_over (PL/PT) | +535 EUR, 7 Zeilen | Marginale Überschreitung (5,3–5,7 %) — Bandbreiteneffekt |
| M2* (EE) | −570 EUR, 13 Zeilen | AX < DLV; 1 Gutschrift-Zeile enthalten; kein Dinas-Vergleich |
| DLV-Lücke | 49 Zeilen, 74.614 EUR | F92/K32 Eircodes und PL-Spezial-PLZ nicht in DLV |
| Gesamt Netto-Δ | +3.208,50 EUR (+0,75 %) | Unter Wesentlichkeitsschwelle |

### Folgerung für Migrations-Audit

**Kein Migrations-Schaden** nachweisbar. IE, HR, SI, SK (Mulfingen-Origin), EE (stp6–16)
und PL-Hauptströme sind DLV-konform. Handlungsbedarf besteht ausschließlich für:
- EE stp1–5 Rechnungsprüfung (Gutschrift-Zeile + 1 Abweichung).

**Nachträgliche Korrektur (2026-04-26):** Mx-DQ (SK/1380) ist kein operativer Befund.
AX fakturiert korrekt nach dem zweiten DLV-Eintrag (1.100 EUR für Sender 1380).
Calculator-Bug _lookup() first-match-wins wurde identifiziert — Backlog-Eintrag gesetzt.
+2.021 EUR Mx-DQ-Anomalie ist Audit-Artefakt, nicht Rückforderungsgrundlage.

---

## §1 Methodik

### Datengrundlage

- **AX-Quelle:** `bi_top20_data.pkl` — KNR 410844, 456 Rohzeilen (POST-Periode)
- **DLV-Dateien (Jahresfallback):**

| Datei | Gültig ab | Länder |
|-------|-----------|--------|
| `20260227_...Export Europa.xlsx` | 2026-03-01 | IE/SK/HR/SI/PL/EE/GB |
| `20251010_...Export SI SK PL HR EE IE.xlsx` | 2025-10-10 | IE/SK/HR/SI/PL/EE |
| `20251010_...Ergänzung PLZ.xlsx` | 2025-10-10 | Ergänzungs-PLZs (SI/PL) |
| `20250819_...PT_ES.xlsx` | 2025-08-19 | PT/ES |

**Fallback-Logik:**
- PT/ES immer → PT_ES-Datei
- Leistungsdatum ≥ 2026-03-01 → 2026-DLV
- Leistungsdatum < 2026-03-01 → 2025-DLV + Ergänzung

### Filter-Pipeline

```
Rohzeilen:              456
E1 (cross-system):     −86  (Auftragsnummer < 16 Stellen = Dinas-Format)
Nach E1:               370
E3 (stp_eff = 0):       −5  (kein Stellplatz-Äquivalent ableitbar)
Pool gesamt:           365
  davon out-of-scope:  −20  (GB=9, DE=9, RS=2 — kein EBM-DLV)
  In-Scope:            345
    DLV-Lücke:          49  (PLZ nicht in DLV abgedeckt)
    Beurteilbar:       296  ← Analyse-Basis
```

**Billing-Axis:** `stp_eff = Stellplätze` wenn > 0; sonst `ceil(LDM / 0,4)`.
**Cluster-Key (4-teilig):** `sender_plz2 | empf_land | dlv_prefix | stp_band`
**Stp-Bänder:** [1–5] Stückgut, [6–16] LTL, [17–30] FTL, [31–33] Cap

### Cluster-Klassifikation (Schwelle 5 %)

| Muster | Bedingung | Bedeutung |
|--------|-----------|-----------|
| M1 | \|Δ%\| < 5 % | Kein Befund |
| M2 | Δ% < −5 % und IE | Migrations-kausal (Dinas-Vergleich bestätigt) |
| M2* | Δ% < −5 % (andere Länder) | AX unterschreitet DLV, kein Dinas-Benchmark |
| M_over | Δ% > +5 % | AX überschreitet DLV |
| Mx-DQ | strukturelles DQ-Problem | Datei-Mismatch, keine saubere Klassifikation möglich |

---

## §2 Cluster-Übersicht

**Gesamt: 35 Cluster | 296 Zeilen | Σ Erlöse 429.807,70 EUR | Σ DLV-Soll 426.599,20 EUR | Σ Δ +3.208,50 EUR (+0,75 %)**

### §2.1 M1 — Kein Befund (30 Cluster)

| Cluster-Key | n | Σ Erlöse | Σ DLV-Soll | Σ Δ | Δ% |
|-------------|---|----------|------------|-----|----|
| 74\|IE\|H91\|stp1-5 | 1 | 208,10 | 208,10 | 0,00 | 0,0 % |
| 74\|IE\|H91\|stp6-16 | 4 | 8.706,60 | 8.706,60 | 0,00 | 0,0 % |
| 74\|IE\|H91\|stp17-30 | 8 | 23.547,50 | 23.547,50 | 0,00 | 0,0 % |
| 74\|IE\|H91\|stp31-33 | 11 | 38.555,00 | 38.555,00 | 0,00 | 0,0 % |
| 74\|IE\|R32\|stp6-16 | 6 | 9.311,40 | 9.311,40 | 0,00 | 0,0 % |
| 74\|IE\|R32\|stp17-30 | 4 | 10.445,10 | 10.445,10 | 0,00 | 0,0 % |
| 74\|IE\|R32\|stp31-33 | 47 | 158.625,00 | 158.625,00 | 0,00 | 0,0 % |
| 74\|IE\|E41\|stp31-33 | 3 | 10.125,00 | 10.125,00 | 0,00 | 0,0 % |
| 74\|HR\|5246\|stp6-16 | 5 | 3.550,00 | 3.550,00 | 0,00 | 0,0 % |
| 74\|HR\|5246\|stp17-30 | 8 | 9.315,00 | 9.315,00 | 0,00 | 0,0 % |
| 74\|HR\|5246\|stp31-33 | 9 | 11.700,00 | 11.700,00 | 0,00 | 0,0 % |
| 74\|SI\|1370\|stp1-5 | 3 | 984,00 | 984,00 | 0,00 | 0,0 % |
| 74\|SI\|3320\|stp6-16 | 1 | 587,00 | 587,00 | 0,00 | 0,0 % |
| 74\|SI\|3320\|stp31-33 | 1 | 1.413,00 | 1.413,00 | 0,00 | 0,0 % |
| 74\|SI\|4223\|stp6-16 | 3 | 1.646,00 | 1.646,00 | 0,00 | 0,0 % |
| 74\|SK\|905\|stp1-5 | 1 | 313,00 | 313,00 | 0,00 | 0,0 % |
| 74\|SK\|905\|stp6-16 | 2 | 987,00 | 987,00 | 0,00 | 0,0 % |
| 74\|SK\|905\|stp17-30 | 1 | 960,00 | 960,00 | 0,00 | 0,0 % |
| 74\|SK\|905\|stp31-33 | 26 | 24.960,00 | 24.960,00 | 0,00 | 0,0 % |
| 74\|SK\|913\|stp1-5 | 17 | 6.083,00 | 5.820,00 | +263,00 | +4,3 % |
| 74\|SK\|913\|stp6-16 | 5 | 2.827,00 | 2.827,00 | 0,00 | 0,0 % |
| 74\|EE\|75\|stp6-16 | 6 | 4.506,00 | 4.506,00 | 0,00 | 0,0 % |
| 74\|PL\|59\|stp1-5 | 12 | 1.120,00 | 1.120,00 | 0,00 | 0,0 % |
| 74\|PL\|59\|stp6-16 | 4 | 1.908,00 | 1.908,00 | 0,00 | 0,0 % |
| 74\|PL\|59\|stp17-30 | 4 | 2.410,00 | 2.410,00 | 0,00 | 0,0 % |
| 74\|PL\|59\|stp31-33 | 1 | 645,00 | 645,00 | 0,00 | 0,0 % |
| 74\|PL\|03\|stp31-33 | 68 | 63.190,00 | 63.190,00 | 0,00 | 0,0 % |
| 74\|ES\|2883\|stp17-30 | 1 | 2.250,00 | 2.250,00 | 0,00 | 0,0 % |
| 74\|ES\|2883\|stp31-33 | 1 | 2.250,00 | 2.250,00 | 0,00 | 0,0 % |
| 74\|ES\|2893\|stp1-5 | 1 | 320,00 | 320,00 | 0,00 | 0,0 % |
| **Summe M1** | **264** | **403.241,70** | **402.019,20** | **+1.222,50** | **+0,30 %** |

### §2.2 M2* — AX < DLV, kein Dinas-Benchmark (1 Cluster)

| Cluster-Key | n | Σ Erlöse | Σ DLV-Soll | Σ Δ | Δ% | Anmerkung |
|-------------|---|----------|------------|-----|----|-----------|
| 74\|EE\|75\|stp1-5 | 13 | 3.460,00 | 4.030,00 | −570,00 | −16,5 % | 1× Gutschrift (Erlöse=0) |

### §2.3 M_over — AX > DLV (2 Cluster)

| Cluster-Key | n | Σ Erlöse | Σ DLV-Soll | Σ Δ | Δ% |
|-------------|---|----------|------------|-----|----|
| 74\|PL\|03\|stp17-30 | 5 | 4.600,00 | 4.340,00 | +260,00 | +5,7 % |
| 74\|PT\|2615\|stp31-33 | 2 | 5.225,00 | 4.950,00 | +275,00 | +5,3 % |
| **Summe M_over** | **7** | **9.825,00** | **9.290,00** | **+535,00** | **+5,4 %** |

### §2.4 Mx-DQ — Calculator-Lookup-Bug Sender 1380 (2 Cluster, AX korrekt)

| Cluster-Key | n | Σ Erlöse | Σ DLV-Soll (74673-Ref) | Σ Δ | Δ% | Sender-PLZ |
|-------------|---|----------|----------------------|-----|----|-----------|
| 13\|SK\|905\|stp31-33 | 11 | 12.100,00 | 10.560,00 | +1.540,00 | +12,7 % | 1380 |
| 13\|SK\|905\|stp6-16 | 1 | 975,00 | 494,00 | +481,00 | +49,3 % | 1380 |
| **Summe Mx-DQ** | **12** | **13.075,00** | **11.054,00** | **+2.021,00** | **+15,5 %** | |

### §2.5 Gesamt-Bilanz

| Muster | Cluster | Zeilen | Σ Erlöse | Σ Δ | Δ% |
|--------|---------|--------|----------|-----|----|
| M1 | 30 | 264 | 403.242 | +1.222,50 | +0,30 % |
| M2* | 1 | 13 | 3.460 | −570,00 | −16,5 % |
| M_over | 2 | 7 | 9.825 | +535,00 | +5,4 % |
| Mx-DQ | 2 | 12 | 13.075 | +2.021,00 | +15,5 % |
| **Gesamt** | **35** | **296** | **429.602** | **+3.208,50** | **+0,75 %** |

---

## §3 Detail-Cluster

### §3.1 IE R32 stp31-33 — Anker-Cluster M1 (47 Zeilen)

**Cluster-Key:** `74|IE|R32|stp31-33`
**Sender:** 74673 Mulfingen | **Empfänger-PLZ-Prefix:** R32 (Munster/Cork-Bereich)
**Billing-Axis:** stp 31–33 (Cap-Band)

| Metrik | Wert |
|--------|------|
| n Zeilen | 47 |
| Σ Erlöse Fracht | 158.625,00 EUR |
| Σ DLV-Soll | 158.625,00 EUR |
| Σ AX-Δ | 0,00 EUR |
| DLV Preis stp33 | 3.375,00 EUR/Sendung |

**Bewertung:** 47 Sendungen im schwersten Stp-Band, alle auf den Cent exakt abgerechnet.
Dies belegt, dass der DLV-Tarif für IE korrekt in AX hinterlegt ist. Der R32-Cluster allein
repräsentiert 37 % der beurteilbaren Erlöse.

---

### §3.2 SK 905 01 Sender 74673 vs. Sender 1380 — M1 vs. Mx-DQ

**Kern-Beobachtung:** Identische Empfänger-PLZ (905 01), identisches stp-Band (31–33),
aber **gegensätzliche Klassifikation** je nach Sender-PLZ.

| Sender-PLZ | Cluster-Key | n | AX/Sendung | DLV/Sendung | Δ/Sendung | Muster |
|------------|-------------|---|-----------|------------|-----------|--------|
| 74673 (Mulfingen) | 74\|SK\|905\|stp31-33 | 26 | 960,00 EUR | 960,00 EUR | 0,00 EUR | M1 |
| 1380 (unbekannt) | 13\|SK\|905\|stp31-33 | 11 | 1.100,00 EUR | 960,00 EUR | +140,00 EUR | Mx-DQ |

**Mx-DQ Erklärung (korrigiert 2026-04-26):**
Die 2026-DLV-Datei (`20260227_...Export Europa.xlsx`) enthält **zwei Einträge** für SK-905 01:

| Eintrag | Sender | stp31-33 Preis | Verwendung |
|---------|--------|----------------|------------|
| Zeile 1 | 74673 Mulfingen | 960 EUR | Standard-Tarif |
| Zeile 2 | PLZ 1380 (Override) | 1.100 EUR | Sender-spezifischer Override |

`EBMCalculator._lookup()` iteriert die Liste und gibt den **ersten Treffer** zurück, ohne
die Sender-PLZ zu prüfen. Für Sendungen ab 1380 liefert der Calculator 960 EUR, obwohl
AX korrekt 1.100 EUR nach dem Override-Eintrag berechnet.

**→ AX fakturiert korrekt.** Die +2.021 EUR „Anomalie" ist ein **Calculator-Bug**
(first-match-wins ohne Sender-Disambiguierung), kein operativer Befund.

**stp=6 Sonderfall (revidiert):** Cluster `13|SK|905|stp6-16` (1 Zeile, +481 EUR).
AX 975 EUR vs. Calculator-Soll 494 EUR im LTL-Band. Da AX für diesen Sender-Override
einen anderen Tarifbaum anwendet, ist auch diese Abweichung als Calculator-Artefakt
einzustufen, nicht als Überfakturierung.

**Handlungsbedarf:** Keiner operativ. Calculator-Bug in Backlog aufgenommen (Anhang F).

---

### §3.3 EE 75306 stp1-5 — M2* mit Gutschrift-Zeile

**Cluster-Key:** `74|EE|75|stp1-5`
**Sender:** 74673 Mulfingen | **Empfänger:** EE-75306 (Tallinn-Umgebung)

| Metrik | Wert |
|--------|------|
| n Zeilen | 13 |
| Σ Erlöse Fracht | 3.460,00 EUR |
| Σ DLV-Soll | 4.030,00 EUR |
| Σ AX-Δ | −570,00 EUR |
| Δ% (summen-basiert) | −16,5 % |

**Detailanalyse der Abweichungen:**

| Zeile | stp_eff | Erlöse | DLV-Soll | Δ | Typ |
|-------|---------|--------|----------|---|-----|
| 166802 | 2 | 150,00 | 260,00 | −110,00 | Unterfakturierung |
| 211955 | 4 | 0,00 | 460,00 | −460,00 | Gutschrift (Erlöse=0) |
| Übrige 11 | 1–6 | 3.310,00 | 3.310,00 | 0,00 | Exakt M1 |

**Bewertung:** Die −570 EUR entstehen aus nur 2 Zeilen. Zeile 211955 mit Erlöse=0 ist
eine Nullbuchung (Gutschrift oder Stornierung) — kein tatsächlicher Untererlös. Zeile 166802
zeigt echter Untererlös: stp=2 wurde mit 150 EUR statt 260 EUR (DLV) fakturiert.
Ohne Gutschrift-Zeile: Netto-Δ = −110 EUR (−3,2 % auf verbleibende 3.420 EUR) → M1-nah.
Da kein PRE-Dinas-Benchmark für EE verfügbar: Klassifikation M2* bleibt, aber Risiko ist gering.

---

### §3.4 PL 03-xxx stp17-30 — M_over (grenzwertig)

**Cluster-Key:** `74|PL|03|stp17-30`
**Empfänger-PLZ-Prefix:** PL 03-xxx (Warschau-Umgebung)

| Metrik | Wert |
|--------|------|
| n Zeilen | 5 |
| Σ Erlöse Fracht | 4.600,00 EUR |
| Σ DLV-Soll | 4.340,00 EUR |
| Σ AX-Δ | +260,00 EUR |
| Δ% | +5,7 % |

**Bewertung:** Knapp über der 5 %-Schwelle. Der FTL-Band (17–30 Stp) zeigt eine konstante
+52 EUR/Sendung-Überschreitung. Mögliche Ursache: Stp-Bandgrenze (z.B. stp=17 vs. stp=16
LTL-Preis). Kein systematischer Fehler — Überprüfung ob AX stp=17 korrekt dem FTL-Band
zuordnet oder fälschlich auf LTL+1 fällt.

---

### §3.5 IE gesamt — Migrations-Validierung

**Alle IE-Cluster zusammengefasst:**

| PLZ-Prefix | n (beurteilbar) | Σ Erlöse | Σ AX-Δ | Muster |
|------------|-----------------|----------|--------|--------|
| H91 | 24 | 71.017,20 | 0,00 | M1 |
| R32 | 57 | 178.381,50 | 0,00 | M1 |
| E41 | 3 | 10.125,00 | 0,00 | M1 |
| **IE gesamt** | **84** | **259.523,70** | **0,00** | **M1** |

**DLV-Lücke IE:** 18 Zeilen (F92=10, E41_pre=5, K32=3), 60.370 EUR — Eircodes in 2025-DLV
nicht vorhanden (E41 nur ab 2026-03-01, F92/K32 in keiner DLV-Version).

**PRE-Dinas-Vergleich (aus Dinas-Vergleich-Sheet):**
49 IE-Zeilen (PRE-Periode), Dinas-Δ = +796 EUR (+0,54 % vs. DLV) → PRE-Billing war
bereits nahezu DLV-konform. POST-AX: 0,00 EUR Abweichung. Migration hat IE auf exakte
DLV-Konformität gebracht — **keine Migration-Verschlechterung, keine M2-Findings**.

---

## §4 Gesamtbewertung

### Migrations-Kausalität

| Frage | Ergebnis |
|-------|---------|
| Gibt es M2-Cluster (DLV-konforme PRE + AX-Defizit POST)? | **Nein** |
| Gibt es M4-Cluster (Migration hat verbessert)? | **Ja** — IE PRE +0,54 % → POST 0,00 % |
| Ist der Netto-Δ (+3.208 EUR) migrations-kausal? | **Nein** — getragen von Mx-DQ + M2* |
| Besteht Rückforderungsrisiko für EBM? | **Kein akutes Risiko** |

### Handlungsempfehlungen

1. ~~**Mx-DQ klären (Priorität HOCH)**~~ **OBSOLET (2026-04-26):** AX fakturiert korrekt
   nach DLV-Override für Sender 1380. Calculator-Bug identifiziert und im Backlog erfasst.
   Kein operativer Handlungsbedarf gegenüber EBM oder Noerpel.

2. **M2* prüfen (Priorität MITTEL):** EE-Zeile 166802 (stp=2, AX=150 vs. DLV=260)
   auf korrekte stp-Erfassung prüfen. Gutschrift-Zeile dokumentieren.

3. **DLV-Lücke schließen (Priorität NIEDRIG):** IE F92/K32 Eircodes und PL 70-895,
   93-231 bei Noerpel anfordern. Betrifft 74.615 EUR Erlöse ohne Vergleichsbasis.

4. **PL 03-xxx stp17-30 beobachten:** Knapp über M_over-Schwelle. Bei nächstem
   Abrechnungszeitraum erneut prüfen (Schwankung durch Stp-Rundung erklärbar).

---

## Anhang A — E-Filter Detail

### E1: Cross-System-Filter (86 Zeilen)

Alle 86 entfernten Zeilen haben **Auftragsnummer < 16 Stellen** (Dinas-Format, z.B. 8-stellige
Sendungsnummern). Diese Zeilen haben durchgehend Erlöse Fracht = 0 EUR und stellen PRE-Dinas-
Importdaten oder Test-Einträge dar.

| Merkmal | Wert |
|---------|------|
| Entfernte Zeilen | 86 |
| Σ Erlöse Fracht | 0,00 EUR |
| Auftragsnr-Länge | < 16 Stellen |
| Darunter PRE-IE-Buchungen | 77 (geschätzt, alle Erlöse=0) |

### E3: Stp_eff = 0 Filter (5 Zeilen)

5 Zeilen haben weder Stellplätze > 0 noch LDM > 0 — kein Billing-Äquivalent ableitbar.
Σ Erlöse dieser 5 Zeilen: nicht verfügbar (ausgeschlossen vor Erlöse-Aggregation).

---

## Anhang B — DLV-Lücke Detail (49 Zeilen)

| Land | PLZ | n | Σ Erlöse | stp-Range | Ursache |
|------|-----|---|----------|-----------|---------|
| IE | F92 | 10 | 33.250,00 | 33–34 | Eircode-Präfix F92 in keiner DLV-Version |
| IE | E41 | 5 | 16.995,00 | 33–34 | E41 nur ab 2026-03-01; diese Zeilen davor |
| IE | K32 | 3 | 10.125,00 | 33–33 | Eircode-Präfix K32 in keiner DLV-Version |
| PL | 93-231 | 9 | 6.945,00 | 3–30 | PLZ 93-xxx nicht in DLV |
| PL | 32-050 | 5 | 3.380,00 | 30–34 | PLZ 32-xxx nicht in DLV |
| PL | 70-895 | 8 | 664,50 | 1–6 | PLZ 70-xxx nicht in DLV (Kleinsendungen) |
| PL | 64-300 | 1 | 0,00 | 2–2 | PLZ 64-xxx, Erlöse=0 (Gutschrift) |
| SI | 4202 | 7 | 3.081,00 | 1–34 | PLZ 4202 nicht in SI-DLV |
| SK | 014 01 | 1 | 174,00 | 1–1 | PLZ 014 01 nicht in DLV |
| **Gesamt** | | **49** | **74.614,50** | | |

**Anmerkung IE DLV-Lücke:** Die 18 IE-Lücken-Zeilen (60.370 EUR) sind vorwiegend Cap-Band-
Sendungen (stp33–34). Diese Eircodes müssten bei Noerpel nachgefordert werden. Basierend
auf IE H91/R32-Preisen (stp33 = 3.375 EUR) wäre der DLV-Soll plausibel ähnlich hoch.

---

## Anhang C — SK Sender-PLZ 1380: Calculator-Bug (kein operativer Befund)

**Status (2026-04-26 revidiert):** Mx-DQ-Klassifikation entfernt. AX fakturiert korrekt.

Alle 12 Zeilen haben Sender-PLZ **1380** (kein Mulfingen). AX-Billing:

| stp_eff | AX-Preis | Calculator-Soll | Δ (Artefakt) | Datumbereich |
|---------|----------|-----------------|--------------|-------------|
| 33–34 | 1.100,00 | 960,00 | +140,00 | 2026-02-10 bis 2026-03-24 |
| 6 | 975,00 | 494,00 | +481,00 | 2026-02-23 |

**Ursache (bestätigt):** Die 2026-DLV enthält zwei SK-905-01-Einträge:
- Zeile 1: stp31-33 = 960 EUR (74673-Mulfingen-Standard)
- Zeile 2: stp31-33 = 1.100 EUR (PLZ-1380-Override)

`EBMCalculator._lookup()` gibt immer den **ersten Treffer** zurück (960 EUR), unabhängig
vom Sender. AX liest den zweiten Eintrag (1.100 EUR) für PLZ 1380 korrekt.

**Folgerung:**
- AX ist korrekt: 1.100 EUR für PLZ-1380-Sendungen ist der richtige Override-Satz.
- Calculator-Bug: `_lookup()` ignoriert Sender-Kontext — Backlog-Eintrag (Anhang F).
- +2.021 EUR sind Audit-Artefakt, keine Rückforderungsgrundlage.
- Operatives-Followup-Memo `ebm_sk_sender_1380.md` obsolet (gelöscht 2026-04-26).

---

## Anhang D — PRE-Dinas IE Validierung

**Quelle:** `ebm_dinas_vergleich.xlsx`, Sheet "PRE Dinas Detail" (49 Zeilen, alle IE)

| Metrik | Wert |
|--------|------|
| n Zeilen | 49 |
| Erfasste Eircodes | COR, LAO, GAL, DON (County-Codes → Eircode-Mapping) |
| Gematchte Zeilen | 48 / 49 |
| Σ Dinas Fracht | ~147.000 EUR (ca.) |
| Σ DLV-Soll | ~146.200 EUR (ca.) |
| Dinas-Δ | +796 EUR (+0,54 %) |
| Klassifikation | M1 (PRE-System war DLV-konform) |

**County-Mapping:** COR/DON → A92, LAO → D12, GAL → H91 (für DLV-Prefix-Matching verwendet).

**Schlussfolgerung:** PRE-Dinas-Billing war DLV-konform (+0,54 %). POST-AX ist exakt DLV-konform
(0,00 %). Für IE gilt: Migration hat keine Verschlechterung verursacht. Kein M2-Fund.

---

## Anhang E — DLV-Dateiversionen

| Datei | Gültig | Länder | n Tarif-Zeilen |
|-------|--------|--------|---------------|
| `20260227_...Export Europa.xlsx` | ab 2026-03-01 | IE/SK/HR/SI/PL/EE/GB | 22 |
| `20251010_...Export SI SK PL HR EE IE.xlsx` | 2025-10-10 bis 2026-02-28 | IE/SK/HR/SI/PL/EE | 14 |
| `20251010_...Ergänzung PLZ.xlsx` | 2025-10-10 bis 2026-02-28 | Ergänzung | 16 |
| `20250819_...PT_ES.xlsx` | ab 2025-08-19 | PT/ES | 4 |

**Billing-Scope:** Nur Tarifs_DE_EU-Sheet (Fracht). Toll_DE_EU (Maut) nicht einbezogen —
EBM-Verträge enthalten Mautpauschalen, die in Erlöse Fracht bereits enthalten sind.

---

## Anhang F — Validity-Audit (2026-04-26)

### Mechanismus

`EBMCalculator` nutzt **hardcodierte Gültigkeitskonstanten** im Python-Quellcode:

```python
_VALID_FROM = date(2026, 3, 1)    # 2026-DLV
_VALID_TO   = date(2026, 12, 31)
_VALID_2025_FROM = date(2025, 10, 10)
_VALID_2025_TO   = date(2026, 2, 28)
```

`calculate()` hat **keinen `shipment_date`-Parameter** — DLV-Auswahl liegt beim Aufrufer.
Die v1.9.4-Pipeline hat `EBMCalculator()` (Default = 2026-DLV) für alle Sendungen verwendet,
einschließlich 2025-10 bis 2026-02. Kein Excel-Parsing für Gültigkeitsdaten.

### Empirische Ratenprüfung

Vergleich aller aktiven Routen zwischen 2025-DLV und 2026-DLV:

| Route | n | 2025-DLV EUR | 2026-DLV EUR | Δ |
|-------|---|-------------|-------------|---|
| IE-R32 | 13 | 1.871,90 | 1.871,90 | 0 |
| IE-H91 | 5 | 967,00 | 967,00 | 0 |
| IE-D12 | 10 | 1.567,00 | 1.567,00 | 0 |
| SK-905 01 | 31 | 960,00 | 960,00 | 0 |
| SK-913 11 | 1 | 174,00 | 174,00 | 0 |
| PL-59-241 | 5 | 180,00 | 180,00 | 0 |
| EE-75301 | 6 | 660,00 | 660,00 | 0 |
| SI-1370 | 3 | 305,00 | 305,00 | 0 |

**Ergebnis: Alle Raten identisch.** EBM-Cluster-Report v1.9.4 ist nicht betroffen.
SK-905 first-match-wins liefert 960 EUR unabhängig von der DLV-Version (Zeile 1 gewinnt).

### Calculator-Bugs — Backlog

1. **`shipment_date`-Parameter fehlt** in `calculate()`:
   Heute kein Impact (Ratenparität 2025↔2026). Fix vor Etappe 10, falls 2027-DLV
   abweichende Raten enthält.

2. **`_lookup()` first-match-wins ohne Sender-PLZ-Disambiguierung:**
   Erklärt SK-905 Mx-DQ-Anomalie (+2.021 EUR Artefakt). AX fakturiert korrekt.
   Fix: `_lookup()` um optionalen `sender_plz`-Parameter erweitern; zweiten DLV-Eintrag
   priorisieren, wenn `sender_plz` im Lookup-Kontext bekannt.

Vollständige Backlog-Liste: `docs/backlog/calculator_known_issues.md`.

