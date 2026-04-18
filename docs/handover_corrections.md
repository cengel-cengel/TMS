# Handover-Korrekturen

Korrekturen zu Fehlern im ursprünglichen Handover-Dokument, identifiziert
durch Daten-Cross-Check (Etappe 6c, 2026-04-18).

---

## Sika ATM — KNR-Korrekturen

### 1. KNR 493163 existiert nicht (Zahlendreher)

**Handover-Angabe:** „Sika ATM DE 2nd → KNR 493163"  
**Korrekt:** KNR **491063** (nicht 493163)

Verifizierung: KNR 493163 hat 0 Treffer in allen 36 Spalten und 3.590 Zeilen der
AX-Abrechnungsstrecken (Sika.xlsx). KNR 491063 hingegen hat 519 Zeilen mit
`Name = "Sika Deutschland CH AG & Co KG"` und `Betrag = 445.116 EUR`.

**Betroffene Entität:** Sika Deutschland GmbH & Co. KG, 70439 Stuttgart  
**ERKA-Kundennr:** 25607

---

### 2. KNR 527406 = Sika Automotive AG (CH), NICHT Sika Deutschland

**Handover-Angabe:** KNR 527406 → „Sika ATM CH" (korrekt) — aber verknüpft mit
Stuttgarter Versender-PLZ 70499/70499, was zu Verwechslung mit 25607 führen kann.

**Klarstellung:** KNR 527406 wird in der AX-Ära mit `Name = "Sika Automotive AG"`
geführt (464 Zeilen, 262.727 EUR). Der physische Versender ist
„Sika Automotive AG c/o LSU Schäberl" aus Stuttgart — aber der **Rechnungsempfänger**
(ERKA-Kundennr 18748) ist die **Sika Automotive AG, Kreuzlingerstrasse 35, 8590 Romanshorn, CH**
(VAT CHE116323165).

KNR 491063 (erka 25607) = Sika Deutschland GmbH & Co. KG  
KNR 527406 (erka 18748) = Sika Automotive AG (CH)

---

### 3. KNR 413276 in AX als Null-Konto geführt

**Handover-Angabe:** KNR 413276 → „Sika ATM DE" (89 Zeilen in Abrechnungsstrecken)  
**Ergänzung:** In der AX-Ära hat KNR 413276 **Betrag = 0 EUR** in allen 89 Zeilen.
Die tatsächlichen Erlöse für `Sika Automotive Deutschland GmbH` laufen in AX über
das Konto **ARA1802357** (514 Zeilen, 107.114 EUR).

Für Dinas-Ära-Berechnungen (Leistungsdatum ≤ 26.09.2025): KNR 413276 verwenden.  
Für AX-Ära-Berechnungen (Leistungsdatum ≥ 27.09.2025): ARA1802357 verwenden.  
Implementiert als Dual-Mapping in `src/tms/dinas/knr_mapping.py` (erka 18894).

---

## Sika SSC — Ergänzungen

### 4. ERKA-Kundennr 15550 = SSC (nicht Sika Polyurethane Italy)

**Handover / knr_mapping.py-Kommentar:** „15550 → unknown (seen in correction invoices,
Sika Polyurethane Italy)"

**Korrekt:** erka 15550 hat als **Rechnungsempfänger** durchgängig
`SIKA SUPPLY CENTER AG, Industriestr. 26, 6060 Sarnen, CH` (5/5 Stichproben).
`Sika Polyurethane` ist der **Absender** (Von-Ort Cerano IT / Alcobendas ES),
nicht der Rechnungsempfänger. → KNR **511241**.

### 5. Zusätzliche SSC-ERKA-Nummern identifiziert

Über die bereits bekannten 14466/14464 hinaus gehören folgende ERKA-Nrn zur SSC:

| ERKA-Nr | Records | Merkmal |
|---|---|---|
| 14465 | 94 | Randnummer, gleicher Fibu-Konto 13890 |
| 14468 | 3 | Minor, gleicher Fibu-Konto 13890 |
| 13890 | 234 | Neuere Nomenklatur (erka_knr = Fibu-Konto) |
| 15550 | 465 | Inbound IT/ES→DE (s.o.) |

Alle → KNR **511241**.
