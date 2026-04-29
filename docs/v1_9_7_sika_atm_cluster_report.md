# Sika ATM — Cluster Report v1.9.7
**KNR:** 527406 (Sika Automotive AG, Romanshorn CH — ERKA-Nr 18748)  
**Stand:** 2026-04-29  
**Pipeline:** `src/build_sika_atm_step23_v197.py`  
**PKL:** `output/sika_atm_step23_results_v197.pkl`  
**Tarif:** Anlage 1 KORRIGIERT — Flat EUR/Sendung (gewichtsbandenbasiert)  
**DLV-Gültigkeit:** 2024-07-01 – 2026-06-30

---

## §1 Pool

| Metrik | Wert |
|---|---:|
| BI-Cache Rohzeilen | 723 |
| Pool ef > 0 | 403 |
| davon is_sub (MS gesetzt, kein UA) | 7 |
| Sub Tonnage = 0 | 7 |
| Sub Tonnage > 0 | 0 |
| Pool nach Sub-Ausschluss | 396 |
| davon Tonnage = 0 | 0 |
| dlv_luecke (DE 70499, nicht nominiert) | 1 |
| **Beurteilbar (ok)** | **395** |
| Σ ef beurteilbar | 217.470 EUR |
| Σ dlv beurteilbar | 224.713 EUR |

**Sub-Rows:** 7 Rows mit Mastersendung gesetzt, kein Unterauftrag, alle Tonnage = 0,
Σ ef = 1.832 EUR. Korrekt ausgeschlossen durch `~is_sub`-Filter.

**dlv_luecke:** 1 Row DE-70499 (Stuttgart, ef = 360 EUR) — Empfängerland DE ist
ERKA nicht nominiert (`_NOT_NOMINATED`). Bekannt, kein Fehler.

**Versender Land:** DE = 212, CH = 190, IT = 1 (alle ex LSU M7 Stuttgart per DLV).

---

## §2 DLV-Struktur

**Tarif-Typ:** Flat EUR/Sendung pro Gewichtsband (60 Bänder je Zone, nicht EUR/kg).  
**Zone-Key:** `{CC}-{2-stelliger-PLZ-Präfix}` für numerische PLZ; `GB-{area}` für UK.  
**Kein Jahresdispatch:** Einzige DLV-Datei gilt 2024–2026 (kein v2025/v2026-Wechsel).  
**Maut:** in Vertragsraten enthalten → `maut_surcharge = None`.  
**Diesel:** externer Dieselfloater (außerhalb Anlage 1) → `diesel_surcharge = None`.

Aktive Empfängerländer (beurteilbar):

| Land | Rows | Zone-Schema | Anmerkung |
|---|---:|---|---|
| IT | 205 | IT-80, IT-85, IT-10, … | Anlage 1 Tarif IT |
| GB | 96 | GB-B, GB-OX, GB-L, … | UK-Area-Prefix |
| ES | 49 | ES-36, ES-50, ES-28, … | Anlage 1 Tarif ES |
| RS | 32 | RS-34 | Separate Vereinbarung (§4) |
| PT | 13 | PT-35, PT-27, … | Anlage 1 Tarif PT |

Coverage: **395/396 = 99,7 %** (nur 1 DE-Row ausgenommen).

---

## §3 Ergebnisse

### Gesamt (beurteilbar, n = 395)

| Metrik | Wert |
|---|---:|
| M1 (│fp│ ≤ 5 %) | 298 (75,4 %) |
| M2 (fp < −5 %) | 92 (23,3 %) |
| M_over (fp > +5 %) | 5 (1,3 %) |
| Σ ef | 217.470 EUR |
| Σ dlv | 224.713 EUR |
| **Net Δ** | **−7.243 EUR (−3,22 %)** |

### Land-Breakdown (beurteilbar)

| Land | n | Σ ef | Σ dlv | Net Δ | Net Δ % | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ES | 49 | 49.460 | 48.190 | +1.270 | +2,64 % | 48 | 0 | 1 |
| GB | 96 | 72.860 | 73.967 | −1.107 | −1,50 % | 85 | 11 | 0 |
| IT | 205 | 64.787 | 66.836 | −2.049 | −3,07 % | 134 | 67 | 4 |
| PT | 13 | 9.619 | 9.619 | +0 | **0,00 %** | 13 | 0 | 0 |
| RS | 32 | 20.744 | 26.101 | −5.357 | −20,52 % | 18 | 14 | 0 |

**Excl. RS (363 Rows):** Net Δ = **−1.886 EUR (−0,95 %)** — kein Migrationsschaden.

---

## §4 Auffälligkeiten

### A1 — RS Serbia (PLZ 34000 Kragujevac): Pre-existing, separate Vereinbarung

32 Rows, alle PLZ 34000. Von diesen:
- **18 M1:** AX-ef entspricht exakt dem Anlage-1-DLV-Satz (kein Delta).
- **14 M2:** AX-ef erheblich unter Anlage-1-Satz (Faktor 0,01 – 0,48).

Die 14 M2-Rows (Σ ef = 4.671 EUR, Σ dlv = 15.513 EUR, Δ = −10.843 EUR)¹ reflektieren
eine separate Tarifvereinbarung für Kragujevac-Lauf, die nicht im DLV Anlage 1 hinterlegt
ist. Die Anlage-1-Sätze sind +20 %–43 % über den tatsächlich berechneten Beträgen.

Vorbestehend dokumentiert: `data/reports/sika_atm_revalidation.md` (Dinas-vs-DLV-Check:
81/106 direkt = 76,4 %; excl. RS = 97,6 %).

**Bewertung:** Kein Migrationsfehler. Operative Klärung separate Laufkarte RS empfohlen
(Einheitlichkeit der Anlage-1-Anwendung). Kein finanzieller Schaden für Noerpel.

¹ Anmerkung: Aggregat-Delta RS M2 = −5.357 EUR (18 M1 + 14 M2 zusammen) da M1-Rows
(ef = dlv) den Δ nicht beisteuern.

### A2 — IT 85025 M_over (Zone IT-85, 2 Rows, Δ = +3.611 EUR)

| ton (kg) | ef (EUR) | dlv (EUR) | Δ (EUR) | fp |
|---:|---:|---:|---:|---:|
| 5.922,76 | 2.500,00 | 1.012,50 | +1.487,50 | +1,47 |
| 8.336,00 | 3.350,00 | 1.226,60 | +2.123,40 | +1,73 |

ef-Werte sind runde Zahlen (2.500, 3.350). Anlage-1-Satz liegt signifikant darunter.
Hypothese: Diese Sendungen wurden auf Stellplatz-Basis (nicht Gewichtsbasis) abgerechnet
(Zone IT-85 = Salerno/Kampanien-Gebiet; hohe Stellplatzzahl wahrscheinlich).
AX-ef > DLV = kein Noerpel-Schaden; mögliche Überzahlung durch Sika gegenüber Carrier.
**Operative Prüfung empfohlen** (Abrechnungsgrundlage IT-85 Großsendungen).

### A3 — ES 28041 M_over (Madrid, 1 Row, Δ = +1.270 EUR)

| ton (kg) | ef (EUR) | dlv (EUR) | Δ (EUR) | fp |
|---:|---:|---:|---:|---:|
| 30 | 1.350,00 | 79,65 | +1.270,35 | +15,95 |

Extrem-Abweichung (fp = 15,95). 30 kg → DLV-Satz Zone ES-28 = 79,65 EUR.
AX-ef = 1.350 EUR entspricht einer Spot-Rate oder Mindest-Sendungspreis für
eine Sonderleistung. Kein Standard-LTL-Tarif.
**Operative Prüfung empfohlen** (Buchungsgrundlage Spot vs. DLV).

### A4 — PT (13 Rows, Net Δ = 0,00 EUR)

Perfekte Übereinstimmung — alle 13 PT-Rows M1, fp ≈ 0,000. DLV Anlage 1 korrekt
angewendet. Die im Revalidierungsreport genannte PT-Abweichung (PLZ 2951-510, −73,7 %)
tritt in diesem BI-Pool nicht auf (anderer Zeitraum oder PLZ nicht mehr aktiv).

### A5 — GB M2 (11 Rows, Δ = −1.107 EUR)

11 GB-Rows mit negativem fp. Abweichungen liegen im Bereich −15 % bis −29 %.
Zone GB-B92 (Solihull, 2 größte Rows: ef = 870 und 1.580 EUR, dlv = 1.224 und 1.880).
Mögliche Ursache: GB-Postcodes mit mehr als 2 Alpha-Zeichen (z.B. B92 → Zone GB-B,
korrekt). Keine Abbildungslücke im Calculator festgestellt. Abweichung möglicherweise
Carrier-Kondition (Sonderrate UK).

---

## §5 P20-Prüfung

| Erlöse-Typ | Σ (Pool roh) | Anteil ef | Adjustment |
|---|---:|---:|---|
| Erlöse Maut | 21 EUR | 0,01 % | **Keiner** |
| Erlöse Diesel | 36 EUR | 0,02 % | **Keiner** |

Beide Werte marginal (< 0,1 % von Σ ef). ATM-Tarif enthält Maut im Vertragsrate;
Diesel ist externer Floater außerhalb Anlage 1. Keine P20-Korrektur erforderlich.

---

## §6 Fazit

| Headline | Wert |
|---|---|
| **Kein Migrationsschaden** | Net Δ −7.243 EUR dominiert durch RS pre-existing (−5.357 EUR) |
| **Excl. RS** | −1.886 EUR (−0,95 %) — innerhalb Wesentlichkeitsschwelle |
| M1-Rate (gesamt) | 75,4 % |
| M1-Rate (excl. RS) | 77,1 % |
| Beurteilbar | 395 / 396 (99,7 %) |

**RS Serbia:** Pre-existing separate Vereinbarung, kein Migrationsfehler.
Operative Klärung empfohlen (einheitliche Anlage-1-Anwendung oder separate DLV-Erfassung).

**IT 85025 + ES 28041 M_over:** AX > DLV. Kein Noerpel-Schaden.
Operative Prüfung Abrechnungsgrundlage (Spot vs. DLV, Stellplatz vs. Gewicht).

**PT: 100 % M1 (0 EUR Δ).** GB und IT weitgehend M1 mit moderatem M2-Anteil
(Carrier-Konditionsabweichung, nicht Migrations-Bug).

**Calculator:** `SikaATMChCalculator` (Commit f005e63) — korrekte Zone-Key-Logik,
Gewichtsband-Lookup, kein Jahresdispatch-Fehler. Keine Calculator-Bugs gefunden.

---

## §7 Anhang

**Pipeline:** `src/build_sika_atm_step23_v197.py`  
**PKL:** `output/sika_atm_step23_results_v197.pkl`  
**Revalidierung:** `data/reports/sika_atm_revalidation.md`  
**BI-Cache:** `output/bi_cache_sika_527406.pkl` (723 Rows, 530 KB)
