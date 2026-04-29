# Dinas-Vergleich Konsistenz-Check — v1.1

**Stand:** 2026-04-29 | **Zweck:** Filter-Konsistenz zwischen Audit M-Klassen und
Dinas-Vergleich-Clustern dokumentieren. Drei Korrekturen umgesetzt.

---

## §1 Übersicht: Vergleich Audit M2 vs. Vergleich Cluster-Anzahl

### Filter-Definition Vergleich
Cluster wird gezeigt wenn: mind. eine AX-Zeile mit `Σ Erloese < Soll * 0.95` (fp < −5 %)  
Soll = DLV-Basispreis aus jeweiligem Calculator.

### Audit M2-Definition
M2 = fp < −5 % **nach Anwendung aller Audit-Exclusions** (t_zero, split_position, §8,
pre_dlv_2026, Gate-6 rn_level_adjustment, rn_valid).

### Konsistenz-Tabelle Final (nach allen Fixes)

| Kunde | KNR | Audit M2 | Cluster (initial) | Cluster (final) | Konsistent? |
|-------|-----|---------|-------------------|-----------------|-------------|
| GEZE | 406035 | 132 | 30 | 30 (unverändert) | Ja |
| EBM-Papst | 410844 | 1 | 1 | 1 (unverändert) | Ja |
| Fischerwerke | 409480 | 107 | 61 | 61 (unverändert) | Ja |
| HERMA | 423650 | 384 | 40 | 40 (unverändert) | Ja |
| **CHT** | **486073** | **0** | **20** | **0** (Fix 1+3) | **Ja ✓** |
| Bitzer | 406345 | 206 | 80 | 80 (unverändert) | Ja |
| **Groz-Beckert** | **490527+** | **0** | **1** | **0** (Fix 2) | **Ja ✓** |
| HELU-KABEL | 408244 | 102 | 16 | 16 (unverändert) | Ja |
| Hornschuch | 490085 | 7 | 6 | 6 (unverändert) | Ja |
| Sika DE | 491063 | 293 | 67 | 67 (unverändert) | Ja |
| Sika SSC | 511241 | 0 | 0 | 0 (unverändert) | Ja ✓ |

**Ergebnis: 11 von 11 Kunden konsistent mit Audit M-Klassen.**

---

## §2 Fix 1 — CHT §8/Split-Positions Filter

### Ursache der ursprünglichen Diskrepanz (Audit M2=0, Vergleich 20 Cluster)

Der Audit schließt mehrere Zeilentypen aus der M-Klassen-Berechnung aus. Der Vergleich
hatte ursprünglich keinen dieser Filter.

### Umgesetzte Korrekturen (Fix 1 in `build_vergleich_cht.py`)

**Filter KNOWN_S8**: (RN, PLZ)-Paare als §8-Anomalie-Ausnahmen klassifiziert  
(Quelle: `build_9c2b_cht_es_calculator_test.py` KNOWN_S8):
```python
_KNOWN_S8 = {("924029","46890"), ("924029","08310"),
             ("924040","46890"), ("924145","46890")}
```

**Filter Split-Positionen**: `ton < 2 kg` (Fragmente von Mehrfach-PLZ-Sendungen)

Ergebnis Fix 1: 20 → 12 Cluster

---

## §3 Fix 2 — Groz-Beckert origin_plz Pass-Through

### Ursache der Diskrepanz (Audit M2=0, Vergleich 1 Cluster)

Der `GrozBeckertCalculator` ist **origin-sensitiv** (LTL-FTL Streckenrate):

| Parameter | Audit | Vergleich (vor Fix) |
|-----------|-------|---------------------|
| **origin_plz** | **58640** (aus `Versender PLZ`-Spalte) | **None → 72458 (Default)** |
| Basispreis | **244.71** (= ef → M1) | **325.29** (fp = −24.2 %) |

### Umgesetzte Korrektur

- `build_vergleich_helpers.py`: `ax_row_generic` übergibt `vers_plz` als 6. Argument an alle `soll_fn`
- `build_vergleich_groz.py`: leitet `vers_plz` als `origin_plz` an Calculator weiter
- Alle übrigen `soll_fn`-Signaturen: `vers_plz=None` als optionaler Parameter ergänzt

**Groz-Beckert: 1 → 0 Cluster ✓**

---

## §4 Fix 3 — CHT pre_dlv_2026 + rn_valid + Gate-6

### Ursache der 12 Residual-Cluster (nach Fix 1)

Alle 12 verbliebenen CHT-Cluster kamen aus Zeilen, die der Audit aus methodischen
Gründen aus M2 ausschließt:

| RN | Land | Audit-Ausschluss-Grund |
|----|------|------------------------|
| 923818, 923911 | BE | pre_dlv_2026 (alle Zeilen Leistungsdatum < 2026-01-01) |
| 923740, 923779 | ES | pre_dlv_2026 |
| 923847, 923957, 923981, 924020 | IT | pre_dlv_2026 |
| RN='0' (mehrere) | BE/ES/IT | rn_valid: RN nicht numerisch > 5 |
| 924132 | BE | Gate-6 rn_level_adjustment (systemischer RN-Faktor) |
| 924075 | ES | Gate-6 rn_level_adjustment |

### Umgesetzte Korrekturen (Fix 3 in `build_vergleich_cht.py`)

```python
_GATE6_RN = {"924132", "924075"}
_DLV_2026_CUTOFF = pd.Timestamp("2026-01-01")

# pre_dlv_2026: nur 2026-DLV verfügbar, 2025-Tarif fehlt
post["_dat"] = pd.to_datetime(post["Leistungsdatum"], errors="coerce")
post = post[post["_dat"].isna() | (post["_dat"] >= _DLV_2026_CUTOFF)].copy()

# rn_valid: RN muss numerisch > 5 sein
def _rn_valid(rn): return float(str(rn).replace(",",".")) > 5
post = post[post["_rn"].apply(_rn_valid)].copy()

# Gate-6: systemischer RN-Faktor, kein Billing-Fehler
post = post[~post["_rn"].isin(_GATE6_RN)].copy()
```

**CHT: 12 → 0 Cluster ✓**

---

## §5 CHT Vollständige Filter-Liste (final)

Alle aktiven Filter in `build_vergleich_cht.py` (Reihenfolge der Anwendung):

| # | Filter | Basis | Entfernt |
|---|--------|-------|---------|
| 1 | KNOWN_S8 (§8 Anomalien) | (RN, PLZ)-Paare | 8 Cluster |
| 2 | Split-Positionen | ton < 2 kg | 0 zusätzlich |
| 3 | pre_dlv_2026 | Leistungsdatum < 2026-01-01 | 10 Cluster |
| 4 | rn_valid | RN nicht numerisch > 5 | in obigen enthalten |
| 5 | Gate-6 rn_level_adjustment | RN ∈ {924132, 924075} | 2 Cluster |
| **∑** | | | **20 → 0** |

---

## §6 Unveränderte Kunden — Kurzbestätigung

Für die 9 anderen Kunden bleiben Cluster-Zahlen unverändert. Die Vergleich-Filter
(AX < Soll × 0.95) und Audit-M2-Schwelle (fp < −5 %) sind konzeptionell identisch.
Abweichungen zwischen absoluter Cluster-Anzahl und M2-Zeilenanzahl sind methodisch
erwartet (Cluster = Land|Band-Gruppierung ≠ M2-Zeilenanzahl).

| Kunde | M2 | Cluster | Anmerkung |
|-------|----|---------|-----------|
| GEZE | 132 | 30 | Dinas-Vergleich (kein Audit-BI-Vergleich) |
| Fischerwerke | 107 | 61 | Cluster-Familien-Matching |
| HERMA | 384 | 40 | Cluster-Familien-Matching |
| Bitzer | 206 | 80 | Gewichtsband-Cluster |
| Sika DE | 293 | 67 | Stellplatz-Cluster |
| HELU-KABEL | 102 | 16 | Gewichtsband-Cluster |
| Hornschuch | 7 | 6 | Gewichtsband-Cluster |
| EBM-Papst | 1 | 1 | Stellplatz-Cluster |

---

## §7 Geänderte Dateien (alle Fixes)

| Datei | Änderung |
|-------|---------|
| `src/build_vergleich_helpers.py` | `ax_row_generic`: `vers_plz` extrahiert + weitergegeben; `dinas_row_generic`: `vers_plz=None` |
| `src/build_vergleich_cht.py` | 5 Filter: KNOWN_S8 + split + pre_dlv_2026 + rn_valid + Gate-6 |
| `src/build_vergleich_groz.py` | `origin_plz=vers_plz` im Calculator-Aufruf |
| `src/build_vergleich_{ebm,fischerwerke,herma,bitzer,helu,hornschuch,sika_de,sika_ssc}.py` | `soll_fn(…, vers_plz=None)` |
| `output/erka_lieferung/CHT_Vergleich.xlsx` | **20 → 0 Cluster** |
| `output/erka_lieferung/Groz_Beckert_Vergleich.xlsx` | **1 → 0 Cluster** |

---

*Erstellt: 2026-04-29 (v1.0) | Aktualisiert: 2026-04-29 (v1.1, Fix 3)*  
*11 von 11 Kunden konsistent mit Final-Audit-Report v2.0. Keine offenen Punkte.*
