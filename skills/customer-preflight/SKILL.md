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

### P9 — Selbst-referenzielle Sub-Master mit Erlöse=0 (administratives Muster)

**Situation:** Fischerwerke AX-Daten enthalten Zeilen mit `has_ms=True, has_ua=True`
(Mastersendung gesetzt, eigener Unterauftrag vorhanden) **und** Erlöse Fracht = 0.
Diese Zeilen sind **keine Sendungen** — sie sind administrative Sammelgruppenköpfe,
die AX zur internen Bündelung erzeugt. Die eigentlichen Erlöse liegen auf den
echten Sub-Zeilen (`has_ms=True, has_ua=False`).

**Erkennung:** In DIAGNOSE 1 beim Sub-Zeilen-Check: wenn `has_ms AND has_ua` AND
`Erlöse_Fracht == 0` für alle solchen Zeilen → administratives Muster, kein Datenfehler.

**Fix:** Diese Zeilen **nicht** in den Audit-Pool aufnehmen und **nicht** als DLV-Lücke
oder M_over werten. In `enrich_master_sub()` bereits korrekt behandelt: Zeilen mit
`has_ua=True` werden als Sub-Master erkannt und aus dem Vergleichs-Pool ausgeschlossen.

**Präzedenzfall:** Fischerwerke (KNR 409480), ca. 49 selbst-referenzielle Sub-Master
identifiziert im Pre-Flight (alle Erlöse = 0). Gesamtbetrag 0 EUR → kein Audit-Impact.

**Generalisierung:** Sub-Master-Pattern ist kein Fehler in der Datenmigration. Es
entsteht wenn AX mehrere Dinas-Sendungen in einer Mastersendung bündelt und dabei
einen Gruppen-Kopf mit 0-Erlösen erzeugt. Prüfe bei jedem neuen Kunden in D1:
`df[(df.has_ms) & (df.has_ua)]["Erlöse Fracht"].sum()` — wenn ≈ 0 → ignorieren.

---

### P10 — Return-/Import-Route-Files kontaminieren DLV-Pool

**Situation:** DLV-Verzeichnis kann Dateien für Reverse-Routen enthalten
(z. B. `ES-43300 → DE-72178 Waldachtal`). Diese sind Import-Tarife, keine
Export-Tarife. Ein Calculator, der den AFL-Header ("Ab frei geladen … bis frei Haus
DE-72178") nach dem DE-72-Muster durchsucht, matcht fälschlicherweise auch auf den
Ziel-String "DE-72" im Bestimmungsort-Teil — und lädt die Datei als DE-Origin-Route.

**Folge:** DLV-Pool enthält Import-Preise (oft deutlich niedriger als Export).
Betroffene Lanes zeigen massive scheinbare M2\*-Defizite, die in Wirklichkeit
Calculator-Artefakte sind. Gesamtdifferenz kann um ≥ 60 % verfälscht werden.

**Erkennung:**

1. **DIAGNOSE 2: DLV-Dateinamen prüfen** — enthält die Liste Dateien mit Muster
   `<ZIELLAND-PLZ>_DE-72` oder `nach DE-72` in beide Richtungen?
   ```
   grep -i "nach de-72\|de-72 nach\|DE-72.*import" <dlv-dateinamen>
   ```
2. **Step 3: massive M2\*-Cluster** auf einzelnen Lanes mit Reverse-Route-Files
   sind verdächtig (z. B. alle ES stp1-5 -68 % Δ).
3. **Origin-Match-Code prüfen:** Wenn die Funktion `re.search(r"DE-72", afl_cell)`
   auf dem vollen AFL-String läuft statt nur auf dem Origin-Teil → anfällig.

**Fix:** Origin-Match-Funktion korrigieren — AFL-String vor "bis" abschneiden und
DE-72-Match nur auf diesen Origin-Teil anwenden:

```python
origin_part = re.split(r"\bbis\b", afl_cell, maxsplit=1)[0]
if re.search(r"DE-72\d*", origin_part):
    origin_de72 = True
```

Alternativ: Reverse-Route-Files in einen dedizierten Unterordner verschieben und
diesen Ordner via `_SKIP_DIRS` ausschließen.

**Präzedenz:** Fischerwerke (KNR 409480), Bug C, Commit `61f229e` (2026-04-26).
4 Import-DLV-Dateien entfernt. ES-43300 2025: p1 von 130 EUR (Import) auf 295 EUR
(Export) korrigiert. Gesamtdifferenz ohne Fix: −97.669 EUR (−41,1 %); nach Fix: −36.318 EUR.

**Generalisierung:** Bei jedem per-Route-DLV-Calculator (Fischerwerke-Typ) in DIAGNOSE 2:
DLV-Verzeichnis auf Reverse-Route-Dateien prüfen, Calculator Origin-Match-Logik auf
Substring-vs.-Full-String-Problem testen.

---

### P11 — Coverage-Test vollständig durchführen, kein Sample

**Situation:** GATE D eines Pre-Flights wurde auf einem 30-Zeilen-Sample ausgeführt
(zufällig oder per `head(30)`). Das Sample zeigte 100 % Calculator-Coverage.
Beim Full-Coverage-Lauf über alle 826 AX-Pool-Zeilen derselben Lane (GB) wurden
10 Area-Codes gefunden, für die das DLV **keine** Zonen-Einträge enthält. Der
Calculator wirft für diese Rows `LookupError` → sie landen im Null-Pool, nicht im
Haupt-Pool. Das Sample hatte diese Codes statistisch nicht erwischt.

**Folge:** 93 Rows / 61.917 EUR werden als DLV-Lücke klassifiziert statt als
Calculator-treffer. Fehlende Codes: WF (45 Rows), ME (22), LS (9), NE (4),
WN (3), BL (3), SA (3), PL (2), YO (1), CH (1). Ohne Full-Run bleibt die Lücke
unentdeckt und der Step-2-Pool ist systematisch um ~7,5 % zu klein.

**Erkennung:**

1. **DIAGNOSE 3 / GATE D**: Coverage-Lauf immer über **alle** AX-Pool-Zeilen laufen
   lassen, niemals `head(n)` oder Random-Sample:
   ```python
   errors = []
   for _, row in pool.iterrows():
       try:
           calc.calculate(row["empf_plz"], row["empf_land"], ...)
       except LookupError as e:
           errors.append((row["empf_plz"], str(e)))
   ```
2. **Auch bei scheinbar "gut abgedeckten" Ländern** wie GB oder IT — Area-Code-Tabellen
   im DLV können selektive Lücken haben, die erst bei vollständiger Iteration sichtbar werden.

**Fix:** Vollständigen Coverage-Lauf als Pflicht-Gate in Pre-Flight §6 (GATE D).
Für identifizierte Lücken-PLZ: Klärung mit Spediteur/Noerpel, welche Zone zuzuordnen ist.
Bis zur Klärung als DLV-Lücke dokumentieren.

**Präzedenz:** HERMA GmbH (KNR 423650), GATE D (2026-04-27).
GB-Pool: 826 Rows total; 30-Row-Sample → 0 Fehler; Full-Run → 93 Rows LookupError
(10 fehlende UK Area-Codes). Σ Erlöse Fracht: 61.917 EUR betroffen.

**Generalisierung:** Jeder Calculator mit Land/PLZ/Area-Code-Lookup kann selektive
Lücken haben. Full-Coverage ist kein Optimierungs-Schritt — es ist ein Pflicht-Gate.
Gilt besonders für: GB (Area-Codes), IT (PLZ-Zonen), ES (PLZ-Ranges), FR (Dept-Codes).

---

### P12 — Pricing-Mode-Wechsel zwischen DLV-Versionen

**Situation:** Eine neue DLV-Version wechselt nicht nur die Raten, sondern die
Pricing-Logik selbst (z. B. per-100-kg → Flat-Rate pro Sendung; kg-basiert →
Stellplatz-basiert). Calculator-Code spiegelt nur eine der Logiken wider und
verwendet diese unverändert auch für das andere DLV-Jahr.

**Folge:** Massive systematische Fehlpreise über alle Sendungen im betroffenen
Zeitraum. HERMA-Präzedenz: 2.351 Sendungen Jan–Mär 2026 mit 2025-Raten berechnet
(Σ Erlöse ~1.248.277 EUR betroffen; alle WB1/WB4-Länder ES/IT/FR/GB/PT/RS betroffen).

**Erkennung in DIAGNOSE 2:**
1. Bei mehreren DLV-Versionen pro Kunde: **5 Sample-Lookups pro Lane in beiden
   Versionen** vergleichen.
2. Wenn Δ ≠ 0 für eine Lane, prüfen:
   - **(a) Rate-Anpassung** (akzeptabel, falls Calculator shipment_date-Dispatch hat)
   - **(b) Pricing-Mode-Wechsel** (immer ein Calculator-BUG)
3. Unterscheidung (a) vs. (b): DLV-Sheet-Spalten der beiden Versionen vergleichen.
   - Falls Spalten-Bedeutung wechselt (z. B. kg-Bänder → PLZ-Bänder) → Typ (b)
   - Falls nur Werte sich unterscheiden → Typ (a)
4. Auch wenn Struktur gleich aussieht: **Logik-Check** — sind die Werte "per 100 kg"
   oder "pro Sendung" (steigen die Werte proportional mit dem Gewicht oder nicht)?

**Fix:**
- Typ (a): `shipment_date`-Dispatch im Calculator hinzufügen; altes und neues DLV
  laden; per Datum das passende nutzen.
- Typ (b): Zwei separate parse/lookup-Funktionen (eine pro DLV-Logik) plus Dispatch.

**Präzedenz:** HERMA Gate B (2026-04-27), Commit `c26dbe1`.
2025 WB1 (Preis pro Sendung, andere Werte) vs. 2026 Haftmaterial (Preis pro Sendung,
revidierte Werte). Fix: `_2026_CUTOFF = date(2026, 1, 1)` + `use_2026`-Flag in
`_get_wb_sheet_name`. Tatsächlich selbe Parsing-Logik, nur andere Pfade.

**Generalisierung:** Vor jedem Step 2 prüfen: hat der Calculator einen
`shipment_date`-Parameter? Wird er verwendet? Gibt es mehrere DLV-Versionen im
Verzeichnis, die nicht alle in der Dispatch-Logik berücksichtigt werden?

---

### P13 — Versender-Name als Routing-Key zwischen Calculatoren

**Situation:** Ein Kunde hat mehrere Sparten oder Geschäftseinheiten mit
unterschiedlichen DLVs (Beispiel: HERMA Haftmaterial vs. HERMA Etiketten).
Die AX-Daten enthalten das Feld "Versender Name" als einzigen Diskriminator.
Der Calculator kennt nur einen DLV-Pfad (den der Hauptsparte).

**Folge:** Sendungen der Nebensparte werden mit falschen Raten bepreist.
Scheinbare M2\*-Defizite (AX < DLV) auf der Nebensparten-Lane — denn die
Nebensparte hat typischerweise günstigere DLV-Raten.
HERMA-Präzedenz: Etiketten NT 2026 hat gleiche Raten wie Haftmaterial ≤ 3000 kg,
aber abweichende Raten > 3000 kg (bis Δ −560 EUR at 3100 kg ES zone 5).

**Erkennung:**
1. **DIAGNOSE 2 (DLV-Listing):** DLV-Verzeichnis zeigt mehrere Unterordner pro
   Kunde (z. B. `Herma Haftmaterial/` + `Herma Etiketten/`). Je Unterordner
   existiert ein separates DLV-Workbook.
2. **DIAGNOSE 1 oder 3 (AX-Daten):** `df["Versender Name"].value_counts()` liefert
   mehr als einen distinct Wert pro KNR. Wenn die Werte fachlich auf verschiedene
   Sparten hinweisen → Routing-Logik prüfen.
3. **Step 3 (M-Klassen-Analyse):** Wenn eine bestimmte Versender-Variant alle
   M2\*-Rows dominiert → Hinweis auf falschen DLV.

**Fix:**
Calculator parametrisierbar gestalten (Gate-A-Pattern):
```python
haft_calc = HermaCalculator()  # default: Haftmaterial
etik_calc = HermaCalculator(
    dlv_2026_ohne=_ETIK_2026_OHNE,
    dlv_2026_mit=_ETIK_2026_MIT,
)
```
Dispatcher im Build-Script anhand `row["Versender Name"]`:
```python
calc = etik_calc if "etiketten" in row["Versender Name"].lower() else haft_calc
```

**Präzedenz:** HERMA Gate A (2026-04-27), Commit `c26dbe1`.
`_ETIK_2026_OHNE/_MIT` hinzugefügt; `HermaCalculator.__init__` mit
`dlv_2026_ohne`/`dlv_2026_mit`-Parametern.

**Generalisierung:** Bei DIAGNOSE 2 immer mehrere DLV-Unterordner als Warnsignal
für Sparten-Routing prüfen. Wenn Unterordner vorhanden: distinct Versender-Name-
Werte in AX-Daten ausgeben und mit Ordnerstruktur abgleichen.

---

### P14 — DLV-Datei "durch neue Tarife ersetzt" kontaminiert Versionsvergleich

**Situation:** DLV-Verzeichnisse enthalten häufig historische DLV-Versionen in
Unterordnern wie `durch neue Tarife ersetzt/`, `Archiv/` oder `ersetzt durch neue
Offerten/`. Ein Pre-Flight-Versionsvergleich (DIAGNOSE 2 Gate: zwei DLV-Versionen
vergleichen) lädt versehentlich eine veraltete Datei aus einem solchen Archiv-
Unterordner und vergleicht sie mit der aktuellen Version.

**Folge:** Der gemeldete Δ-Wert ist ein Vergleich mit einer veralteten Tarifdatei,
nicht mit der tatsächlich in der Produktion verwendeten. Im HERMA-Präzedenzfall wurde
ein Δ bis −560 EUR (ES Etiketten ≥ 3100 kg) gemeldet — tatsächlich haben die aktuelle
Etiketten-NT-Datei und die Haftmaterial-Datei **identische** Raten für ≤ 3000 kg.
Der scheinbare Unterschied stammte aus dem veralteten `durch neue Tarife ersetzte`-File.

**Erkennung in DIAGNOSE 2:**
1. Beim DLV-Listing: `rglob("*.xlsx")` erfasst auch Archiv-Unterordner.
   Archiv-Marker als Pfad-Substrings ausschließen:
   ```python
   ARCHIV_MARKER = ['durch neue', 'ersetzt', 'archiv', 'alt', 'obsolet', 'historisch']
   def is_active_dlv(path: Path) -> bool:
       pstr = str(path).lower()
       return not any(m in pstr for m in ARCHIV_MARKER)
   active_dlvs = [p for p in DLV_DIR.rglob('*.xlsx') if is_active_dlv(p)]
   ```
2. Dateinamen-Vergleich: NT-Suffix ("_NT") oder Datum im Namen ist ein Hinweis
   auf eine neue Tarif-Version; Dateien ohne diese Marker könnten veraltet sein.
3. Wenn ein Archiv-Unterordner existiert und der Vergleich große Δ zeigt: immer
   prüfen, ob die aktuelle NT-Datei tatsächlich andere Werte hat (manueller
   Spot-Check 5 Zeilen).

**Fix:** Archiv-Filter in alle DLV-Scan-Routinen integrieren. Beim Calculator-
Loading immer explizit den aktiven Pfad aus der definierten Konstante nehmen
(z. B. `_ETIK_2026_OHNE`), nie per `glob()` aus dem vollen Verzeichnisbaum.

**Präzedenz:** HERMA Gate A (2026-04-27). Pre-Flight meldete Δ bis −560 EUR
für Etiketten-ES (3100 kg+) basierend auf Vergleich mit `ersetzt durch neue
Tarife/20251212_Herma_Frachtraten ohne VL_2026-2028.xlsx`. Aktueller NT-Stand:
`20251212_Herma_Frachtraten ohne VL_2026-2028_NT.xlsx` — identisch für ≤ 3000 kg.

**Generalisierung:** Jeder Pre-Flight-Versionsvergleich muss Archiv-Unterordner
explizit ausschließen. Regel: "Aktive Datei = kein Archiv-Marker im Pfad UND
größtes Datum im Dateinamen innerhalb des Zielordners."

### P15 — Upload-Ordner sind aktive erweiterte Tarife, nicht Archiv

**Situation:** DLV-Verzeichnisse enthalten häufig einen `Upload/`-Unterordner.
Ein naiver Archiv-Filter (der "upload" als Ausschluss-Marker behandelt) übersieht
diese Dateien. Der `Upload/`-Ordner enthält jedoch **nicht** veraltete, sondern
**aktive erweiterte Tarife** — insbesondere Gewichtsbänder oder Routen, die im
Jahrestarif nicht abgedeckt sind.

**Präzedenz:** Bitzer IT (2026-04-27). Die Datei
`Bitzer Rottenburg/2026/Upload/V_FRA_7042_O_IT_ALL_Bitzer.xlsx` enthält das
erweiterte Gewichtsband bis 24 000 kg (FTL-Flat-Rate 1120.8/1260.1 EUR/Sendung)
sowie leicht angepasste Raten für alle Bänder. Das Jahres-DLV 2025 endet bei
20 000 kg und hat eine fehlerhafte per-Sendung-Erkennung für das 20 000-kg-Band
(Lookahead detektiert fälschlich "per Sendung" aus der FTL-Zeile). Ohne die
Upload-Datei würde der Calculator FTL-Sendungen falsch berechnen.

**Erkennung:**
1. `Upload/`-Unterordner im Pfad ≠ Archiv. Archiv-Marker sind: `durch neue`,
   `ersetzt`, `archiv`, `alt`, `obsolet`, `historisch`. `upload` ist KEIN Marker.
2. Wenn ein `Upload/`-Ordner existiert und eine Datei mit gleichem Kundennamen/
   Zielland enthält: prüfen, ob diese Datei neue Gewichtsbänder oder angepasste
   Raten hat — sie ist wahrscheinlich die aktuellere Tarif-Grundlage.
3. Calculator-Konstante `_find_dlv()` erhält einen `allow_upload`-Parameter:
   Wenn `dlv_dir` selbst ein Upload-Pfad ist, werden Upload-Dateien einbezogen;
   andernfalls ausgeschlossen (verhindert versehentliches Einlesen des Upload-
   Ordners bei Glob über das Hauptverzeichnis).

**Fix:** Upload-Ordner in allen DLV-Scan-Routinen explizit als **aktiv** behandeln.
Calculator-Konstanten, die auf `Upload/`-Pfade zeigen, explizit definieren:
```python
_ROT_2026_UPLOAD = _BASE / "Bitzer Rottenburg/2026/Upload"
_COUNTRY_DLV["IT"] = (_ROT_2026_UPLOAD, "V_FRA_7042_O_IT_ALL_Bitzer.xlsx")
```
Archiv-Filter anpassen:
```python
ARCHIV_MARKER = ['durch neue', 'ersetzt', 'archiv', 'alt', 'obsolet', 'historisch']
# "upload" ist KEIN Archiv-Marker — nicht in diese Liste aufnehmen
```

**Generalisierung:** Die Unterscheidung "Archiv vs. aktive Erweiterung" kann nicht
allein aus dem Ordnernamen abgeleitet werden. Entscheidend ist der Inhalt: Enthält
die Datei Bänder/Routen, die im Jahrestarif fehlen? → aktive Erweiterung. Enthält
sie ältere Versionen bekannter Bänder? → Archiv.

---

### P16 — Upload-DLV ist kein universeller Ersatz für Standard-DLV: Zonen-Map vergleichen

**Situation:** Ein `Upload/`-Ordner enthält eine erweiterte DLV-Datei (z. B. höhere
Gewichtsbänder bis 24 000 kg, FTL-Flat-Rate). Das Calculator-Lade-Code setzt diese
Datei als **universellen Ersatz** für das Standard-Jahres-DLV ein — für alle
Sendungen aller Zeiträume. Dabei bleibt unbeachtet, dass das Upload-DLV in der
Zonen-Zuordnung (PLZ → Zone) vom Standard-DLV abweicht.

**Folge:** PLZs, die im Standard-DLV Zone 2 sind, werden im Upload-DLV Zone 4
berechnet (oder umgekehrt). Der Calculator produziert für diese PLZs systematisch
falsche DLV-Soll-Werte. Das BI-Abgleich zeigt massive M2-Cluster auf diesen PLZs —
die nicht auf Abrechnungsfehler hinweisen, sondern reine Calculator-Artefakte sind.

**Bitzer-IT-Präzedenz (2026-04-28):** PLZ 32010 (Belluno):
- Standard-DLV 2025 (`20250205_Bitzer_Export Italien.xlsx`): Zone **2** → 767 EUR bei 11 800 kg
- Upload-DLV 2026 (`V_FRA_7042_O_IT_ALL_Bitzer.xlsx`): Zone **4** → 1 038 EUR bei 11 800 kg
- Tatsächliche BI-Abrechnung 2025: 767,00 EUR (exakter Zone-2-Match, kein M2)
- Vor Fix: 77 Rows, −21 511 EUR scheinbares M2-Defizit (Calculator-Artefakt)
- Nach Fix: 13 Rows (FTL-Anteil), +17 EUR (M1)

**Erkennung:**

1. **DIAGNOSE 2: Zonen-Maps beider Versionen vergleichen** — wenn Upload-DLV
   vorhanden: mindestens 5 Spot-PLZs in Standard und Upload nachschlagen:
   ```python
   spot_plz = ["32010", "00134", "35040", "40013", "00198"]  # anpassen
   for plz in spot_plz:
       z_std    = lookup_zone(plz, zone_map_standard)
       z_upload = lookup_zone(plz, zone_map_upload)
       if z_std != z_upload:
           print(f"ZONE-ABWEICHUNG: PLZ {plz}: Standard={z_std}, Upload={z_upload}")
   ```
2. **Wenn Zone-Abweichungen gefunden:** Upload ist **kein universeller Ersatz**.
   Es handelt sich um eine Zonen-Reform-Amendment: Bestimmte PLZs wurden neu
   klassifiziert. Upload-DLV gilt nur für neue Verträge / ab einem Stichtag.
3. **Standard-DLV bleibt primär** für alle Sendungen innerhalb seiner Gültigkeitsperiode.
   Upload-DLV gilt ab seinem expliziten Gültigkeitsbeginn (aus AFL-Header oder
   Dateiname ablesen).
4. **Wenn nur Band-Erweiterung** (alle PLZ-Zonen gleich, nur höhere Gewichtsbänder
   vorhanden): Upload als Ergänzung für FTL-Bänder nutzbar, Standard für LTL-Bänder.

**Fix:** `shipment_date`-Dispatch im Calculator implementieren:

```python
_IT_CUTOFF = date(2026, 2, 1)   # Gültigkeitsbeginn Upload/2026

def _get_it(self, shipment_date: date | None = None):
    if shipment_date is not None and shipment_date >= _IT_CUTOFF:
        return self._load("IT_2026", _IT_DLV_2026), _VALID_FROM_2026, _VALID_TO_2026
    else:
        return self._load("IT_2025", _IT_DLV_2025), _VALID_FROM_2025, _VALID_TO_2025
```

Build-Script muss `shipment_date` aus BI-Daten (Feld `Leistungsdatum` o. ä.) an
`calculate()` übergeben; fehlendes Datum → konservativ Standard-DLV (früherer Tarif).

**Generalisierung:**
- "Upload-aktiv" (P15) ≠ "Upload ersetzt Standard".
- Reihenfolge der Diagnose: (1) Upload-Bänder vs. Standard-Bänder vergleichen →
  reine Band-Erweiterung oder Zonen-Reform? (2) Wenn Zonen-Reform: Stichtag aus
  Dateiname / AFL-Header bestimmen. (3) Dispatch implementieren, niemals beide
  Dateien ohne Stichtag kombinieren.
- Symptom in Step 3: große M2-Cluster auf einzelnen PLZ-Gruppen, die genau der
  Zonen-Grenze einer der beiden DLV-Versionen entsprechen → immer Zonen-Map-
  Vergleich erzwingen bevor strukturelle Ursache (Migrationsschaden) angenommen wird.

---

### P17 — Zone-Lookup-Format-Mismatch (HELU + Hornschuch, 2026-04)

**Situation:** Calculator `zone_fn` gibt einen Zone-Schlüssel zurück, der nicht
mit den Keys im DLV-Dict übereinstimmt — wegen Wert-Mismatch, Typ-Mismatch oder
falscher PLZ-Stelligkeit.

**Drei Varianten:**

**P17-A (Wert-Mismatch):** `zone_fn` gibt `"ES-20870"` zurück; DLV-Dict-Key
ist `"ES"` (Regex in `_parse_vertical` extrahiert nur Zeichen bis zum Bindestrich).
`dict.get("ES-20870")` → `None` → `LookupError`.
Erkennung: 100 % LookupError auf einer Lane obwohl DLV vorhanden. Zone-Key vs.
Dict-Keys ausgeben (`list(rates.keys())[:5]`).
Fix: `zone_fn` an Regex-Extraktion anpassen.
Präzedenz: HELU H1 ES-Mendaro (67 Rows betroffen), Commit 897a2c6.

**P17-B (Typ-Mismatch):** `rates_by_col` mit `int`-Keys aufgebaut (Spalten-Indizes),
`zone_fn` gibt `str(col)` zurück. `dict.get("1")` auf int-Key-Dict → `None`.
Erkennung: Identisch P17-A. Fix: Dict mit `str(c)`-Keys.
Präzedenz: HELU H2 GB rates_by_col (55 Rows betroffen), Commit 897a2c6.

**P17-C (PLZ-Stelligkeit):** DLV hat 1-stellige Zonen (z. B. AT: 1–9, PT: 1–9).
Calculator extrahiert 2-stelligen PLZ-Prefix als Zone → kein DLV-Eintrag.
Erkennung: Alle LookupErrors auf einem Land mit 1-stelliger Zonen-Struktur.
Fix: Länderspezifische Stelligkeit im `_zone()`-Dispatcher (gleiche Logik wie PT
auf AT ausdehnen).
Präzedenz: Hornschuch G3 AT (PLZ 4191 → Zone "41" statt "4", 1 Row), Commit a0a9822.

**Generalisierung:** Bei jedem LookupError-100%-Cluster auf einer Lane:
```python
# Diagnostic snippet
sample_row = pool[pool['empf_land'] == 'PROBLEM_LAND'].iloc[0]
zone_key = calc._zone(sample_row['empf_plz'], 'PROBLEM_LAND')
print(f"zone_key: {repr(zone_key)}")
rates = calc._rates.get(('PROBLEM_LAND', zone_key))
print(f"rates: {rates}")
# list first 5 dict keys for the land
land_keys = [k for k in calc._cache if k[0] == 'PROBLEM_LAND'][:5]
print(f"cache keys: {land_keys}")
```

---

### P18 — Additiver Zuschlag wird als Ersatz-Tarif behandelt (Hornschuch, 2026-04)

**Situation:** Ein DLV enthält einen per-Sendung-Aufschlag (z. B. Paletten-basiert,
326–975 EUR) ZUSÄTZLICH zum per-kg-Carrier-Tarif. AX bucht den Aufschlag als
separate Erlöskategorie, nicht unter "Erlöse Fracht". Wenn der Calculator den
Aufschlag in die DLV-Soll-Kalkulation einbezieht (oder statt des per-kg-Tarifs
verwendet), entsteht ein massiver scheinbarer M_over (AX buchte nicht so viel).

**Korrekte Behandlung:** Per-kg-Tarif = korrekte Vergleichsbasis für "Erlöse Fracht".
Aufschlag ist separates Erlöselement und außerhalb des Audit-Scopes dieser Lane.

**Erkennung:**
1. In DIAGNOSE 2 (DLV-Listing): Wenn DLV-Datei einen "Paletten-Zuschlag"- oder
   "Anlieferungs-Aufpreis"-Sheet enthält → additiver Aufschlag-Typ prüfen.
2. Empirischer Validierungstest: Pool-Rows dieser Empfänger-Gruppe berechnen.
   Wenn fp = 0,0000 für alle Rows → per-kg-Tarif ist korrekte Basis.
3. Wenn fp stark positiv (M_over) → Aufschlag in DLV-Soll eingerechnet → falsch.

**Fix:** DLV-Soll-Berechnung = nur per-kg-Anteil. Aufschlag-Datei in Calculator
nicht laden oder explizit als additives Non-Fracht-Element markieren.

**Präzedenz:** Hornschuch G2 Castorama/Leroy Merlin (318 FR-Rows). Castorama-DLV
(20250131) definiert Paletten-Aufschlag (326–975 EUR/Sendung) zusätzlich zu
ContiTech per-kg. AX bucht nur per-kg unter Erlöse Fracht.
Ergebnis: fp = 0,0000 für alle 318 Rows empirisch bestätigt. Kein Calculator-Bug.

---

### P19 — FTL-Flat-Rate vs. per-kg-Extrapolation (M2-Artefakt bei Großsendungen)

**Situation:** AX rechnet Großsendungen (typisch > 12 000 kg) als Vollfahrzeug-
Festpreis (FTL-Flat, z. B. 1.120 EUR für ~14 000 kg). Der Calculator extrapoliert
den per-kg-Tarif linear auf das gesamte Gewicht → DLV-Soll deutlich höher als
die FTL-Flat. Ergebnis: systematische M2-Rows bei Großsendungen ohne Abrechnungsfehler.

**Erkennungs-Muster:**
1. M2-Rows mit ton > 12 000 kg und konstantem ef-Betrag (z. B. 1.120 EUR für alle
   Rows in einem Tonnage-Bereich trotz unterschiedlicher Gewichte).
2. fp zwischen −7 % und −17 % (unterhalb der 5 %-M2-Schwelle).
3. ContiTech DLV enthält separate "roundtrip"- oder FTL-Spalte mit Flat-Werten
   (873–1.152 EUR) — diese Werte entsprechen den ef-Beträgen.
4. AX-Billing entspricht dem FTL-Band, nicht der per-kg-Extrapolation.

**Behandlung:** KEIN Calculator-Bug, KEIN Abrechnungsfehler. AX rechnet korrekt
nach FTL-Vertrag. Calculator-per-kg-Extrapolation überschätzt den DLV-Soll bei
Großsendungen. M2-Rows als "FTL-Flat-Rate-Artefakt" dokumentieren, keine Korrektur.

**Optionale Calculator-Erweiterung:** FTL-Band ab Tonnage-Schwelle implementieren
(nur wenn mehrere Kunden betroffen und Volume > 10 TEUR). Aufwand: ~2 h.

**Präzedenz:** Hornschuch M2 (7 Rows, IT zone31/33/20, ES zone12).
Tonnage 13.000–17.000 kg; ef: 1.120/1.270/1.700 EUR (Flat); dlv: 1.200–1.900 EUR
(per-kg-Extrapolation). Net Δ dieser 7 Rows: −860 EUR (fp = −7 bis −17 %).

---

### P20 — Erlös-Spalten-Separation: AX billt mehrere Erlös-Komponenten getrennt

**Situation:** AX kann Maut, Diesel-Zuschlag, und andere Surcharges in **separaten Erlös-Spalten**
billen (`Erlöse Maut`, `Erlöse Diesel`, `Erlöse Nebengebühr` etc.). Wenn das DLV diese
Komponenten **integriert** in die Hauptrate aufnimmt (z. B. `basispreis + de_maut`), aber
die Pipeline `ef = Erlöse Fracht` verwendet, entsteht ein systematischer negativer Bias:

```
ef   = Erlöse Fracht          (ohne Maut)
dlv  = basispreis + de_maut   (mit Maut)
→ delta = ef − dlv = −de_maut systematisch negativ
→ fp ≈ −Maut% (z. B. −2,4 % für Sika 491063)
```

**Erkennung in DIAGNOSE 2:**
```python
# Alle Erlöse-Spalten auflisten
erloese_cols = [c for c in bi.columns if 'erlö' in c.lower()]
# Σ pro Pool
for col in erloese_cols:
    pool[col] = pd.to_numeric(pool[col], errors='coerce').fillna(0)
    sigma = pool[col].sum()
    pct   = sigma / pool['ef'].sum() if pool['ef'].sum() > 0 else 0
    print(f"{col}: {sigma:,.2f} ({pct:.2%} von Erlöse Fracht)")
```

**Entscheidungsregel:**
- Wenn `Σ Erlöse [Komponente] > 1 % von Σ Erlöse Fracht`: DLV-Sheet prüfen.
  - DLV enthält Maut/Diesel in Hauptrate → P20 betroffen; `ef_total = ef + Erlöse [Komponente]`
  - DLV hat separate Maut/Diesel-Kalkulation → Pipeline vergleicht balanciert, kein P20
- Wenn `Σ Erlöse [Komponente] < 1 %`: negligible, kein Handlungsbedarf.

**Korrektheit-Check über Kunden (Rückwirkend geprüft 2026-04-28):**

| Kunde | Σ Erlöse Maut | DLV-Treatment | P20? |
|---|---|---|---|
| EBM-Papst | 15.596 EUR (2,95 %) | `dlv = r.basispreis` (ohne Maut) | Nein — balanciert |
| CHT Germany | 12.742 EUR (4,08 %) | `delta_fracht = Erlöse Fracht − basispreis` | Nein — balanciert |
| HERMA GmbH | 6.518 EUR (0,25 %) | `maut_surcharge=None` in Calculator | Nein — balanciert |
| GEZE GmbH | 17 EUR (0,003 %) | — | Negligible |
| Bitzer / HELU / Hornschuch | 0 EUR | — | Nein |
| **Sika DE 491063** | **30.555 EUR (2,39 %)** | `dlv = basispreis + de_maut` | **JA — P20 bestätigt** |

**Pipeline-Korrektur für betroffene Kunden:**
```python
# Option A: ef_total (AX-seitig erweitern)
ef_total = ef + Erlöse_Maut  # + weitere separierte Komponenten

# Option B: dlv_basis (DLV-seitig reduzieren)
dlv_basis = float(r.basispreis)  # ohne r.maut_surcharge

# Beide Ansätze sind äquivalent. Wahl abhängig von der Pipeline-Struktur.
```

**Präzedenz:** Sika Deutschland GmbH (KNR 491063), Welle 1.
Nominelles Net Δ = −25.758 EUR (−1,97 %). Σ Erlöse Maut = 30.555 EUR.
Adjustiertes Net Δ = **+4.797 EUR (+0,37 %)**. Δ-Adjustment = +31,2 TEUR.
Rückwirkender Check aller 9 Welle-1+2-Kunden: Nur 491063 betroffen.

