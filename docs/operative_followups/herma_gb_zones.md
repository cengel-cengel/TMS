# HERMA — GB Area-Code Zonen-Klärung

**Erstellt:** 2026-04-27  
**Kontext:** v1.9.4 Pre-Flight, GATE D (Coverage-Test)  
**Status:** OFFEN — Klärung mit HERMA/Noerpel erforderlich

---

## Befund

Beim vollständigen Coverage-Test (826 AX-Pool-Zeilen, Ladedatum 2025/2026,
Land=GB) wurden 93 Sendungen gefunden, deren UK Area-Code nicht in der
HERMA 2026 Haftmaterial DLV-Workbook-Lookup-Map enthalten ist.

Der Calculator (`HermaCalculator._parse_gb()`) liest die Area-Code-Gruppen
direkt aus dem GB-Sheet des DLV-Workbooks. Die 10 fehlenden Codes sind
daher eine **DLV-Lücke**, kein Calculator-Fehler.

---

## Fehlende Area-Codes

| Area-Code | Ort            | Rows | Erlöse Fracht (EUR) |
|-----------|----------------|-----:|--------------------:|
| WF        | Wakefield      |   45 |           28.859,00 |
| ME        | Medway         |   22 |           23.011,00 |
| LS        | Leeds          |    9 |            4.462,00 |
| NE        | Newcastle      |    4 |            1.467,00 |
| WN        | Wigan          |    3 |            1.425,00 |
| BL        | Bolton         |    3 |            1.178,00 |
| SA        | Swansea        |    3 |              868,00 |
| PL        | Plymouth       |    2 |              407,00 |
| YO        | York           |    1 |              140,00 |
| CH        | Chester        |    1 |              100,00 |
| **Σ**     |                | **93** |        **61.917,00** |

---

## Frage an HERMA/Noerpel

Welcher DLV-Zone (z. B. Zone 1/2/3 aus dem GB-Sheet) sind die oben
genannten Area-Codes laut aktueller DLV-Vereinbarung zuzuordnen?

Alternativ: Sollen diese Postleitzahlgebiete einem bestehenden
Area-Code-Cluster im GB-Sheet hinzugefügt werden?

---

## Auswirkung bis zur Klärung

- Die 93 Sendungen (61.917 EUR Erlöse Fracht) werden im v1.9.4-Cluster-Report
  als **DLV-Lücke (Kategorie: GB-Zone-NaN)** geführt.
- Sie werden **nicht** als Audit-Befund (M-Klasse) gewertet.
- Nach Klärung: entweder DLV-Workbook um die fehlenden Codes ergänzen oder
  Calculator-Map manuell patchen (`_parse_gb` liest live aus dem Workbook).

---

## Blockiert Step 2?

**Nein.** DLV-Lücke ist methodisch sauber zu führen. Step 2 kann starten,
solange die 93 Rows als NaN-Zone-Anhang ausgewiesen werden.
