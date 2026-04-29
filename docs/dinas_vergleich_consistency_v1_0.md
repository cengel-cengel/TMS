# Dinas-Vergleich Konsistenz-Check — v1.0

**Stand:** 2026-04-29 | **Zweck:** Filter-Konsistenz zwischen Audit M-Klassen und
Dinas-Vergleich-Clustern dokumentieren. Zwei Korrekturen umgesetzt.

---

## §1 Übersicht: Vergleich Audit M2 vs. Vergleich Cluster-Anzahl

### Filter-Definition Vergleich
Cluster wird gezeigt wenn: mind. eine AX-Zeile mit `Σ Erloese < Soll * 0.95` (fp < −5 %)  
Soll = DLV-Basispreis aus jeweiligem Calculator.

### Audit M2-Definition
M2 = fp < −5 % **nach Anwendung aller Audit-Exclusions** (t_zero, split_position, §8,
pre_dlv_2026, Gate-6 rn_level_adjustment, rn_valid).

### Tabelle vor und nach Fixes

| Kunde | KNR | Audit M2 | Cluster (vor Fix) | Cluster (nach Fix) | Konsistent? |
|-------|-----|---------|-------------------|--------------------|-------------|
| GEZE | 406035 | 132 | 30 | 30 (unverändert) | Ja |
| EBM-Papst | 410844 | 1 | 1 | 1 (unverändert) | Ja |
| Fischerwerke | 409480 | 107 | 61 | 61 (unverändert) | Ja |
| HERMA | 423650 | 384 | 40 | 40 (unverändert) | Ja |
| **CHT** | **486073** | **0** | **20** | **12** (Fix 1) | Ja¹ |
| Bitzer | 406345 | 206 | 80 | 80 (unverändert) | Ja |
| **Groz-Beckert** | **490527+** | **0** | **1** | **0** (Fix 2) | Ja ✓ |
| HELU-KABEL | 408244 | 102 | 16 | 16 (unverändert) | Ja |
| Hornschuch | 490085 | 7 | 6 | 6 (unverändert) | Ja |
| Sika DE | 491063 | 293 | 67 | 67 (unverändert) | Ja |
| Sika SSC | 511241 | 0 | 0 | 0 (unverändert) | Ja ✓ |

¹ Restliche 12 CHT-Cluster = Audit-Residual (pre_dlv_2026 / rn_valid / Gate-6), kein Billing-Fehler.

---

## §2 Fix 1 — CHT §8/Split-Positions Filter

### Ursache der ursprünglichen Diskrepanz (Audit M2=0, Vergleich 20 Cluster)

Der Audit (`build_9c2b_cht_es_calculator_test.py`) schließt drei Zeilentypen aus M2 aus:

1. **§8 KNOWN_S8** — dokumentierte anomale Abrechnungsfälle:
   ```python
   KNOWN_S8 = {
       ('924029', '46890'),  # 3832 kg fp=-36%, 12334 kg fp=-13% (Gewichts-Anomalie)
       ('924029', '08310'),
       ('924040', '46890'),  # 7 Pos. (1344/6762/9076/1190/15166 kg)
       ('924145', '46890'),  # 4 Split-Pos. (0.20–11.70 kg) + 2 Begleit-Pos.
   }
   ```
2. **Split-Positionen** — Fragmente von Mehrfach-PLZ-Sendungen (ton < 2 kg)
3. **pre_dlv_2026** — Leistungsdatum < 2026-01-01 (2025-DLV unbekannt)
4. **Ungültige RN** — `Rechnungsnummer` nicht numerisch > 5 (z.B. RN='0')
5. **Gate-6 rn_level_adjustment** — systemischer RN-weiter Faktor

### Umgesetzte Korrekturen in `build_vergleich_cht.py`

- **KNOWN_S8-Filter**: Pre-Filter auf `post` vor `build_and_save` — 8 der 20 Cluster entfernt
- **Split-Filter**: `ton < 2.0 kg` — split-Positionen ausgeschlossen

### Ergebnis

| Filtertyp | Cluster entfernt |
|-----------|-----------------|
| KNOWN_S8 (§8 Anomalien) | 8 |
| Split-Positionen (ton < 2 kg) | 0 (vollständig durch KNOWN_S8 abgedeckt) |
| **Total entfernt** | **8** |
| **Verbleibend** | **12** |

### Verbleibende 12 Cluster — Erklärung

Alle 12 Residual-Cluster entsprechen Zeilen, die im Audit aus methodischen Gründen
nicht M2 sind — aber KEINEN Billing-Fehler darstellen:

| RN | Land | Audit-Ausschluss-Grund | Cluster-Anzahl |
|----|------|------------------------|----------------|
| 923818, 923911 | BE | pre_dlv_2026 (alle Zeilen < 2026-01-01) | 2 |
| 923740, 923779 | ES | pre_dlv_2026 (alle Zeilen < 2026-01-01) | 5 |
| 923847, 923957, 923981, 924020 | IT | pre_dlv_2026 (alle Zeilen < 2026-01-01) | 4 |
| RN='0' (mult.) | BE/ES/IT | rn_valid-Filter (RN nicht numerisch > 5) | enthalten in obigen |
| 924132 | BE | Gate-6 rn_level_adjustment (in_dlv_2026) | Teil von BE|bis 200kg |
| 924075 | ES | Gate-6 rn_level_adjustment (in_dlv_2026) | Teil von ES-Clustern |

**Fazit:** Die 12 verbleibenden Cluster sind **nicht reparierbar ohne pre_dlv_2026-Filter
und Gate-6-Logik** im Vergleich. Sie stellen keine echten Billing-Fehler dar.
Der Vergleich zeigt diese als Residual-Information; Carlos entscheidet ob weitere Filterung nötig.

---

## §3 Fix 2 — Groz-Beckert origin_plz Pass-Through

### Ursache der Diskrepanz (Audit M2=0, Vergleich 1 Cluster)

Der `GrozBeckertCalculator` ist **origin-sensitiv** (LTL-FTL Streckenrate):

| Parameter | Audit (`build_groz_beckert_step23_v196.py`) | Vergleich (vor Fix) |
|-----------|---------------------------------------------|---------------------|
| PLZ | 4409-516 | 4409-516 |
| Ton | 270 kg | 270 kg |
| LDM | 1.0 | 1.0 |
| **origin_plz** | **58640** (aus `Versender PLZ`-Spalte) | **None → 72458 (Default)** |
| Basispreis | **244.71** (= Erlöse Fracht → M1) | **325.29** (→ fp = −24.2 %) |

Der Vergleich übergibt `origin_plz=None` → Calculator fällt auf Default 72458 (Albstadt) zurück.
Mit korrektem Versender-PLZ 58640 ist basispreis = ef → M1.

### Umgesetzte Korrektur

1. `build_vergleich_helpers.py` `ax_row_generic`: extrahiert `vers_plz` aus `"Versender PLZ"`-Spalte
   und übergibt als 6. Argument an `soll_fn(land, plz, ton, ldm, stp, vers_plz)`
2. `build_vergleich_helpers.py` `dinas_row_generic`: übergibt `vers_plz=None`
3. Alle `soll_fn`-Signaturen: `vers_plz=None` als optionaler 6. Parameter ergänzt
4. `build_vergleich_groz.py` `soll_fn`: leitet `vers_plz` als `origin_plz` an Calculator weiter

### Ergebnis

**Groz-Beckert: 1 Cluster → 0 Cluster** ✓  
Echter Berechnungsfehler durch fehlenden origin_plz korrigiert.

---

## §4 Unveränderte Kunden — Kurzbestätigung

Für die 9 anderen Kunden bleiben Cluster-Zahlen unverändert. Die Vergleich-Filter
(AX < Soll × 0.95) und Audit-M2-Schwelle (fp < −5 %) sind konzeptionell identisch.
Abweichungen zwischen absoluter Cluster-Anzahl und M2-Zeilenanzahl sind methodisch
erwartet (Cluster ≠ Zeilen; Vergleich zeigt Top-5 pro Cluster).

| Kunde | M2 | Cluster | Verhältnis |
|-------|----|---------|------------|
| GEZE | 132 | 30 | n/a (Dinas-Vergleich vs. Unit-Test) |
| Fischerwerke | 107 | 61 | Cluster-Familien-Matching |
| HERMA | 384 | 40 | Cluster-Familien-Matching |
| Bitzer | 206 | 80 | Gewichtsband-Cluster |
| Sika DE | 293 | 67 | Stellplatz-Cluster |
| HELU-KABEL | 102 | 16 | Gewichtsband-Cluster |

---

## §5 Geänderte Dateien

| Datei | Änderung |
|-------|---------|
| `src/build_vergleich_helpers.py` | `ax_row_generic`: `vers_plz` extrahiert + an soll_fn übergeben; `dinas_row_generic`: `vers_plz=None` übergeben |
| `src/build_vergleich_cht.py` | KNOWN_S8-Filter + split-Filter (ton < 2 kg) auf `post`; soll_fn-Signatur |
| `src/build_vergleich_groz.py` | soll_fn-Signatur; `origin_plz=vers_plz` im Calculator-Aufruf |
| `src/build_vergleich_{ebm,fischerwerke,herma,bitzer,helu,hornschuch,sika_de,sika_ssc}.py` | soll_fn-Signatur: `vers_plz=None` ergänzt |
| `output/erka_lieferung/CHT_Vergleich.xlsx` | 20 → 12 Cluster (KNOWN_S8 + split entfernt) |
| `output/erka_lieferung/Groz_Beckert_Vergleich.xlsx` | 1 → 0 Cluster (origin_plz-Bug behoben) |

---

## §6 Offene Punkte (Entscheidung Carlos)

1. **CHT 12 Residual-Cluster**: Sollen pre_dlv_2026-Filter + Gate-6 + rn_valid im
   Vergleich ergänzt werden, um vollständige M2-Konsistenz herzustellen?
   → Aufwand: ~1 Stunde; würde CHT von 12 auf voraussichtlich 0-2 Cluster reduzieren.

2. **Soll-Konsistenz andere Kunden**: Cluster-Anzahl ≠ M2-Zeilenanzahl ist strukturell
   bedingt (Cluster = Land|Band-Gruppierung, M2 = Zeilenklasse). Keine Korrekturen nötig.

---

*Erstellt: 2026-04-29 | Fixes implementiert + getestet*
*Keine retroaktiven Korrekturen an anderen Vergleich-Dateien (9 Kunden unverändert)*
