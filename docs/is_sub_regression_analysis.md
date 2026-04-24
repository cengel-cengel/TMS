# is_sub-Filter Regression-Analyse — v1.9 Methodik

**Stand:** 2026-04-24 | **Datenbasis:** `output/bi_top20_data.pkl`, POST-Perioden
**Fragestellung:** Welche Zeilen werden unter Tonnage>0-Proxy anders klassifiziert
als unter explizitem is_sub-Check (`Mastersendung gesetzt AND kein Unterauftrag`)?

---

## §1 Methodik

**Methode A — Alter Proxy:** `keep = Tonnage (eff.) > 0`

**Methode B — Neu v1.9:** `is_sub = has_ms & ~has_ua` (§2e Rule A);
`keep = ~is_sub` (Master + Standalone)

Abweichungstypen:
- **FP (False Positive):** Proxy behält Zeile, v1.9 schließt sie aus.
  → Sub-Zeile mit Tonnage > 0 (proxy irrtümlich behalten, korrekt: ausschließen)
- **FN (False Negative):** Proxy schließt Zeile aus, v1.9 behält sie.
  → Nicht-Sub-Zeile mit Tonnage = 0 (proxy irrtümlich ausgeschlossen, korrekt: behalten)

---

## §2 Ergebnis-Matrix

| Kunde | KNR | POST-Zeilen | FP (Sub, Tonnage>0) | FP-EUR | FN (Non-Sub, Tonnage=0) | FN-EUR | Pass-Rate-Impact |
|-------|-----|-------------|---------------------|--------|------------------------|--------|-----------------|
| EBM-Papst | 410844 | 379 | **0** | — | 0 | — | **Keiner** |
| GEZE | 406035 | 7.752 | **153** | 17.614 € | 37 | 2.769 € | **Keiner (kein aktiver BI-PR)** |
| Fischerwerke | 409480 | 1.883 | **63** | 19.717 € | 0 | — | **Keiner (enrich_master_sub)** |
| Sika DE | 491063 | 1.443 | **0** | — | 0 | — | **Keiner** |
| SSC Sika | 511241 | 448 | **0** | — | 0 | — | **Keiner** |
| CHT Germany | 486073 | 779 | **0** | — | 0 | — | **Keiner** |
| HERMA | 423650 | 5.502 | **2** | 1.816 € | 30 | 5.333 € | **Keiner (enrich_master_sub)** |

**Gesamt FP:** 218 Zeilen, 39.147 € | **Gesamt FN:** 67 Zeilen, 8.102 €

---

## §3 Detailbefunde pro Kunde

### EBM-Papst (410844) — Keine Abweichung

Keine Sub-Zeilen mit Tonnage > 0 in POST-Daten. 2 Zeilen von beiden Methoden
gleich ausgeschlossen (Tonnage = 0, is_sub = False → unbeurteilbar).

### GEZE (406035) — FP: 153 Zeilen, FN: 37 Zeilen

**FP (153 Sub-Zeilen mit Tonnage > 0):**
- Sub-Zeilen haben `Mastersendung` gesetzt (als Float ≈ 7.09e15 = Auftragsnummer
  des Masters), `Unterauftrag = NaN`
- `Tonnage (eff.) > 0`: zwischen 11 kg und 480 kg
- Erlöse Fracht: 4,64 EUR bis 192 EUR pro Position
- Unter Proxy fälschlicherweise im Vergleichs-Set; v1.9 schließt korrekt aus
- **Keine Auswirkung auf aktuelle Berichte** — GEZE hat keinen aktiven BI-Pass-Rate-Vergleich
  (nur Unit-Tests, 9b.1). §8-Relevanz: latent, wird aktiv bei Etappe 9b.2.

**FN (37 Standalone-Zeilen mit Tonnage = 0 und Lademeter = 0):**
- `Mastersendung = NaN`, `Unterauftrag = NaN` → kein Sub, kein Master
- Tonnage = 0, Lademeter = 0 → **unbeurteilbar** gemäß §5.0
- Unter Proxy ausgeschlossen; v1.9 behält sie im Vergleichs-Set
- Als `unbeurteilbar` sollten sie VOR dem Calculator-Check gefiltert werden
- Keine Pass-Rate-Auswirkung, sofern `unbeurteilbar`-Filter angewendet wird

### Fischerwerke (409480) — FP: 63 Zeilen

**FP (63 Sub-Zeilen mit Tonnage > 0):**
- Sub-Zeilen mit Tonnage-Werten von 101 kg bis 7.422 kg (Stückgut-Sendungen)
- Erlöse Fracht: 21,41 EUR bis 850,42 EUR pro Zeile
- Unter Proxy fälschlicherweise im Vergleichs-Set
- **Keine Auswirkung:** `enrich_master_sub()` in `build_fischer_report.py` erkennt
  und entfernt Sub-Zeilen über den Mastersendungs-Vergleich — unabhängig vom
  Tonnage-Wert. Die 63 Zeilen werden dort bereits korrekt behandelt.

### Sika DE (491063), SSC Sika (511241), CHT Germany (486073) — Keine Abweichung

Alle POST-Zeilen stimmen zwischen Proxy und v1.9 überein.
- Sika DE: 18 Zeilen ausgeschlossen (Tonnage = 0, kein Mastersendungs-Eintrag → unbeurteilbar)
- SSC: 0 Ausschlüsse
- CHT: 38 Zeilen ausgeschlossen (sind Sub-Zeilen mit Tonnage = 0 → Proxy und v1.9 stimmen überein)

### HERMA (423650) — FP: 2 Zeilen, FN: 30 Zeilen

**FP (2 Sub-Zeilen mit Tonnage > 0):**
- 2 Zeilen mit Tonnage 2.293 kg und 24.000 kg (Großsendungen)
- Erlöse Fracht: 634 EUR und 1.182 EUR
- `enrich_master_sub()` behandelt diese bereits korrekt in `build_herma_report.py`
- **Keine Auswirkung auf aktuelle Berichte.**

**FN (30 Standalone-Zeilen mit Tonnage = 0 und Lademeter = 0):**
- Erlöse Fracht > 0 (Summe 5.333 EUR), aber keine Billing-Dimension
- → **unbeurteilbar** gemäß §5.0
- Analog GEZE: v1.9 behält diese; sie müssen vor Calculator-Check als `unbeurteilbar`
  gefiltert werden. Bestehende Cluster-Familien-Matching-Logik verarbeitet sie nicht.
- HERMA-Analyse steht noch unter Vorbehalt (DLV-Validierung ausstehend).

---

## §4 Methodische Erkenntnis: Zweiteiliger Filter

`filter_comparison_set()` entfernt ausschließlich Sub-Zeilen (`is_sub = True`).
Es ist kein Ersatz für den `~is_t0`-Filter der CHT-Scripts:

| Filter | Entfernt | Behält |
|--------|----------|--------|
| `~is_t0` (Tonnage>0) | Sub-Rows (wenn Tonnage=0) + Unbeurteilbar | Master-Rows (wenn Tonnage=0) fälschlicherweise entfernt |
| `filter_comparison_set()` | Nur is_sub-Rows | Alle Master + Standalone (inkl. unbeurteilbar) |
| **v1.9 vollständig** | `filter_comparison_set()` DANN `~unbeurteilbar` | Nur beurteilbare Master + Standalone |

**v1.9-Vollkette:**
```python
df = filter_comparison_set(df)           # Step 1: entfernt Sub-Rows
is_unbeurteilbar = (
    (pd.to_numeric(df['Tonnage (eff.)'], errors='coerce').fillna(0) <= 0) &
    (pd.to_numeric(df['Lademeter'], errors='coerce').fillna(0) <= 0)
)
df_vergleich = df[~is_unbeurteilbar]     # Step 2: entfernt unbeurteilbar
```

Diese Kette ist für Kunden relevant, die weder `enrich_master_sub()` noch
`~is_t0` verwenden (z. B. künftige Etappe 9b.2 GEZE BI-Vergleich).

---

## §5 STOP-Kriterium-Check

> "Wenn Regression-Test bei einem Kunden Pass-Rate-Verschiebung >2 Prozentpunkte
> zeigt: melden, gemeinsam entscheiden."

**Ergebnis: Kein aktiver Pass-Rate-Impact bei irgendeinem Kunden.**

- Alle Kunden mit FP-Zeilen verwenden `enrich_master_sub()` oder haben keinen
  aktiven BI-Pass-Rate-Vergleich
- FN-Zeilen (`unbeurteilbar`) werden nicht in Calculator-Vergleiche einbezogen
- STOP-Kriterium nicht ausgelöst — Sika-Re-Run kann fortgesetzt werden

---

## §6 Empfehlungen für Etappe 9b.2 (GEZE BI-Vergleich)

1. Verwende `filter_comparison_set()` statt `~is_t0`-Proxy
2. Füge `~unbeurteilbar`-Filter nach `filter_comparison_set()` hinzu
3. Die 153 GEZE FP-Zeilen (Sub-Rows mit Tonnage>0) müssen explizit ausgeschlossen
   werden — unter v1.9 korrekt, unter altem Proxy würden sie den Vergleich verfälschen
4. Die 37 FN-Zeilen sind `unbeurteilbar` und sollten im Report als §5.0-Lücke
   dokumentiert werden (Erlöse > 0, aber keine Billing-Dimension)

---

## §7 Resilienz-Analyse

### Befund

Die Formulierung "Kein aktiver Pass-Rate-Impact" ist technisch korrekt, verdeckt
aber eine strukturell wichtige Beobachtung:

**Die Tonnage>0-Proxy-Logik war bei drei Kunden strukturell fehlerhaft:**

| Kunde | Falsch klassifizierte Zeilen | EUR-Volumen | Schutz-Mechanismus |
|-------|------------------------------|-------------|-------------------|
| GEZE (406035) | 153 FP + 37 FN = 190 gesamt | 20.383 EUR | Kein aktiver BI-Vergleich |
| Fischerwerke (409480) | 63 FP | 19.717 EUR | `enrich_master_sub()` |
| HERMA (423650) | 2 FP + 30 FN = 32 gesamt | 7.149 EUR | `enrich_master_sub()` |

**Total: ≥ 285 falsch klassifizierte Zeilen, ≈ 47.249 EUR.**

Ohne `enrich_master_sub()` oder einen expliziten Schutz-Mechanismus wären bei
Fischerwerke und HERMA signifikante Pass-Rate-Verschiebungen aufgetreten:
- Fischerwerke: 63 Sub-Rows mit Tonnage>0 in der Vergleichsmenge → fehlerhafte
  fp-Werte (Sub-Erlöse sind anteilige Master-Beträge, keine selbständig
  bereinigte Fracht) → unkontrollierter §8-Kandidaten-Strom
- HERMA: 30 `unbeurteilbar`-Zeilen im Calculator → Calculator-Fehler oder
  Null-Outputs → Pass-Rate-Einbruch

### Schlussfolgerung

Die historisch korrekten Pass-Raten bei Fischerwerke und HERMA sind **nicht**
auf die Korrektheit des Tonnage-Proxys zurückzuführen, sondern auf die Redundanz
durch `enrich_master_sub()`. Der Proxy war ein latenter Fehler, der durch eine
nachgelagerte Funktion kompensiert wurde — ohne diese Kompensation hätte er
sichtbare Auswirkungen gehabt.

Dies unterstreicht die Notwendigkeit der v1.9-Zweistufigkeit (§2e Rule D):

> `filter_comparison_set()` (Stufe 1) + `~unbeurteilbar` (Stufe 2) ersetzen
> gemeinsam `enrich_master_sub()` als explizite, dokumentierte Schutzlogik
> statt impliziter, versteckter Kompensation.

Bei GEZE — dem einzigen Kunden ohne aktive Schutzlogik — wurde der Fehler
nur dadurch unsichtbar, dass kein aktiver BI-Pass-Rate-Vergleich implementiert
ist. Etappe 9b.2 muss zwingend die v1.9-Vollkette verwenden.

---

*Aktualisiert: 2026-04-24 (§7 Resilienz-Analyse ergänzt)*
*Erstellt: 2026-04-24 | Grundlage: bi_top20_data.pkl POST-Daten*
*Keine Code-Änderungen an bestehenden Report-Scripts.*
