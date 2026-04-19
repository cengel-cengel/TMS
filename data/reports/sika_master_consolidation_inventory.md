# Sika-Familie — AX Master-Konsolidierungsstruktur Inventur

**Quelle:** `data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Sika.xlsx`  
**Gesamt-Rows:** 3.590  
**Erstellt:** 2026-04-19  
**Scope:** Reine Inventur — kein Code, kein Commit.

---

## 1. Alle KNRs in der Datei

| KNR | Name (Kontobezeichnung) | Ort | Rows | Masters | Master Betrag>0 | Master Betrag=0 | Gesamt-Betrag (EUR) |
|-----|-------------------------|-----|------|---------|-----------------|-----------------|---------------------|
| **491063** | Sika Deutschland GmbH / Sika Deutschland CH AG & Co KG | Stuttgart | 519 | 486 | 481 | 5 | 445.116,36 |
| **511241** | SIKA SUPPLY CENTER AG | Sarnen (CH) | 499 | 366 | 341 | 25 | 825.548,94 |
| **527406** | Sika Automotive AG | — | 464 | 402 | 386 | 15 | 262.726,78 |
| **413276** | 000534470 - Sika Automotive Deutschland GmbH | — | 89 | 69 | **0** | **69** | **0,00** |
| **ARA1802357** | Sika Automotive Deutschland GmbH | Hamburg | 514 | 413 | 413 | 0 | 107.113,99 |
| **ARA_Sika_DE+CH** *(neu)* | Sika Deutschland CH AG & Co KG + SIKA SUPPLY CENTER AG | Stuttgart | 1.504 | 1.144 | 807 | 337 | 1.089.761,69 |
| **529453** *(neu)* | Sika S.A.U. | Alcobendas (ES) | 1 | 1 | 1 | 0 | 234,96 |

**Nicht vorhanden:** Kein eigener KNR für "Sika Automotive AG (CH)" als eigenständiges Konto – KNR 527406 deckt diese Entität ab (Von Name = "Sika Automotive AG c/o LSU Schäberl").

### Beobachtung: Shadow/Billing-Paare

| Shadow-KNR (immer Betrag=0) | Billing-KNR (tatsächlicher Betrag) | Gemeinsame Auftragsnummern |
|-----------------------------|------------------------------------|---------------------------|
| **413276** | **ARA1802357** | 67 von 69 (97%) |
| **527406** (15 Null-Rows) | ARA1802357 (2), ARA_Sika_DE+CH (2), 529453 (1) | partiell |
| **ARA_Sika_DE+CH** (337 Null-Masters) | ARA_Sika_DE+CH (andere Master mit selber Auftrnr) | 330 von 337 |

> **KNR 413276 ist ein reines Spiegelkonto:** Alle 69 Master-Rows haben Betrag=0,00 EUR.
> Die faktische Abrechnung derselben Sendungen erfolgt unter KNR ARA1802357 (Sika Automotive
> Deutschland GmbH, Hamburg). 2 von 69 Rows haben keinen ARA1802357-Gegenpart
> (Auftrnr 7092010004666003 / 7092010004701001, je 2025-10-07, Melfi/IT + Kragujevac/RS).

---

## 2. Master/Sub-Struktur — Gesamtstatistik

| | Anzahl |
|--|--------|
| **Master-Rows** (Hauptabrechnungsstrecke = Ja) | **2.881** |
| **Sub-Rows** (Hauptabrechnungsstrecke = Nein) | **709** (davon 1 mit Zusammengefasst in = NaN) |
| Masters mit ≥1 Sub | **517** |
| Masters ohne Sub (Singleton) | **2.364** |

### Sub-Anzahl Verteilung

| Sub-Anzahl | Anzahl Master-Cluster |
|------------|----------------------|
| 1 Sub (Singleton-Konsolidat) | **380** |
| 2 Subs | **102** |
| 3 Subs | **19** |
| 4 Subs | **13** |
| 5 Subs | **3** |
| **Gesamt mit Subs** | **517** |

### Verteilung nach KNR

| KNR | Master mit Subs | Standalone Masters | Sub-Rows |
|-----|-----------------|--------------------|----------|
| ARA_Sika_DE+CH | 266 | 878 | 360 |
| 511241 | 113 | 253 | 133 |
| ARA1802357 | 57 | 356 | 101 |
| 527406 | 51 | 351 | 62 |
| 491063 | 15 | 471 | 32 |
| 413276 | 15 | 54 | 20 |

---

## 3. Multi-KNR-Test — NEGATIV

**Ergebnis: Kein einziger Master-Cluster enthält Subs mit unterschiedlichen KNRs.**

Alle 517 Master-Cluster sind strikte Mono-KNR-Cluster: Master-KNR === Sub-KNR für 100% der Rows.

> Das bedeutet: In der AX-Struktur gibt es **keine KNR-übergreifende Konsolidierung innerhalb
> eines einzelnen Master-Clusters**. Die "Zusammenführung" verschiedener Sika-Gesellschaften
> erfolgt auf Konto-Ebene (ARA_Sika_DE+CH = DE+CH kombiniert), nicht auf
> Sendungs-/Cluster-Ebene.

### Cross-KNR-Verbindung auf Auftragsnummer-Ebene

Obwohl kein Cluster KNR-übergreifend ist, erscheinen dieselben **Auftragsnummern** unter
mehreren KNRs als getrennte Master-Rows:

- 67 Auftragsnummern tauchen sowohl bei KNR **413276** (Betrag=0) als auch bei **ARA1802357**
  (Betrag>0) auf — exakt dieselbe Sendung, zweimal verbucht.
- 94 Sub-Auftragsnummern erscheinen in mehr als einem Master-Cluster (davon die meisten
  innerhalb desselben KNR als "Storno/Duplikat"-Muster).

**Exemplarische Cross-KNR-Doppelbuchung (413276 ↔ ARA1802357):**

| Auftrnr | KNR | Abrechnungsstrecke | Betrag | Route |
|---------|-----|--------------------|--------|-------|
| 7092010011405008 | **413276** | 77089 | **0,00 EUR** | Stuttgart → Settimo Torinese (IT) |
| 7092010011405008 | **ARA1802357** | 114896 | **148,25 EUR** | Stuttgart → Settimo Torinese (IT) |

*Identische Subs (Auftrnr 7092010011398003/400003/401000/407002), identisches Leistungsdatum.*

---

## 4. Rechnungsempfänger-Prüfung

**Hypothese bestätigt:** Der Rechnungsempfänger (Feld `Name`) ist innerhalb eines Clusters
**immer identisch**. Master und alle Subs tragen denselben Name-Wert.

- **0 Abweichungen** über alle 708 validen Sub-Rows.
- Die `Name`-Werte unterscheiden sich zwischen KNRs (z.B. "Sika Automotive Deutschland GmbH"
  bei ARA1802357 vs. "000534470 - Sika Automotive Deutschland GmbH" bei 413276 — offenbar
  unterschiedliche Formatierung desselben Kunden).

---

## 5. Leistungsdatum-Check

**"Pro Tag" bestätigt als exakt 0 Tage Streuung:**

- **Spread unter Subs desselben Masters:** 0 Tage in 100% der Multi-Sub-Cluster (137/137).
- **Master-Datum vs. Sub-Datum:** 0 Tage Differenz bei 100% aller 708 Sub-Rows.

Alle Sendungen eines Clusters haben exakt dasselbe Leistungsdatum. Keine ±1-Tag-Toleranz
erforderlich — AX erzwingt ein einheitliches Datum pro Abrechnungscluster.

---

## 6. Origin/Destination-PLZ-Check

*(Hinweis: Explizite PLZ-Felder fehlen in der Datei. Analyse basiert auf `Von Ort` / `Nach Ort`.)*

### Destination (Nach Ort)
- **136 von 137** Multi-Sub-Cluster (99,3%): Alle Subs haben identischen `Nach Ort`.
- **1 Ausnahme** (Master 286727, ARA_Sika_DE+CH): 2 Subs mit verschiedenen Dublin-Adressen
  ("Dublin (Ashtown)" vs. "Dublin (Ballymun)") — selbe Stadt, unterschiedliche Werke.

### Origin (Von Ort)
- **74 von 137** Multi-Sub-Cluster (54%): Alle Subs haben identischen `Von Ort`.
- **63 von 137** Cluster (46%): Verschiedene `Von Ort` unter Subs — meistens Varianten
  derselben Stadt ("Stuttgart" vs. "Stuttgart (Weilimdorf)"), aber auch echte
  unterschiedliche Abholorte (z.B. Schwieberdingen ≠ Stuttgart in Cluster 15808).

**Interpretation:** Die Konsolidierung erfolgt primär nach Route (Destination) und Datum,
toleriert aber verschiedene Abholpunkte aus demselben Großraum. Für Etappe 7/8:
Origin-PLZ als "gruppierende Variable" ungeeignet; Destination-PLZ + Datum + KNR
ist der verlässliche Cluster-Schlüssel.

---

## 7. Exemplarische Multi-Sub-Cluster (8 Beispiele mit vollständigen Sub-Details)

### Cluster 1 — ARA1802357, 5 Subs (Stuttgart → Minworth/GB)

| Feld | Wert |
|------|------|
| Master-ID | 178023 |
| KNR | ARA1802357 |
| Billing Entity | Sika Automotive Deutschland GmbH |
| Leistungsdatum | 2025-12-04 |
| Route | Stuttgart (Weilimdorf) → Minworth (GB) |
| Master-Betrag | **481,95 EUR** |
| Gewicht | 240,4 kg |
| Stellplätze | 6 |
| LDM | 2,4 |
| Master-Auftrnr | 7092010021922007 |

| Sub | Auftragsnummer | Von Ort | Nach Ort | Betrag |
|-----|----------------|---------|----------|--------|
| 178024 | 7092010021925008 | Stuttgart (Weilimdorf) | Minworth | 0,00 |
| 178025 | 7092010021926005 | Stuttgart (Weilimdorf) | Minworth | 0,00 |
| 178026 | 7092010021927002 | Stuttgart (Weilimdorf) | Minworth | 0,00 |
| 178027 | 7092010021929006 | Stuttgart (Weilimdorf) | Minworth | 0,00 |
| 178028 | 7092010021933003 | Stuttgart (Weilimdorf) | Minworth | 0,00 |

---

### Cluster 2 — 491063, 5 Subs (Stuttgart → Newport/GB)

| Feld | Wert |
|------|------|
| Master-ID | 379995 |
| KNR | 491063 |
| Billing Entity | Sika Deutschland CH AG & Co KG |
| Leistungsdatum | 2026-02-27 |
| Route | Stuttgart → Newport/MHI Vestas (GB) |
| Master-Betrag | **2.541,22 EUR** |
| Gewicht | 1.165,76 kg |
| Stellplätze | 7 |
| LDM | 2,8 |

| Sub | Auftragsnummer | Von Ort | Betrag |
|-----|----------------|---------|--------|
| 379996 | 7092010040171004 | Stuttgart | 0,00 |
| 379997 | 7092010040168004 | Stuttgart | 0,00 |
| 379998 | 7092010040172001 | Stuttgart | 0,00 |
| 379999 | 7092010040165003 | Stuttgart | 0,00 |
| 380000 | 7092010040173008 | Stuttgart | 0,00 |

---

### Cluster 3 — 413276 (SHADOW), 4 Subs (Stuttgart → Settimo Torinese/IT)

| Feld | Wert |
|------|------|
| Master-ID | 77089 |
| KNR | **413276 (SHADOW — Betrag=0)** |
| Billing Entity | 000534470 - Sika Automotive Deutschland GmbH |
| Leistungsdatum | 2025-10-27 |
| Route | Stuttgart (Weilimdorf) → Settimo Torinese/PILKINGTON ITALIA (IT) |
| Master-Betrag | **0,00 EUR** |
| Gewicht | 56,0 kg |
| Stellplätze | 6 |

| Sub | Auftragsnummer | Betrag |
|-----|----------------|--------|
| 77418 | 7092010011398003 | 0,00 |
| 77419 | 7092010011400003 | 0,00 |
| 77420 | 7092010011401000 | 0,00 |
| 77421 | 7092010011407002 | 0,00 |

*Identische Sendungen erscheinen unter Master 114896 (ARA1802357, 148,25 EUR) — s. Cluster 4.*

---

### Cluster 4 — ARA1802357 (BILLING), 4 Subs (= Cluster 3 gespiegelt)

| Feld | Wert |
|------|------|
| Master-ID | 114896 |
| KNR | **ARA1802357 (BILLING — Betrag>0)** |
| Billing Entity | Sika Automotive Deutschland GmbH |
| Leistungsdatum | 2025-10-27 |
| Route | Stuttgart (Weilimdorf) → Settimo Torinese/PILKINGTON ITALIA (IT) |
| Master-Betrag | **148,25 EUR** |
| Master-Auftrnr | **7092010011405008** ← selbe wie Cluster 3 |

| Sub | Auftragsnummer | Betrag |
|-----|----------------|--------|
| 114899 | 7092010011398003 | 0,00 |
| 114900 | 7092010011400003 | 0,00 |
| 114901 | 7092010011401000 | 0,00 |
| 114902 | 7092010011407002 | 0,00 |

---

### Cluster 5 — 511241, 2 Subs (Cerano/IT → Stuttgart, Import)

| Feld | Wert |
|------|------|
| Master-ID | 4484 |
| KNR | 511241 |
| Billing Entity | SIKA SUPPLY CENTER AG |
| Leistungsdatum | 2025-09-29 |
| Route | Cerano (IT) → Stuttgart (Weilimdorf) — Import |
| Master-Betrag | **4.977,43 EUR** |
| Gewicht | 19.040 kg |
| Stellplätze | 99 |

| Sub | Auftragsnummer | Von Ort | Betrag |
|-----|----------------|---------|--------|
| 4485 | 7092010000674002 | Cerano | 0,00 |
| 4486 | 7092010000706000 | Cerano | 0,00 |

---

### Cluster 6 — 527406, 2 Subs (Stuttgart → Atessa/IT)

| Feld | Wert |
|------|------|
| Master-ID | 27923 |
| KNR | 527406 |
| Billing Entity | Sika Automotive AG |
| Leistungsdatum | 2025-10-10 |
| Route | Stuttgart → FCA Atessa Carrozzerie (IT) |
| Master-Betrag | **758,80 EUR** |
| Gewicht | 3.353 kg |
| Stellplätze | 8 |
| LDM | 3,2 |

| Sub | Auftragsnummer | Von Ort | Betrag |
|-----|----------------|---------|--------|
| 27924 | 7092010006237003 | Stuttgart | 0,00 |
| 27928 | 7092010006371004 | Stuttgart | 0,00 |

---

### Cluster 7 — 491063, 4 Subs (Stuttgart → Newport/GB)

| Feld | Wert |
|------|------|
| Master-ID | 187988 |
| KNR | 491063 |
| Billing Entity | Sika Deutschland CH AG & Co KG |
| Leistungsdatum | 2025-12-09 |
| Route | Stuttgart → Newport/MHI Vestas (GB) |
| Master-Betrag | **2.354,23 EUR** |
| Gewicht | 352 kg |
| Stellplätze | 6 |

| Sub | Auftragsnummer | Von Ort | Betrag |
|-----|----------------|---------|--------|
| 187989 | 7092010023333009 | Stuttgart | 0,00 |
| 187990 | 7092010023332002 | Stuttgart | 0,00 |
| 187991 | 7092010023331005 | Stuttgart | 0,00 |
| 187994 | 7092010023852005 | Stuttgart | 0,00 |

---

### Cluster 8 — ARA_Sika_DE+CH (Betrag=0 Zero-Master), 4 Subs (Stuttgart → Sassuolo/IT)

| Feld | Wert |
|------|------|
| Master-ID | 202259 |
| KNR | ARA_Sika_DE+CH |
| Billing Entity | Sika Deutschland CH AG & Co KG + SIKA SUPPLY CENTER AG |
| Leistungsdatum | 2025-12-15 |
| Route | Stuttgart → Sika Italia S.p.a. / Sassuolo (IT) |
| Master-Betrag | **0,00** (internes Duplikat — Billing unter anderer Master-ID) |
| Gewicht | 592,67 kg |
| Stellplätze | 19 |
| LDM | 7,6 |

| Sub | Auftragsnummer | Von Ort | Betrag |
|-----|----------------|---------|--------|
| 202267 | 7092010024964004 | Stuttgart | 0,00 |
| 202274 | 7092010024955002 | Stuttgart (Weilimdorf) | 0,00 |
| 202275 | 7092010024978001 | Stuttgart (Weilimdorf) | 0,00 |
| 202276 | 7092010025204000 | Stuttgart (Weilimdorf) | 0,00 |

---

## 8. Zusammenfassung für Etappe 7/8 Spec

### Was in AX bestätigt ist

| Frage | Antwort |
|-------|---------|
| Cross-KNR-Konsolidierung (ein Cluster, mehrere KNRs)? | **NEIN** — nie |
| Rechnungsempfänger immer einheitlich pro Cluster? | **JA** — 100%, keine Ausnahme |
| Leistungsdatum exakt gleich pro Cluster? | **JA** — 0 Tage Streuung, kein ±1-Tag |
| Destination immer gleich pro Cluster? | **JA** — 99,3% (1 Ausnahme: 2 Dublin-Werke) |
| Origin immer gleich pro Cluster? | **NEIN** — nur 54%, echte Multi-Origin-Abholungen möglich |
| Sub-Betrag immer 0? | **JA** — alle 708 Sub-Rows haben Betrag=0,00 |
| Betrag ausschließlich auf Master? | **JA** — 100% |

### KNR-Klassifikation für Calculator-Mapping

| KNR | Typ | Für Calculator relevant? |
|-----|-----|--------------------------|
| **491063** | Billing, Export DE→EU | Ja — SikaDeCalculator (oder SSC?) |
| **511241** | Billing, Import EU→DE | Ja — eigener Calculator |
| **527406** | Billing, ATM Export | Ja — SikaATMChCalculator |
| **413276** | **Shadow (Betrag immer 0)** | **Nein** — Spiegel von ARA1802357 |
| **ARA1802357** | Billing, ATM Hamburg | Ja — SikaATMDeCalculator |
| **ARA_Sika_DE+CH** | Billing, DE+CH kombiniert | Ja — unklar ob eigener Calculator |
| **529453** | Billing, ES-Entität (1 Row) | Grenzfall |

### Offene Punkte für Spec-Entscheidung

1. **KNR 413276 als Shadow**: Beim Migration-Audit doppeltes Billing-Risiko, wenn 413276 UND ARA1802357 für dieselbe Sendung ausgewertet werden. → Empfehlung: 413276 aus Soll-Erlös-Berechnung ausschließen.

2. **ARA_Sika_DE+CH 337 Zero-Masters**: 241 davon sind Standalone ohne Subs — Ursache unklar (Stornos? Duplikate?). Für Abweichungsanalyse nur Betrag>0-Masters heranziehen.

3. **ARA_Sika_DE+CH als kombiniertes Konto**: Deckt sowohl Sika Deutschland GmbH (491063-ähnlich) als auch SIKA SUPPLY CENTER AG (511241-ähnlich) ab — in AX als ein Konto. Calculator-Routing benötigt KNR-Unterscheidung, nicht nur Sendungsroute.

4. **KNR 511241 (SIKA SUPPLY CENTER AG, Sarnen)**: Importrouten IT/ES/RO→DE. Bisher kein dedizierter Calculator — falls relevant für Etappe 7/8, eigener Calculator nötig.

5. **Origin-PLZ**: Nicht als Cluster-Schlüssel verwendbar (46% der Multi-Sub-Cluster haben variable Origins). Für Calculator-Matching: Destination-Land + PLZ-Präfix + KNR ist zuverlässiger.
