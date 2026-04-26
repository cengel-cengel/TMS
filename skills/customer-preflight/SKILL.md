---
name: customer-preflight
description: >
  Standardisiertes Pre-Flight-Protokoll vor Step 2 (Cluster-Bildung) für
  TMS Billing-Audit-Kunden. Führt 4 Diagnosen durch, identifiziert Filter-
  Lücken, DLV-Lücken, billing_axis und finale Scope-Entscheidungen.
  Reduziert typischen 4-Iterations-Konvergenz-Aufwand auf 1 Durchlauf.
when-to-use: >
  Vor jeder Step-2-Cluster-Bildung für einen neuen Kunden. Mindestvoraus-
  setzung: KNR bekannt, bi_top20_data.pkl geladen, DLV-Verzeichnis bekannt,
  Calculator-Commit bekannt.
---

# TMS Customer Pre-Flight Diagnostic

## Inhaltsverzeichnis

1. [Voraussetzungen](#1-voraussetzungen)
2. [DIAGNOSE 1 — Master-Sub-Empirik](#2-diagnose-1--master-sub-empirik)
3. [DIAGNOSE 2 — Tarifgruppen-Mapping + DLV-Sheet-Struktur](#3-diagnose-2--tarifgruppen-mapping--dlv-sheet-struktur)
4. [DIAGNOSE 3 — Coverage-Validation + Lane-Discovery](#4-diagnose-3--coverage-validation--lane-discovery)
5. [DIAGNOSE 4 — Scope-Entscheidungen + Final-Pool](#5-diagnose-4--scope-entscheidungen--final-pool)
6. [Output-Format-Templates](#6-output-format-templates)
7. [Decision-Heuristiken](#7-decision-heuristiken)
8. [Known Pitfalls](#8-known-pitfalls)

---

## 1 Voraussetzungen

Vor Beginn sicherstellen:

| Pflichtfeld | Quelle |
|---|---|
| `KNR` | Handover-Dokument |
| `billing_axis` | Handover-Dokument (IMMER empirisch bestätigen — kann falsch sein) |
| `calculator_commit` | git log / Handover |
| `dlv_dir` | Pfad zum DLV-Verzeichnis des Kunden |
| `bi_top20_data.pkl` | `output/bi_top20_data.pkl` |

**Warnung billing_axis:** Das Handover-Dokument kann falsch sein.
EBM-Präzedenzfall: Handover sagte `tonnage_eff`, empirische Analyse
zeigte `stp_eff` (DLV-Pricing ist stellplatz-basiert). Immer im
Calculator-Code verifizieren — `pricing_basis`-Attribut des Calculators.

---

## 2 DIAGNOSE 1 — Master-Sub-Empirik

**Zweck:** Verstehen wie AX Master/Sub-Zeilen für diesen Kunden
strukturiert sind, bevor reconstruct_ax_master() konfiguriert wird.

**Script:**

```python
import pandas as pd
import numpy as np

KNR = XXXXXXX  # ersetzen

bi = pd.read_pickle('output/bi_top20_data.pkl')['df']
cust_raw = bi[bi['Kunden Nr BK'] == KNR].copy()

def _nonempty(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return str(v).strip() not in ('', 'nan', 'None')

cust_raw['has_ms'] = cust_raw['Mastersendung'].apply(_nonempty)
cust_raw['has_ua'] = cust_raw['Unterauftrag'].apply(_nonempty)
cust_raw['is_sub']        = cust_raw['has_ms'] & ~cust_raw['has_ua']
cust_raw['is_master']     = ~cust_raw['has_ms'] & cust_raw['has_ua']
cust_raw['is_standalone'] = ~cust_raw['has_ms'] & ~cust_raw['has_ua']
cust_raw['is_sub_master'] = cust_raw['has_ms'] & cust_raw['has_ua']  # AX-Artefakt

n_total  = len(cust_raw)
n_master = cust_raw['is_master'].sum()
n_sub    = cust_raw['is_sub'].sum()
n_stand  = cust_raw['is_standalone'].sum()
n_subm   = cust_raw['is_sub_master'].sum()

print(f"Gesamt:          {n_total}")
print(f"is_master:       {n_master}")
print(f"is_sub:          {n_sub}")
print(f"is_standalone:   {n_stand}")
print(f"is_sub_master:   {n_subm}  (hat BEIDE Felder gesetzt)")

COLS = ['Auftragsnummer','Mastersendung','Unterauftrag',
        'Tonnage (eff.)','Lademeter','Stellplätze','Erlöse Fracht',
        'Empfänger Land','Empfänger PLZ']

if n_sub > 0:
    print(f"\nSub-Rows (n={n_sub}):")
    print(cust_raw[cust_raw['is_sub']][COLS].to_string(index=False))

if n_subm > 0:
    sm = cust_raw[cust_raw['is_sub_master']]
    print(f"\nSub-Master-Zeile(n) (n={n_subm}):")
    print(sm[COLS].to_string(index=False))
    sm_ms = pd.to_numeric(sm.iloc[0]['Mastersendung'], errors='coerce')
    sm_au = pd.to_numeric(sm.iloc[0]['Auftragsnummer'], errors='coerce')
    self_ref = not np.isnan(sm_ms) and abs(sm_ms - sm_au) < 1
    print(f"  self_referential: {self_ref}")
    print(f"  Sub-Summe Erlöse: {cust_raw[cust_raw['is_sub']]['Erlöse Fracht'].sum():.2f} EUR")
    if self_ref:
        print(f"  -> Behandlung: wie klassischer Master")
        print(f"     (phys. Master, Erlöse = Sub-Summe, RNs als Liste)")
        print(f"     Methodik-Praezedenz: EBM 7092010036894009")
    else:
        print(f"  -> ESKALATION: nicht-self-referential sub_master.")
        print(f"     Carlos befragen vor weiterer Verarbeitung.")

stand = cust_raw[cust_raw['is_standalone']].copy()
ton = pd.to_numeric(stand['Tonnage (eff.)'], errors='coerce').fillna(0)
ldm = pd.to_numeric(stand['Lademeter'],      errors='coerce').fillna(0)
stp = pd.to_numeric(stand['Stellplätze'],    errors='coerce').fillna(0)

print(f"\nStandalone Physische Felder (n={n_stand}):")
print(f"  Tonnage > 0:        {(ton>0).sum()} / {n_stand}  ({100*(ton>0).mean():.1f}%)")
print(f"  Lademeter > 0:      {(ldm>0).sum()} / {n_stand}  ({100*(ldm>0).mean():.1f}%)")
print(f"  Stellplaetze > 0:   {(stp>0).sum()} / {n_stand}  ({100*(stp>0).mean():.1f}%)")
print(f"  Nur LDM (kein Stp): {((stp==0)&(ldm>0)).sum()}")
print(f"  Nur Stp (kein LDM): {((stp>0)&(ldm==0)).sum()}")
print(f"  Weder Stp noch LDM: {((stp==0)&(ldm==0)).sum()}")

ton_pos = ton[ton > 0]
print(f"\nTonnage Statistik (Standalone):")
print(f"  min: {ton_pos.min():.1f}  median: {ton.median():.1f}  max: {ton.max():.1f}  =0: {(ton==0).sum()}")

has_both = (stp > 0) & (ldm > 0)
if has_both.sum() > 0:
    ratio = ldm[has_both] / stp[has_both]
    print(f"\nLDM/Stp-Ratio (n={has_both.sum()}, erwartet 0.400):")
    print(f"  median: {ratio.median():.3f}  min: {ratio.min():.3f}  max: {ratio.max():.3f}")

master_all = cust_raw[cust_raw['is_master'] | cust_raw['is_sub_master']]
ton_m = pd.to_numeric(master_all['Tonnage (eff.)'], errors='coerce').fillna(0)
pct_leer = 100*(ton_m==0).mean() if len(master_all) > 0 else float('nan')
print(f"\nSpektrum-Einordnung:")
print(f"  Master-Zeilen gesamt: {len(master_all)}")
print(f"  Phys. Feld leer:      {(ton_m==0).sum()} ({pct_leer:.0f}%)")
print(f"  GEZE:         ~0%  (Master fuehrt immer)")
print(f"  EBM:           0%  (identisch GEZE)")
print(f"  Fischerwerke: ~29% (LDM-Fallback dominiert)")

# ──── Interpretation Decision-Tree ────
if pct_leer < 5:
    print("\n→ GEZE/EBM-Muster: Master fuehrt immer.")
    print("  reconstruct_ax_master() = No-Op.")
    print("  billing_axis aus Calculator pricing_basis lesen.")
elif pct_leer > 20:
    print("\n→ Fischerwerke-Muster: LDM-Fallback dominant.")
    print("  reconstruct_ax_master() KRITISCH konfigurieren.")
    print("  billing_axis vermutlich lademeter (verifizieren).")
else:
    print(f"\n→ Mittel-Position ({pct_leer:.0f}%): genauer untersuchen.")
    print("  Vor D2: Master/Sub-Verteilung manuell sichten.")
```

---

## 3 DIAGNOSE 2 — Tarifgruppen-Mapping + DLV-Sheet-Struktur

**Zweck:** DLV-Tarif-Struktur des Kunden empirisch verstehen,
Sheet-Namen auto-detecten, billing_axis aus Calculator-Code
verifizieren, Pricing-Knicke fuer Band-Definition extrahieren.
Adressiert P1 (billing_axis falsch) und P2 (Sheet-Name abweichend).

**Voraussetzung:** DIAGNOSE 1 abgeschlossen.

**Script:**

```python
import pandas as pd
import numpy as np
from pathlib import Path
import importlib

KNR = XXXXXXX            # ersetzen
DLV_DIR = Path('data/dlv/<customer-folder>')   # ersetzen
CALC_MODULE = 'tms.tariff.calculators.<customer>'   # ersetzen
LANES_FROM_HANDOVER = ['IE', 'PL', 'EE', 'SK', 'HR']  # ersetzen / leer falls unbekannt

# ──── 1) Calculator pricing_basis lesen (P1-Pitfall) ────
calc_mod = importlib.import_module(CALC_MODULE)
calc_class = [c for c in dir(calc_mod) if 'Calculator' in c][0]
calc = getattr(calc_mod, calc_class)()
pb = getattr(calc, 'pricing_basis', '<MISSING>')
print(f"Calculator: {CALC_MODULE}.{calc_class}")
print(f"  pricing_basis: {pb}")
print(f"  -> billing_axis fuer Cluster-Key: {pb}")
if pb == '<MISSING>':
    print(f"  WARNUNG: Calculator hat kein pricing_basis-Attribut.")
    print(f"  -> Calculator-Code manuell pruefen, was als Lookup-Key dient.")

# ──── 2) DLV-Verzeichnis-Listing ────
print(f"\n=== DLV-Dateien ({DLV_DIR}) ===")
for p in sorted(DLV_DIR.rglob('*.xlsx')):
    rel = p.relative_to(DLV_DIR)
    print(f"  {rel}  ({p.stat().st_size//1024} KB)")

# ──── 3) Sheet-Namen pro DLV-Datei (P2-Pitfall) ────
print(f"\n=== Sheet-Namen pro DLV-Datei ===")
SHEET_KANDIDATEN = ['Tariffs_DE_EU', 'DE-EU', 'Tariffs', 'Tarif', 'DE_EU']
for p in sorted(DLV_DIR.rglob('*.xlsx')):
    if 'durch neue' in str(p).lower():
        continue
    try:
        sheets = pd.ExcelFile(p).sheet_names
        print(f"  {p.name}")
        print(f"    sheets: {sheets}")
        match = next((s for s in SHEET_KANDIDATEN if s in sheets), None)
        if match:
            print(f"    -> auto-detect: '{match}'")
        else:
            print(f"    WARNUNG: kein Standard-Sheet — manuell pruefen")
    except Exception as e:
        print(f"  {p.name}  FEHLER: {e}")

# ──── 4) Tarifgruppen-Bezeichner pro Lane ────
print(f"\n=== Tarifgruppen pro Lane (aktive DLV-Version) ===")
ACTIVE_DLV = sorted([p for p in DLV_DIR.rglob('*.xlsx')
                     if 'durch neue' not in str(p).lower()])[-1]
print(f"  Aktive Datei: {ACTIVE_DLV.name}")
try:
    df = pd.read_excel(ACTIVE_DLV, sheet_name=0)
    print(f"  Spalten (erste 10): {list(df.columns[:10])}")
    print(f"  Zeilen: {len(df)}")
except Exception as e:
    print(f"  FEHLER beim Lesen: {e}")

# ──── 5) Pricing-Knicke fuer Band-Definition ────
# Wenn pricing_basis = stp_eff: Stp 1..N abfragen, Delta/Stp berechnen
# Wenn pricing_basis = lademeter / tonnage: analog mit Werte-Range
print(f"\n=== Pricing-Knicke (fuer Band-Definition) ===")
print(f"  pricing_basis = {pb}")
print(f"  -> manuell ueber Calculator.calculate() abfragen,")
print(f"     Delta/Einheit-Kurve plotten, Knicke identifizieren.")
print(f"  Beispiel EBM (stp_eff):")
print(f"    1-5  Stueckgut:  ~190 EUR/Stp")
print(f"    6-16 LTL:        ~107 EUR/Stp  (Knick bei 6)")
print(f"    17-30 FTL:        ~75-85 EUR/Stp")
print(f"    31-33 Cap:        flat")

# ──── 6) Lane-Coverage Vorab-Check ────
print(f"\n=== Lane-Coverage Vorab-Check ===")
print(f"  Handover-Lanes: {LANES_FROM_HANDOVER}")
print(f"  -> vollstaendige Lane-Discovery erst in DIAGNOSE 3.")
print(f"     Hier nur: Plausibilitaet — listet DLV alle Handover-Lanes?")

# ──── 7) Interpretations-Decision-Tree ────
print(f"\n=== Interpretation ===")
if pb == '<MISSING>':
    print(f"-> ESKALATION: pricing_basis nicht ableitbar. Carlos befragen.")
elif pb in ('stp_eff', 'stellplaetze'):
    print(f"-> Stellplatz-basiert: Cluster-Key Gewichtsklasse = Stp-Band.")
    print(f"   Cap-Risiko pruefen (P7).")
elif pb in ('lademeter',):
    print(f"-> Lademeter-basiert: Cluster-Key = LDM-Band.")
elif pb in ('tonnage', 'tonnage_eff'):
    print(f"-> Tonnage-basiert: Cluster-Key = Tonnage-Band.")
else:
    print(f"-> Unbekannt ({pb}): Calculator-Code manuell sichten.")
```

---

## 4 DIAGNOSE 3 — Coverage-Validation + Lane-Discovery

*Placeholder — wird nach ersten 2 Kunden konkretisiert.*

**Zweck:** Vollständige empirische Lane-Verteilung erheben, DLV-Coverage
pro Lane messen, Cross-System-Filter anwenden, finale Scope-Entscheidung
vorbereiten.

Adressiert P4 (Cross-System-Schatten) und P5 (Lane-Discovery unvollständig).

---

## 5 DIAGNOSE 4 — Scope-Entscheidungen + Final-Pool

*Placeholder — wird nach ersten 2 Kunden konkretisiert.*

**Zweck:** Alle Filter-Entscheidungen aus D1–D3 zusammenführen, Final-Pool
quantifizieren (Sendungen, EUR-Scope), Cluster-Key-Spalten bestätigen.

---

## 6 Output-Format-Templates

*Placeholder — wird nach ersten 2 Kunden konkretisiert.*

Alle Diagnose-Outputs: Plain-Text-Code-Blöcke (kein JSON, kein HTML).
Format-Regel: ein Code-Block pro Diagnose-Abschnitt, keine verschachtelten
Markdown-Blöcke.

---

## 7 Decision-Heuristiken

*Placeholder — wird nach ersten 2 Kunden konkretisiert.*

Heuristiken aus D1-D3 werden hier konsolidiert (Spektrum-Einordnung,
billing_axis-Bestätigung, LDM-Fallback-Entscheidung, Cap-Handling).

---

## 8 Known Pitfalls

### P1 — billing_axis im Handover falsch (EBM, 2026-04)

**Situation:** Handover gab `billing_axis: tonnage_eff`. EBM-Calculator
nutzt `stellplaetze` / `lademeter` als Primäreingang. Tonnage wird für
DLV-Lookup nicht verwendet.

**Erkennung:** `pricing_basis`-Attribut des Calculators lesen.
Wenn `pricing_basis != 'tonnage'` → Handover-Wert falsch.

**Fix:** billing_axis auf Calculator-Basis korrigieren, in §2g-Tabelle
(AUDIT_METHODOLOGY.md) aktualisieren.

---

### P2 — DLV-Sheet-Name abweichend (EBM PT/ES, 2026-04)

**Situation:** `load_prefixes()` verwendete Standardname `Tariffs_DE_EU`.
EBM-Datei `20250819_PT_ES.xlsx` nutzt Sheet-Name `DE-EU`. Coverage 0/5.

**Erkennung:** Bei Coverage = 0% für eine Lane obwohl DLV-Datei existiert:
`pd.ExcelFile(path).sheet_names` ausgeben, Sheet-Name manuell prüfen.

**Fix:** Auto-detect-Logik: `['Tariffs_DE_EU', 'DE-EU', 'Tariffs', 'Tarif', 'DE_EU']`
als Kandidaten in Reihenfolge prüfen.

---

### P3 — Sika SSC KNR-Normalisierungs-Bug (~772k EUR Scheindefizit)

**Situation:** SSC Sika hat zwei KNRs im System (511241 + Variante).
Beim Laden aus bi_top20_data.pkl wurde KNR-Filterung falsch angewandt →
falsche Scope-Abgrenzung → ~772k EUR Scheindefizit (Sendungen doppelt
oder falsch zugeordnet).

**Erkennung:** Vor Analyse: `bi[bi['Kunden Name'].str.contains('Sika', na=False)]['Kunden Nr BK'].unique()` ausgeben. Wenn > 1 KNR: alle explizit listen, Scope-Entscheidung dokumentieren.

**Generalisierung:** Bei Kunden mit mehreren Niederlassungen / Konzern-KNRs
(SSC, CHT-Länder-Split) immer KNR-Liste empirisch erheben, nicht aus
Handover übernehmen.

---

### P4 — Cross-System-Schatten-Einträge (8-stellige Auftragsnummern)

**Situation:** AX-Tagesbericht enthält Dinas-Nummern (8-stellig) als
Schatten-Einträge für Cross-System-Sendungen. Diese haben alle Erlöse = 0,
Tonnage = 0, aber belegen Zeilen im Datensatz. Nicht gefiltert → 62% der
scheinbaren DLV-Lücke ist Rauschen.

**Erkennung:** `ax['Auftragsnummer'].astype(str).str.len().value_counts()`
— wenn 8-stellige Einträge vorhanden: Cross-System-Filter nötig.

**Fix:**
```python
ax = ax[ax['Auftragsnummer'].astype(str).str.strip()
          .str.replace(r'\.0$', '', regex=True).str.len() >= 16]
```

**Sicherheit:** Vor Anwenden verifizieren dass alle <16-stelligen Einträge
Erlöse = 0 haben. Wenn nicht → separater Befund.

---

### P5 — Lane-Discovery: Handover unvollständig

**Situation:** EBM-Handover listete Lanes `IE, PL, EE, SK, HR`.
Tatsächlich im Datensatz: SI (15 Sendungen), DE (11), GB (9), ES (6),
PT (5), RS (2). SI hat eigenes DLV → gehört in Scope.

**Erkennung:** DIAGNOSE 3 Coverage-Validation deckt das auf (immer
alle Empfänger-Länder ausgeben, nicht nur Handover-Lanes).

**Generalisierung:** Handover-Lane-Liste als Mindest-Scope behandeln,
empirische Lane-Verteilung immer vollständig erheben.

---

### P6 — LDM-Fallback: Stellplätze oft leer, LDM als Proxy nötig

**Situation:** EBM hatte 171 Sendungen mit Stellplätze = 0 aber Lademeter > 0.
Ohne LDM-Fallback würden diese als "unbeurteilbar" herausgefiltert
(133k EUR nicht erreichbar).

**Erkennung:** DIAGNOSE 1 Ausgabe `Nur LDM (kein Stp)` > 0 bei
stellplatz-basiertem Calculator → Fallback nötig.

**Fix:**
```python
import math
stp_eff = (
    int(stp) if stp > 0
    else max(1, math.ceil(ldm / 0.4)) if ldm > 0
    else 0
)
```
Sendungen mit `stp_eff = 0` nach Fallback → unbeurteilbar, herausfiltern.

**Generalisierung:** Bei jedem stellplatz-basierten Kunden: LDM/Stp-Ratio
aus DIAGNOSE 1 ablesen (Erwartung ~0.4 LDM/Stp). Starke Abweichung →
kundenspezifische Ratio verwenden.

---

### P7 — DLV-Cap-Risiko: Stellplatz-Obergrenze des Tarifs

**Situation:** EBM DLV deckt maximal 33 Stellplätze ab. Sendungen mit
Stp > 33 erhalten keinen Lookup-Treffer (None) oder werden auf 33 gecappt.
Ohne explizites Cap-Handling: stille Fehlklassifikation oder LookupError.

**Erkennung:** In DIAGNOSE 2, Schritt 5: Pricing-Knicke-Kurve auf Maximum
prüfen. `max_pallet = max(prices)` aus Calculator `_lookup()`-Logik ablesen.

**Fix:** Im Cluster-Key das oberste Band als `[max_pallet - 2 .. max_pallet]`
definieren (EBM: Band [31-33]). Sendungen mit Stp > max_pallet ins oberste
Band einordnen, nicht herausfiltern.

**Generalisierung:** Immer `_col_for_pallets()`-Logik / DLV-Struktur auf
Max-Wert prüfen. Cap explizit in Cluster-Band-Definition dokumentieren.

### P8 — Pre-Flight Pool-Schätzung vs. tatsächlicher Pipeline-Output

**Situation:** EBM Pre-Flight schätzte 314 beurteilbare Zeilen. Tatsächliche v1.9.4
Pipeline lieferte 296 beurteilbar + 49 DLV-Lücke + 20 out-of-scope = 365 Pool.
Pre-Flight hatte E3 (stp_eff=0) mit 64 geschätzt, Pipeline entfernte nur 5.
DLV-Lücke mit 32 geschätzt, tatsächlich 49.

**Erkennung:** Nach Step 2 Pool-Zahlen mit Pre-Flight-Vorhersage abgleichen.
Insbesondere E3 (stp_eff=0) hängt von LDM-Fallback-Implementierung ab:
Pre-Flight-Schätzung zählt Zeilen mit Stellplätze=0, ohne LDM-Fallback zu kennen.
Wenn Calculator LDM-Fallback hat → weniger E3-Ausfälle als geschätzt.

**Fix:** Kein Fix nötig. Pre-Flight-Zahlen sind Heuristik. Diskrepanz < 20 % akzeptabel.
Bei Diskrepanz > 20 %: E3-Filter-Logik im Calculator nachprüfen und dokumentieren.

**Generalisierung:** Pre-Flight ist Navigations-Instrument, kein exakter Vorab-Check.
Tatsächliche Pool-Zahlen aus Step 2 stets separat dokumentieren und als Audit-Basis
verwenden, nicht Pre-Flight-Schätzung.
