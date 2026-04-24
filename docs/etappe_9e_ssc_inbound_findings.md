# Etappe 9e — SSC Inbound Calculator: Findings-First

**Status:** Vorarbeit — Calculator-Build noch nicht gestartet  
**Erstellt:** 2026-04-23 | **Kontext:** STOP-Befund E1 aus Sika-Re-Run Schritt 1

---

## Scope

Etappe 9e baut einen SSC Inbound Calculator für Routen, die vom SSC Export-Calculator
(SSC Stellplatz-Offerte 2026) nicht abgedeckt werden: Stückgut-Sendungen von
IT-28065 (Cerano) und ES-28108 (Alcobendas) nach DE-70499 Stuttgart.

**KNR:** 511241 (Sika Supply Center AG)  
**Routing:** IT-28065 → DE-70499 Stuttgart / ES-28108 → DE-70499 Stuttgart  
**Rate-Basis:** Anzahl Paletten (1–34), Flatpreis pro Sendung  
**DLV-Datei:** `data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Deutschland GmbH Stuttgart/2026/20251216_Sika Supply_Import Spanien und Italien 2026.xlsx`

---

## DLV-Struktur

**Gültig:** 01.01.2026 – 31.12.2026  
**Sheet:** Offerte

| Paletten | Max. Gewicht | Preis/Sendung |
|----------|--------------|---------------|
| 1 | 600 kg | 168,23 € |
| 2 | 1.200 kg | 275,35 € |
| 3 | 1.800 kg | 389,87 € |
| 4 | 2.400 kg | 500,85 € |
| 5 | 3.000 kg | 550,37 € |
| 6 | 3.600 kg | 621,11 € |
| 7 | 4.200 kg | 691,96 € |
| 8 | 4.800 kg | 762,59 € |
| 9 | 5.400 kg | 833,34 € |
| 10 | 6.000 kg | 904,07 € |
| 11 | 6.600 kg | 974,70 € |
| 12 | 7.200 kg | 1.045,45 € |
| 13 | 7.800 kg | 1.116,19 € |
| 14 | 8.400 kg | 1.187,04 € |
| 15 | 9.000 kg | 1.257,67 € |
| 16 | 9.600 kg | 1.328,40 € |
| 17 | 10.200 kg | 1.399,15 € |
| 18 | 10.800 kg | 1.469,89 € |
| 19 | 11.400 kg | 1.540,63 € |
| 20 | 12.000 kg | 1.611,26 € |
| 21 | 12.600 kg | 1.682,11 € |
| 22 | 13.200 kg | 1.752,85 € |
| 23 | 13.800 kg | 1.823,48 € |
| 24 | 14.400 kg | 1.894,23 € |
| 25 | 15.000 kg | 1.964,44 € |
| 26 | 15.600 kg | 2.033,19 € |
| 27 | 16.200 kg | 2.103,10 € |
| 28 | 16.800 kg | 2.159,31 € |
| 29 | 17.400 kg | 2.228,08 € |
| 30 | 18.000 kg | 2.288,78 € |
| 31 | 18.600 kg | 2.323,25 € |
| 32 | 19.200 kg | 2.365,89 € |
| 33 | 19.800 kg | 2.382,18 € |
| 34 | 20.400 kg | 2.400,78 € |

**Komplett-LKW:** LKW 1: 1.562 € / LKW 2: 1.645 €  
**Dieselfloater:** Quartalswert ab 01.03.2024 (separat, nicht in Flatpreis)  
**DE-Maut:** zzgl. gem. Anlage DE-Maut ab 202312  
**AT-Maut:** inkludiert für IT-28065; nicht relevant für ES-28108  
**ADR-Zuschlag:** inkludiert

---

## BI-Datenstand (Stand 2026-04-23)

| Metrik | Wert |
|--------|------|
| SSC DE-Inbound gesamt (KNR 511241, Empf. Land DE) | 663 Zeilen |
| Empfänger PLZ | 70499 (Stuttgart) |
| Herkunft IT-28065 | 461 Zeilen |
| Herkunft ES-28108 | 201 Zeilen |
| Sonstige Herkunft | 1 Zeile |
| Stellplätze (ø) | 32,7 |
| Erlöse Fracht (ø) | 952,80 € |
| Erlöse Fracht (max) | 2.382,18 € |

---

## §8-Notiz: DLV-Lücke >34 Paletten

> **§8-Kandidat:** Im BI-Datensatz erscheinen SSC Inbound-Zeilen mit Stellplätze = 35 und 36
> (Stichprobe: 2 Zeilen identifiziert, max. Stellplätze = 36). Das DLV deckt nur 1–34 Paletten.
>
> **Mögliche Erklärungen:**
> 1. **Cap-Regel:** AX rechnet mit dem 34-Paletten-Satz auch für 35/36 Paletten
>    (impliziter Cap im System).
> 2. **Proportionale Extrapolation:** AX rechnet linear über 34 Paletten hinaus
>    (außerhalb DLV-Scope, nicht durch Vereinbarung gedeckt).
> 3. **Sondervereinbarung:** Eine separate Komplett-LKW-Vereinbarung greift bei > 34 Paletten
>    (DLV nennt LKW 1: 1.562 € / LKW 2: 1.645 €, aber ohne PLZ-Zuordnung).
> 4. **DLV-Lücke analog SSC-ES/PLZ-03:** Strukturelle Tarifabdeckungslücke, die als
>    §8-Klärungsfall zu dokumentieren ist.
>
> **Status:** Ungeklärt — in Etappe 9e Findings-First aufzuklären vor Calculator-Build.
> Anzahl betroffener Zeilen: geschätzt < 10. EUR-Impact abhängig von Klärung.

---

## Vorgehen Etappe 9e (nach Abschluss 9d)

1. **Findings-First:** BI-Daten SSC Inbound analysieren (Stellplätze-Verteilung,
   Erlöse vs. DLV-Soll, Muster-A-Check für ERKA-Floater)
2. **>34-Paletten-Klärung:** AX-Konfiguration für SSC Inbound prüfen (Cap vs. Extrapolation)
3. **Calculator-Build:** `SSCInboundCalculator` in `src/tms/tariff/calculators/ssc_inbound.py`
   — Paletten-Lookup (1–34, dann Cap oder LKW-Rate), Versender-PLZ-Validierung
4. **Integration-Test:** Gegen BI-Daten, erwartete Pass-Rate > 90 %
5. **Report:** 9e-Befundbericht mit Ergebnis-Tabelle und §8-Klärungsfällen

---

*Erstellt: 2026-04-23. Etappe 9e beginnt nach Abschluss Sika-Re-Run (Etappe 9d).*
