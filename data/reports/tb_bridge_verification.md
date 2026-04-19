# Etappe 8b — TB Cross-Reference Verifikation

**Erstellt:** 2026-04-19  
**Scope:** Dinas ↔ AX Verbindung über Tagesbericht — Struktur und Hypothesen-Test  
**Status:** Analyse abgeschlossen

---

## 1. Datenbasis und Zeitfenster

| Dataset | Leistungsdatum Range | Rows |
|---------|---------------------|------|
| Dinas (dinas_pdfs.parquet) | 2024-10-04 – 2025-09-26 (Extrakt) | 5.533 |
| TB (Tagesbericht) | 2025-04-01 – 2026-03-31 | 250.950 |
| Sika.xlsx (AX) | **2025-09-29 – 2026-04-17** | 3.590 |

**Kritischer Befund:** Dinas und AX haben keine zeitliche Überlappung auf Sendungsebene. Die 10 Sample-Sendungen (April–Juli 2025) sind alle **PRE-Migration** — zu diesem Zeitpunkt existieren noch keine AX-Gegenbuchungen in Sika.xlsx. Dinas und AX repräsentieren aufeinanderfolgende Abrechnungsperioden, nicht parallele Systeme für dieselben Sendungen.

---

## 2. Die 10 Stichproben

| # | sendungsnummer | rechnung_nr | leistung_date | ERKA | Land | fracht_eur |
|---|---------------|-------------|---------------|------|------|------------|
| 1 | 32872026 | 3759173 | 2025-04-02 | 10255 | GB | 420.00 |
| 2 | 32878236 | 3760258 | 2025-04-14 | 10255 | GB | 190.00 |
| 3 | 32900005 | 3767515 | 2025-05-26 | 12817 | ES | 859.94 |
| 4 | 32903920 | 3768276 | 2025-06-03 | 12817 | ES | 859.94 |
| 5 | 32930567 | 3774258 | 2025-07-23 | 13021 | GR | 715.64 |
| 6 | 32874847 | 3763113 | 2025-04-08 | 13890 | ES | 447.45 |
| 7 | 32874848 | 3763113 | 2025-04-08 | 13890 | ES | 865.10 |
| 8 | 21138626 | 2383657 | 2025-06-23 | 14464 | IT | 1154.60 |
| 9 | 32874363 | 3763114 | 2025-04-07 | 14464 | IT | 1126.65 |
| 10 | 32883777 | 3763115 | 2025-04-25 | 14465 | ES | 350.03 |

---

## 3. Per-Sendung Cross-Reference Befunde

### Primärfelder (für alle 10 bestätigt)

| Feld | Ergebnis | Bedeutung |
|------|----------|-----------|
| `TB.Auftragsnummer` == `Dinas.sendungsnummer` | **10/10 Match** | Primärer Join-Key funktioniert |
| `TB.Rechnungsnummer` (strip '0') == `Dinas.rechnung_nr` | **10/10 Match** | Sekundärer Cluster-Level-Key |
| `TB.Mastersendung` | **NaN bei allen 10** | Kein AX-Verweis in Dinas-Rows |
| `TB.Eingangsbordero` | **NaN bei allen 10** | Kein eingehender Bordero-Link |

### Felder mit gemischtem Inhalt

| SNR | TB.Kundenreferenz | in Dinas.bordero_nr? | in Dinas.sendungsnr? |
|-----|-------------------|---------------------|---------------------|
| 32872026 | `LS260581,260595 // 1` | Nein | Nein |
| 32878236 | `11944 260738` | Nein | Nein |
| 32900005 | `32900005` | Nein | **Ja** (Selbstreferenz) |
| 32903920 | `6100177084 / LADEREF` | Nein | Nein |
| 32930567 | `58036` | Ja | Nein |
| 32874847 | `75108961` | **Ja** | Nein |
| 32874848 | `75108960` | **Ja** | Nein |
| 21138626 | `75111418` | **Ja** | Nein |
| 32874363 | `75108929` | **Ja** | Nein |
| 32883777 | `75109559` | **Ja** | Nein |

**TB.Kundenreferenz enthält in 86,6% der 3.626 Dinas-TB-Rows die `Dinas.bordero_nr`** (3.141/3.626). Dies ist ein Nebenprodukt der Noerpel-internen Bordero-Logik, kein AX-Verweis.

### TB.Ausgangsbordero

Alle 10 Dinas-Rows haben eine `Ausgangsbordero` im Format `2025_XXXXXXXX` (z.B. `2025_24200650`). Dinas.bordero_nr hat Format `XXXXXXXX` (z.B. `75108961`). **Kein gemeinsames Format, kein Match.**

Across alle AX-TB-Rows: **0 shared Ausgangsbordero** mit Dinas-TB-Rows für rechnung_nr=3763113.

---

## 4. Rechnungsnummer-Gruppen im TB

### Beispiel rechnung_nr=3763113 (31 Sendungen, ERKA 13890, ES)

| Eigenschaft | Wert |
|-------------|------|
| TB-Rows mit RN=3763113 | **31** |
| davon 8-stellig (Dinas) | **31** (100 %) |
| davon 16-stellig (AX) | **0** |
| Dinas-Sendungen in dieser Rechnung | 31 |
| Übereinstimmung Dinas-SNR ↔ TB-Auftr. | **31/31 (100 %)** |

**Befund: TB.Rechnungsnummer-Gruppen für Dinas-Rechnungen enthalten ausschließlich 8-stellige (Dinas) Auftragsnummern.** Keine AX-Zeilen (16-stellig) sind in denselben Gruppen vorhanden.

### Systemweite Aufteilung

| Rechnungsnummer-Quelle | 8-digit TB-Rows | 16-digit TB-Rows |
|------------------------|----------------|-----------------|
| Dinas rechnung_nr | **7.092** | 0 |
| `0` (Dummy / leer) | — | 22.978 (*) |

(*) Die 22.978 vermeintlichen 16-digit Matches (Rechnungsnummer=`0` → stripped=`''`) sind Artefakte: `0` stripped to `''` matcht auf leere Einträge in Dinas. Kein echter inhaltlicher Match.

---

## 5. Hypothesen-Auswertung

### Hypothese A: 1 Dinas-PDF = 1 AX-Cluster

**Ergebnis: NICHT TESTBAR über TB.**

Ursache: Die 10 Stichproben stammen aus April–Juli 2025 (PRE-Migration). Sika.xlsx startet erst am 2025-09-29 (POST-Migration). Es gibt keine zeitliche Überlappung auf Sendungsebene — die Systeme decken aufeinanderfolgende Perioden ab, nicht parallele. Ein 1:1-Mapping auf Sendungsebene ist konzeptionell nicht vorgesehen.

Für Cluster-Familien-Bildung (Etappe 8) bedeutet das: **Dinas und AX müssen über Route×Kunden×Periode verglichen werden, nicht über gemeinsame IDs.**

### Hypothese B: 1:1 Sendungs-Link über TB

**Ergebnis: BESTÄTIGT NEGATIV.**

- `TB.Mastersendung` = NaN für alle 10 Dinas-Rows (kein Verweis auf AX-Auftragsnummer)
- Kein einziges TB-Feld in Dinas-Rows referenziert eine 16-stellige AX-Auftragsnummer
- `TB.Kundenreferenz` enthält Dinas-Bordero-Nummern (86,6%), nicht AX-Auftragsnummern
- `TB.Ausgangsbordero` hat anderes Format als Dinas.bordero_nr — kein Overlap

**Es gibt keinen direkten 1:1 Dinas-Sendung → AX-Sendung Join über TB.**

### Hypothese C: Verbindung nur über Cluster-Ebene (Rechnungsnummer)

**Ergebnis: BESTÄTIGT** — aber mit Einschränkung.

Die Verbindung über `Dinas.rechnung_nr = TB.Rechnungsnummer (strip 0)` funktioniert als **Dinas-interner** Cluster-Key (gruppiert alle Sendungen einer Dinas-Rechnung im TB). Diese Gruppe enthält jedoch **keine AX-Rows** — der Rechnungsnummer-Key überbrückt nicht zu AX.

Die einzige Verbindung Dinas ↔ AX ist daher **konzeptuell** (Route, Kunde, Periode), nicht über gemeinsame IDs im TB.

---

## 6. Empfehlung für Etappe 8 Join-Pfad

### Pfad 1: Dinas-Sendung → TB (Sendungsebene)

```
Dinas.sendungsnummer = TB.Auftragsnummer (8-stellig)
Coverage: 99.8 % (für leistung_date ∈ [2025-04-01, 2026-03-31])
```

Damit erhält jede Dinas-Sendung volle TB-Felder (Erlöse, Kosten, PLZ, Relation).

### Pfad 2: Dinas-Cluster → TB-Gruppe (Rechnungsebene)

```
Dinas.rechnung_nr = TB.Rechnungsnummer.lstrip('0')
Gruppe: alle TB-Rows mit dieser Rechnungsnummer (ausschließlich 8-digit)
```

Validierung: Anzahl TB-Rows == Dinas n_sendungen (rechnung_nr=3763113: 31/31 ✓).

### Pfad 3: Dinas ↔ AX (Cluster-Familien)

**Kein ID-basierter Join möglich.** Matching über zusammengesetzte Kriterien:

```python
# Route-Cluster-Key (approximativer Join)
route_key = (empf_land, empf_plz[:2], monat)
kunden_key = erka_knr_to_ax_knr_mapping[erka_kundennr]

# Dinas-Cluster: aggregiert auf (kunden_key, route_key)
# AX-Cluster:   aggregiert auf (master_knr, route_key)
# Match:        kunden_key == master_knr AND route_key == route_key
```

**Präziser KPI-Vergleich nur per-Unit (EUR/100kg, EUR/Stp, EUR/LDM)**, nicht absolut — wegen unterschiedlicher Sendungszusammenfassung zwischen Dinas (viele Einzel-Sendungen pro Rechnung) und AX (Zusammengefasst-in Cluster).

---

## 7. Zusammenfassung Cross-Reference-Felder

| TB-Feld | Enthält | Verwendbar als Bridge? |
|---------|---------|----------------------|
| `Auftragsnummer` (8-dig) | Dinas.sendungsnummer | **JA — Primärer Join** |
| `Auftragsnummer` (16-dig) | AX.Auftragsnummer | **JA — für AX-Join** |
| `Rechnungsnummer` | Dinas.rechnung_nr (0-padded) | **JA — Cluster-Level** |
| `Kundenreferenz` | Dinas.bordero_nr (86,6 %) oder Kundeneigene Ref | Nein (nicht AX-Link) |
| `Mastersendung` | NaN bei Dinas-Rows | Nein |
| `Eingangsbordero` | NaN bei Dinas-Rows | Nein |
| `Ausgangsbordero` | Noerpel-interne Bordero-Kennung | Nein (anderes Format) |

### Vollständiger Join-Graph (final)

```
Dinas.sendungsnummer ─────────────────────(=)─── TB.Auftragsnummer (8-digit)
                                                          │
                                              TB.Rechnungsnummer ─── Dinas.rechnung_nr
                                                          │
                             ┌──────────────────────────── ✗ keine gemeinsame ID ─────────────────┐
                             │                                                                      │
AX.Auftragsnummer (16-dig) ──(=)─── TB.Auftragsnummer (16-digit)          Dinas-Cluster (rechnung_nr)
         │                                    │                                        │
  AX-Cluster (ZGI)               AX.Rechnungsnummer (Noerpel intern)      Route+Kunden+Periode
                                                                                       │
                                                                      Cluster-Familie (approximativer Match)
```

**Kein deterministischer Dinas ↔ AX Join auf Sendungs- oder Rechnungsebene.**  
**Die Cluster-Familien-Bildung in Etappe 8 muss über Route+Kunden+Periode erfolgen (nicht ID-basiert).**
