# ERKA-Kundennummer → Rechnungsempfänger Mapping

**Stand:** 2026-04-18  
**Quelle:** PDF-Extraktion aus `data/parsed/dinas_pdfs.parquet` (5.533 Records, 496 PDFs)  
**Methode:** Wortextraktion via PyMuPDF aus Seite 1, y=155–205, x<300 (linke Spalte = Empfänger)  
**Konsistenz:** Jede erka_kundennr durch 3–5 Stichproben verifiziert (außer n=1)

---

## Sika-Gesellschaften (bestätigt / zu bestätigen)

| erka_knr | Datensätze | Empfänger (exakt wie auf PDF) | Straße | PLZ | Stadt | Land | USt-ID Empf. | Fibu-Konto | Dinas KNR | Sika-Zuordnung |
|---|---|---|---|---|---|---|---|---|---|---|
| **14466** | 201 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ✓ | Sika SSC — bestätigt |
| **14464** | 201 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ✓ | Sika SSC — bestätigt (ältere Variante) |
| **14465** | 94 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ? | Sika SSC — Bestätigung ausstehend |
| **14468** | 3 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ? | Sika SSC — Bestätigung ausstehend |
| **13890** | 234 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ? | Sika SSC — neuere Rechnungen (erka_knr = Fibu-Konto) |
| **15550** | 465 | SIKA SUPPLY CENTER AG | INDUSTRIESTR. 26 | 6060 | SARNEN | SCHWEIZ | — (CH) | 13890 | **511241** ? | Sika SSC — inkl. Korrekturrechnungen |
| **25607** | 1064 | SIKA DEUTSCHLAND CH AG & CO. KG ¹ | KORNWESTHEIMER STR. 103-107 | 70439 | STUTTGART | DE | DE326812378 | 15607 | **?** | Sika ATM DE — Dinas KNR unklar |
| **18894** | 695 | SIKA AUTOMOTIVE DEUTSCHLAND GMBH | REICHSBAHNSTRASSE 99 | 22525 | HAMBURG | DE | DE812164982 | 1077344 | **?** | Sika ATM DE — Dinas KNR unklar |
| **18748** | 417 | SIKA AUTOMOTIVE AG | KREUZLINGERSTRASSE 35 | 8590 | ROMANSHORN | SCHWEIZ | CHE116323165 | 18748 | **?** | Sika ATM CH — Dinas KNR unklar |
| **15607** | 3 | SIKA DEUTSCHLAND GMBH (CHEM. FABRIK) ² | KORNWESTHEIMER STR. 103-107 | 70439 | STUTTGART | DE | DE813561973 | 15607 | **?** | Sika — ältere Gesellschaftsform, gleiche Adresse wie 25607 |

**Anmerkungen:**
> ¹ erka_knr 25607: Namensvariant „SIKA DEUTSCHLAND CH & CO. KG" (2 von 5 Stichproben) vs. „SIKA DEUTSCHLAND CH AG & CO. KG" (3 von 5). Dominante Form: **CH AG & CO. KG**. Bitte korrekten Vollnamen mit Rechtsform bestätigen.  
> ² erka_knr 15607: Nur 3 Datensätze; VAT DE813561973 unterscheidet sich von 25607 (DE326812378) → separate Rechtsperson trotz gleicher Adresse.

---

## Bekannte Nicht-Sika-Entitäten (Projekt-Scope oder Partner)

| erka_knr | Datensätze | Empfänger | PLZ Stadt | Land | USt-ID | Fibu-Konto | Einordnung |
|---|---|---|---|---|---|---|---|
| **25052** | 177 | FISCHERWERKE GMBH & CO. KG | 72178 WALDACHTAL | DE | DE144252337 | 15051 | Projekt-Scope (Fischerwerke) |
| **97501** | 422 | NOERPEL SE | 89520 HEIDENHEIM | DE | DE147042215 | 71003 | NOERPEL intern / Verrechnung |
| **97505** | 379 | NOERPEL SE | 78052 VILLINGEN-SCHWENNINGEN | DE | DE147042215 | 71001 | NOERPEL intern / Verrechnung |
| **97502** | 170 | NOERPEL SE | 40721 HILDEN | DE | DE147042215 | 71005 | NOERPEL intern / Verrechnung |
| **97513** | 32 | LEBERT AG (Intern. Spedition) | TÄGERWILEN CH | CH | — | 706500 | Subunternehmer/Partner |
| **90123** | 359 | RABELINK LOGISTICS | 7031 GG WEHL | NL | NL853204883B01 | 90123 | Partner Carrier NL |
| **90107** | 311 | DGS TRANSPORTS | 94450 LIMEIL BRÉVANNES | FR | FR63328233176 | 90107 | Partner Carrier FR |
| **95322** | 195 | TRANSNATUR NORTE S.L. | POLÍGONO LANBARREN, ORKOIEN | ES | ESB20449393 | 95321 | Partner Carrier ES (Nord) — nur erka_correction |
| **95329** | 72 | TRANSNATUR S.A. | 28820 COSLADA | ES | ESA08604316 | 527435 | Partner Carrier ES |
| **95309** | 6 | TRANSNATUR S.A. (ZALII) | ZONA ACTIVIDADES LOGÍSTICAS II | ES | ESA08604316 | 527435 | Partner Carrier ES |
| **95347** | 3 | TRANSNATUR S.A. | PARQUE EMPRESARIAL | ES | ESA08604316 | 527435 | Partner Carrier ES |
| **12817** | 9 | WÜRTH LOGISTICS AG | 7000 CHUR | CH | — | 88888 | Partner/Kunde CH |
| **10255** | 14 | LOHNPACK GMBH | EBERHARDT (DE) | DE | — | 1046877 | Out-of-scope Kunde |
| **70146** | 2 | SILVA & LUIS LDA | 2460 ALENQUER | PT | PT502495448 | 1104169 | Partner PT |
| **13021** | 1 | MANFRED SCHÄGNER GMBH | DE | — | DE144019289 | 13021 | Out-of-scope |
| **14666** | 1 | STÄUBLI BAYREUTH GMBH | BAYREUTH | DE | — | 60957 | Out-of-scope |
| **70183** | 1 | WIRZ TRANSPORT AG | 78244 GOTTMADINGEN | DE | DE812955801 | 86002 | Carrier/Partner |
| **90135** | 1 | SIMARCO INTERNATIONAL LIMITED | ESSEX, GB | GB | GB688528180 | 90134 | Partner GB |
| **91220** | 1 | CLF LTD | RATH BUSINESS PARK, IE | IE | IE6387022A | 91220 | Partner IE |

---

## Offene Fragen für User-Freigabe

### 1. Sika SSC — KNR 511241 für Varianten-KNRs bestätigen?

Alle 6 SSC-Varianten (14466, 14464, 14465, 14468, 13890, 15550) zeigen identisch:  
**SIKA SUPPLY CENTER AG, Industriestr. 26, 6060 Sarnen, CH, Fibu-Konto 13890**

→ Mapping-Vorschlag: alle 6 → Dinas KNR **511241**

### 2. Sika ATM — welche Dinas KNR?

Bekannte Dinas KNRs aus Abrechnungsstrecken (ATM-Gruppe):
- **413276** — „Sika ATM DE" (89 Zeilen, alle betrag=0)
- **493163** — „Sika ATM DE 2nd" (Zeilen unbekannt)
- **527406** — „Sika ATM CH" (387 non-zero Zeilen in EUR, Ursprung DE→IT/ES/GB/PT)

Vorgeschlagene Zuordnung (zu bestätigen):

| erka_knr | Gesellschaft (auf PDF) | Vorschlag Dinas KNR | Begründung |
|---|---|---|---|
| 25607 | SIKA DEUTSCHLAND CH AG & CO. KG | **527406** ? | Größter Block, DE-Versender, INT-Empfänger |
| 18894 | SIKA AUTOMOTIVE DEUTSCHLAND GMBH | **413276** oder **493163** ? | DE, Hamburg |
| 18748 | SIKA AUTOMOTIVE AG | **413276** oder **493163** ? | CH Romanshorn |

### 3. Rechtsform 25607 — Vollname bestätigen?

PDF zeigt: „SIKA DEUTSCHLAND CH AG & CO. KG" (dominante Variante, 4/5 Stichproben)  
Bitte korrekten Vollnamen mit Rechtsform angeben (z.B. GmbH & Co. KG? oder tatsächlich CH AG & Co. KG?).

---

*Dieses Dokument wird nach User-Freigabe als Basis für `src/tms/dinas/knr_mapping.py` verwendet.*
