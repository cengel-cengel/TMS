# v1.9 Pipeline-Integrations-Flow

**Stand:** 2026-04-24 | **Methodik:** v1.9.2 (`docs/AUDIT_METHODOLOGY.md`)
**Scope:** Ablauf für GEZE-Integration; generalisierbar auf alle Kunden.

---

## §1 Übersicht

```
AX-Rohdaten
    │
    ▼
[1] classify_ax_rows()
    ├── is_sub      → filtert raus
    ├── is_master   → reconstruct_ax_master() + Dinas-Matching
    └── is_standalone → direkt in Vergleichs-Set
    │
    ▼
[2] Sub-Rows trennen, Master-Gruppen bilden
    │
    ▼
[3] reconstruct_ax_master() pro Master-Gruppe
    (Master führt physisch; Erlöse aus Subs)
    │
    ▼
[4] Vergleichs-Set zusammenführen
    (rekonstruierte Master + Standalones)
    │
    ▼
[5] ~unbeurteilbar-Filter (Stage 2, §2e Rule D)
    (Tonnage ≤ 0 AND LDM ≤ 0)
    │
    ▼
[6] Dinas-Matching
    (aggregate_dinas_per_invoice() + Routing-Key-Join)
```

---

## §2 Schritt-für-Schritt mit Datentypen

### Schritt 1 — AX-Daten laden und klassifizieren

```python
import pandas as pd
from tms.billing.aggregation import classify_ax_rows

# AX-Rohdaten
bi = pd.read_pickle('output/bi_top20_data.pkl')['df']
geze_raw = bi[bi['Kunden Nr BK'] == 406035].copy()

# Klassifikation (fügt is_sub, is_master, is_standalone hinzu)
geze = classify_ax_rows(geze_raw)
# geze hat Spalten: ..., has_ms, has_ua, is_sub, is_master, is_standalone
```

**Input:** roher AX-DataFrame (alle Zeilen, keine Filterung)
**Output:** DataFrame mit 5 Klassifikations-Spalten

**Wichtig:** `Unterauftrag` enthält komma-separierte Strings → `_nonempty()`
(string-check) korrekt; kein `float()`-Check verwenden.

---

### Schritt 2 — Drei Gruppen trennen

```python
masters     = geze[geze['is_master']].copy()     # 586 Zeilen (GEZE)
subs        = geze[geze['is_sub']].copy()         # 1.751 Zeilen (GEZE)
standalones = geze[geze['is_standalone']].copy()  # 8.610 Zeilen (GEZE)
```

**Sub-Zeilen werden nicht weiterverarbeitet** (kein Calculator, kein Matching).
Sie fließen nur als Input in `reconstruct_ax_master()` für ihre Master-Zeile.

---

### Schritt 3 — Master-Gruppen bilden

Der Bezug Sub→Master läuft über:
- Sub: `Mastersendung` = Master-`Auftragsnummer` (als Float gespeichert)
- Master: `Auftragsnummer` (als String oder Float)

```python
import numpy as np

def _match_float(val_a, val_b, tol=0.5) -> bool:
    try:
        return abs(float(val_a) - float(val_b)) < tol
    except (TypeError, ValueError):
        return False

# Subs nach Mastersendung-Wert indexieren
subs_indexed = {}
for _, sub in subs.iterrows():
    ms_val = sub['Mastersendung']
    try:
        key = round(float(ms_val))
        subs_indexed.setdefault(key, []).append(sub)
    except (TypeError, ValueError):
        pass

# Je Master: passende Subs finden
master_groups = []
for _, master in masters.iterrows():
    try:
        key = round(float(master['Auftragsnummer']))
    except (TypeError, ValueError):
        continue
    matched_subs = subs_indexed.get(key, [])
    sub_df = pd.DataFrame(matched_subs) if matched_subs else pd.DataFrame(columns=geze.columns)
    master_groups.append((master, sub_df))
```

**Input:** `masters` Series + `subs` DataFrame
**Output:** Liste von `(master_row: pd.Series, sub_rows: pd.DataFrame)` Paaren

**Randbedingung:** Mastersendung ist Float (z.B. `7092010001835006.0`).
Rundung auf Integer für stabiles Dictionary-Keying.

---

### Schritt 4 — reconstruct_ax_master() aufrufen

```python
from tms.billing.aggregation import reconstruct_ax_master

reconstructed_rows = []
for master, sub_df in master_groups:
    rec = reconstruct_ax_master(master, sub_df)
    # rec ist dict: {'Tonnage (eff.)': ..., 'Erlöse Fracht': ..., 'rechnungsnummern': [...], ...}
    
    # Master-Metadaten übernehmen (Land, PLZ, Datum, Auftragsnummer, ...)
    row = master.to_dict()
    row.update(rec)                          # rekonstruierte Werte überschreiben
    row['_source'] = 'reconstructed_master'
    row['_n_subs'] = len(sub_df)
    reconstructed_rows.append(row)

masters_reconstructed = pd.DataFrame(reconstructed_rows)
```

**Input:** `(master_row, sub_rows)` pro Gruppe
**Output:** DataFrame mit rekonstruierten Master-Zeilen
(physische Werte: Master-Führung; Erlöse: Sub-Summe)

---

### Schritt 5 — Vergleichs-Set zusammenführen

```python
standalones_copy = standalones.copy()
standalones_copy['_source'] = 'standalone'
standalones_copy['_n_subs'] = 0
standalones_copy['rechnungsnummern'] = standalones_copy['Rechnungsnummer'].apply(
    lambda v: [str(v)] if pd.notna(v) else []
)

comparison_set = pd.concat([masters_reconstructed, standalones_copy], ignore_index=True)
```

**Input:** rekonstruierte Master + Standalones
**Output:** `comparison_set` — alle Calculator-relevanten Zeilen

---

### Schritt 6 — Stage-2-Filter: ~unbeurteilbar (§2e Rule D)

```python
ton = pd.to_numeric(comparison_set['Tonnage (eff.)'], errors='coerce').fillna(0)
ldm = pd.to_numeric(comparison_set['Lademeter'],      errors='coerce').fillna(0)
is_unbeurteilbar = (ton <= 0) & (ldm <= 0)

df_vergleich = comparison_set[~is_unbeurteilbar].copy()
# Protokoll:
print(f"Unbeurteilbar gefiltert: {is_unbeurteilbar.sum()} Zeilen")
print(f"Vergleichs-Set: {len(df_vergleich)} Zeilen")
```

**Input:** `comparison_set`
**Output:** `df_vergleich` — nur beurteilbare Zeilen für Calculator

---

### Schritt 7 — Dinas-Matching

```python
from tms.billing.aggregation import aggregate_dinas_per_invoice
import pickle

with open('output/dinas_cache_406035.pkl', 'rb') as f:
    dinas_raw = pickle.load(f)

dinas_agg = aggregate_dinas_per_invoice(
    dinas_raw,
    rn_col='rechnung_nr',
    sender_plz_col='empf_land',   # GEZE-spezifisch, prüfen
    empf_plz_col='empf_plz',
    date_col='leistungsdatum',
    agg_cols=['fracht', 'diesel', 'maut_ssd', 'gesamtbetrag', 'stellplaetze', 'ldm'],
)
# dinas_agg: 759 Routing-Keys (GEZE), davon 23 Multi-Groups

# Matching: df_vergleich × dinas_agg über (Empfänger_PLZ, Leistungsdatum)
# → entspricht bestehender build_geze_report.py-Logik, mit v1.9-Scope
```

**Input:** `df_vergleich` + `dinas_agg`
**Output:** Matched DataFrame für Pass-Rate / §8-Kandidaten

---

## §3 Eingriffspunkte im bestehenden GEZE-Script

Datei: `src/build_9b3_geze_phase_rollout.py`

| Zeile (ca.) | Aktueller Code | v1.9-Änderung |
|-------------|---------------|---------------|
| 102 | `core['tonnage_ok'] = core['Tonnage (eff.)'] > 0` | Ersetzen durch `classify_ax_rows()` + `filter_comparison_set()` |
| 117 | Gate-1-Check basiert auf Tonnage=0 | Gate-1 bleibt; aber Scope-Berechnung ändert sich |
| 140 | `grp['tonnage_source'] = 'direct'` | Entfällt; Tonnage kommt von `reconstruct_ax_master()` |
| — | (kein Stage-2-Filter) | `~unbeurteilbar` nach Schritt 6 einfügen |

Datei: `src/build_geze_report.py`

| Zeile (ca.) | Aktueller Code | v1.9-Änderung |
|-------------|---------------|---------------|
| 161 | `pre = pre[pre['Dinas Fracht'].fillna(0) > 0]` | PRE-Seite unverändert (Dinas-Filter) |
| 184–197 | Tonnage-Berechnungen auf POST-Daten | Tonnage aus `reconstruct_ax_master()` verwenden |

---

## §4 Nicht-veränderte Teile

| Komponente | Grund |
|-----------|-------|
| DLV-Parsing (`lookup_geze()`) | Tarif-Logik unverändert |
| Muster-A/B-Erkennung | Formeln unverändert |
| CHF-Floater-Modell | Unverändert |
| 9b.1 Unit-Tests | Separat; kein Eingriff |
| Gate-1-Schwelle (20 %) | Schwelle unverändert; Scope-Berechnung passt sich an |

---

## §5 Datenfluss-Typen pro Schritt

| Schritt | Eingang | Ausgang |
|---------|---------|---------|
| 1 | `pd.DataFrame` (rohe AX) | `pd.DataFrame` (+ Klassifikations-Spalten) |
| 2 | Klassifizierter DataFrame | 3 × `pd.DataFrame` (masters, subs, standalones) |
| 3 | masters + subs | `list[tuple[pd.Series, pd.DataFrame]]` |
| 4 | Master-Gruppen-Liste | `pd.DataFrame` (rekonstruierte Master) |
| 5 | Rekonstruierte Master + Standalones | `pd.DataFrame` (comparison_set) |
| 6 | comparison_set | `pd.DataFrame` (df_vergleich, beurteilbar) |
| 7 | df_vergleich + dinas_agg | Matched DataFrame |

---

## §6 STOP-Kriterien mid-Integration

| Trigger | Nach Schritt | Konsequenz |
|---------|-------------|------------|
| Scope-Änderung > 5 kEUR nach Sub-Exclusion | 5 | STOP, Abstimmung |
| Mehr als 3 der 12 Muster-B-Kandidaten sind Sub-Rows | 2 | STOP, Findings-Review |
| `reconstruct_ax_master()` liefert für >5 % der Master NaN-Ergebnisse | 4 | Datenproblem untersuchen |
| Stage-2-Filter entfernt >200 Zeilen aus dem Vergleichs-Set | 6 | STOP, prüfen ob legitim |

---

*Erstellt: 2026-04-24 | Keine Code-Änderungen. Keine Ausführungen.*
*Grundlage: build_9b3_geze_phase_rollout.py, build_geze_report.py, aggregation.py*
