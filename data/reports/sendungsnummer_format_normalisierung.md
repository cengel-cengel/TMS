# Etappe 8a — Sendungsnummer Format-Normalisierung

**Erstellt:** 2026-04-19  
**Scope:** Dinas.sendungsnummer ↔ AX.Auftragsnummer Matching-Strategie  
**Status:** Analyse abgeschlossen — Empfehlung: **indirekter Join über TB**

---

## 1. Längen-Verteilungen

### Dinas (5.533 Rows, `dinas_pdfs.parquet`)

| Länge | Anzahl | Anteil | Beispiel |
|-------|--------|--------|---------|
| 8 | 5.533 | **100 %** | `32847970`, `21109633` |
| andere | 0 | 0 % | — |

Ranges: `21xxxxxx` (Import-Routen Cerano→Stuttgart) · `32xxxxxx` (Export-Routen STR→IE/GB/IT/PT/…)

### AX / Sika.xlsx (3.590 Rows)

| Länge | Anzahl | Anteil | Beispiel |
|-------|--------|--------|---------|
| 16 | 3.589 | 99,97 % | `7092010000551006` |
| 10 | 1 | 0,03 % | `1804959006` (Ausreißer) |

Struktur der 16-stelligen AX-Nummern: `7092` + `01` + `0000xxxxxx` (festes Präfix `7092010`, Suffix = nullaufgefüllte interne Sequenz, Werte ~500–500.000).

### Tagesbericht / TB (250.950 Rows)

| Länge | Anzahl | Anteil | Beispiel |
|-------|--------|--------|---------|
| 8 | 118.052 | 47 % | `10156296`, `21125266`, `32870611` |
| 16 | 132.588 | 53 % | `7092010000551006` (AX-Format) |

Die 16-stelligen TB-Auftragsnummern entsprechen exakt den AX-Auftragsnummern (2.709 Matches Sika↔TB bestätigt in Etappe 7a). Die 8-stelligen TB-Auftragsnummern sind in **zwei** Ranges:
- `101xxxxx` (Noerpel-interne Aufträge, kein Dinas-Bezug)
- `21xxxxxx` / `32xxxxxx` (Dinas-Sendungsnummern, s. u.)

---

## 2. Hypothesen-Test (direkt Dinas ↔ AX)

Getestete Normalisierungsstrategien auf 20 Dinas-Stichproben vs. alle AX-Auftragsnummern:

| Hypothese | Methode | Matches | Ergebnis |
|-----------|---------|---------|----------|
| a) Links-Padding | `32847970` → `0000000032847970` (16-stellig) | 0 | **Fail** |
| b) Rechts-Padding | `32847970` → `3284797000000000` (16-stellig) | 0 | **Fail** |
| c) Teilstring AX-Suffix | `32847970` im AX-Suffix `xxxxxx` extrahieren | 0 | **Fail** |
| d) Substring | Dinas-Nr. als Substring in AX-Nr. | 0 | **Fail** |

**Ursache:** AX-Auftragsnummern und Dinas-Sendungsnummern stammen aus **vollständig getrennten Nummernräumen**. Die AX-internen Sequenznummern (`~500–500.000`) überlappen sich nicht mit dem Dinas-Bereich (`21.000.000–32.999.999`).

**Fazit: Es gibt keine direkte Format-Verknüpfung Dinas ↔ AX auf Sendungsebene.**

---

## 3. Gewinnende Hypothese: Indirekter Join über Tagesbericht

### Befund

`TB.Auftragsnummer` enthält **beide** Nummernräume:

```
TB.Auftragsnummer (8-stellig, ~21xxx/32xxx) = Dinas.sendungsnummer
TB.Auftragsnummer (16-stellig, 7092010...) = AX.Auftragsnummer
```

### Match-Quote (50-Stichprobe / In-Range-Population)

| Population | Dinas unique SNR | TB-Match (8-dig. Auftr.) | Coverage |
|------------|-----------------|--------------------------|----------|
| leistung_date ∈ [2025-04-01, 2026-03-31] | 3.603 | 3.595 | **99,8 %** |
| leistung_date < 2025-04-01 | ~1.885 | ~8 | ~0 % (TB-Cutoff) |
| leistung_date > 2026-03-31 | ~45 | 0 | 0 % (TB-Cutoff) |
| **Gesamt** | **5.533** | **~3.603** | **65 %** |

Die 35 % Gesamtlücke sind **ausschließlich Datumsbedingt**: Dinas-Parquet enthält Sendungen ab Oktober 2024, TB beginnt erst am 2025-04-01.

**Verifizierung:** `TB.Kundenreferenz == TB.Auftragsnummer` für alle 223 Dinas-Match-Rows (100 % Konsistenz).

### Sekundärer Bridge-Key (Rechnungsebene)

`TB.Rechnungsnummer` (führende Null entfernt) = `Dinas.rechnung_nr` für **30.076 TB-Rows**. Damit ist auch ein Join auf Rechnungsebene (Cluster-Level) möglich.

---

## 4. Join-Graph (vollständig)

```
Dinas.sendungsnummer ──(=)──→ TB.Auftragsnummer (8-digit)  ←─ Noerpel-interne Sendung
                                         │
                                    TB als Drehscheibe
                                         │
AX.Auftragsnummer ──────(=)──→ TB.Auftragsnummer (16-digit) ←─ AX/ERP-Sendung
```

Kein direkter Dinas ↔ AX Join auf Sendungsebene möglich.
Der Join läuft **immer über TB** als Mittler.

### Sekundärer Cluster-Level Join

```
Dinas.rechnung_nr ──(= TB.Rechnungsnummer strip '0')──→ TB-Rows
```

---

## 5. Empfehlung für Etappe 8

### Primärer Join (Sendungsebene)

```python
# Normalisierung: keine — direkte Integer-Gleichheit
dinas_snr = dinas_df['sendungsnummer'].astype(str)     # "32847970"
tb_auftr   = tb_df['Auftragsnummer'].astype(str)       # "32847970" (8-digit rows)

merged = dinas_df.merge(
    tb_df[tb_df['Auftragsnummer'].astype(str).str.len() == 8],
    left_on='sendungsnummer',
    right_on='Auftragsnummer',
    how='left',
    suffixes=('_dinas', '_tb'),
)
```

**Erwartete Coverage:** 99,8 % für Sendungen mit leistung_date ∈ TB-Fenster [2025-04-01, 2026-03-31].  
Sendungen außerhalb des Fensters (~35 % des Parquets) erhalten `NaN` in TB-Feldern — kein Fehler, sondern erwartet.

### Optionaler Cluster-Level Join

```python
# TB.Rechnungsnummer → Dinas rechnung_nr (Invoice-Level-Anreicherung)
tb_df['rechnung_nr_norm'] = tb_df['Rechnungsnummer'].astype(str).str.lstrip('0')
merged_cluster = dinas_cluster_df.merge(
    tb_df.groupby('rechnung_nr_norm').agg(...),
    left_on='cluster_id',    # = rechnung_nr
    right_on='rechnung_nr_norm',
    how='left',
)
```

### Warum kein Dinas ↔ AX Direkt-Join

Dinas-Sendungen und AX-Sendungen sind **unterschiedliche Transportketten**:
- Dinas = Subunternehmer-Perspektive (Dinas Spedition berechnet an ERKA / Sika)
- AX = Noerpel-interne Abrechnung (Noerpel berechnet an Sika-Konten)

Eine Sendung kann in **beiden** Systemen vorkommen (Import-Route Cerano→STR: Dinas AND AX), aber der Matching-Key ist das TB als gemeinsame operative Instanz, nicht die Sendungsnummer selbst.

---

## 6. Zusammenfassung

| Frage | Antwort |
|-------|---------|
| Direkte Format-Normalisierung Dinas ↔ AX? | **Nein** — keine gemeinsame Basis |
| Gewinnende Hypothese | **Indirekter Join: Dinas.SNR = TB.Auftragsnummer (8-dig.)** |
| Coverage im TB-Fenster | **99,8 %** (3.595 / 3.603 unique SNR) |
| Gesamtcoverage | **65 %** (Restlücke = Datumsbedingt, kein Datenfehler) |
| Sekundärer Bridge (Cluster-Level) | **TB.Rechnungsnummer (strip 0) = Dinas.rechnung_nr** |
| Empfehlung Etappe 8 | Merge auf `Dinas.sendungsnummer = TB.Auftragsnummer` (8-digit subset) |
