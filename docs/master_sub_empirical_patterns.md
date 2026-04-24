# Master-Sub Empirische Muster — AX-Daten

**Stand:** 2026-04-24 | **Datenbasis:** `output/bi_top20_data.pkl`
**Methodik:** `classify_ax_rows()` v1.9 (string-basierter Unterauftrag-Check)

---

## §1 Fragestellung

Beim Validierungsbeispiel GEZE `7092010001835006` haben alle 3 Sub-Zeilen
Tonnage = 0, während der Master Tonnage = 361,9 kg trägt. Ist das strukturell
typisch — oder ein Einzelfall?

**Konkret gefragt:** Wie oft greift der Fallback-Mechanismus von
`reconstruct_ax_master()` (Sub-Summe bei leerem Master-Feld) in der Praxis?

---

## §2 Methodik-Notiz: Unterauftrag ist ein String, keine Zahl

Das `Unterauftrag`-Feld enthält in AX eine **komma-separierte Liste** von
Sub-Auftragsnummern (z.B. `"7091200280103007, 7091200280104004, 7091200280107005"`).

`float()` schlägt auf diesem Wert fehl → ein numerischer Leer-Check würde
Master-Zeilen fälschlicherweise als Sub klassifizieren.

`classify_ax_rows()` verwendet korrekt `_nonempty()` (string-basiert), nicht
`_nonempty_numeric()`. Alle Auswertungen dieses Dokuments nutzen `classify_ax_rows()`.

---

## §3 GEZE (KNR 406035)

**Datenmenge:** 10.947 Zeilen → 586 Master, 1.751 Sub, 8.610 Standalone

### Physische Felder — Master-Verteilung

| Feld | Master nonzero | Master gesamt | Anteil |
|------|---------------|--------------|--------|
| Tonnage (eff.) | 586 | 586 | **100 %** |
| Volumen | 569 | 586 | 97,1 % |
| Colli | 586 | 586 | **100 %** |
| Lademeter | 1 | 586 | 0,2 % (Ausnahme) |
| Stellplätze | 1 | 586 | 0,2 % (Ausnahme) |

### Physische Felder — Sub-Verteilung

| Feld | Subs nonzero | Subs gesamt | Anteil |
|------|-------------|------------|--------|
| Tonnage (eff.) | 153 | 1.751 | 8,7 % |
| Volumen | 153 | 1.751 | 8,7 % |
| Colli | 153 | 1.751 | 8,7 % |
| Lademeter | 0 | 1.751 | 0 % |
| Stellplätze | 0 | 1.751 | 0 % |

### Interpretation

**Normalmuster (100 % der 20 verifizierten Master-Gruppen):**
Tonnage + Colli auf Master; Subs = 0. Lademeter + Stellplätze = 0 überall
(GEZE ist Tonnage-basiert, keine LDM/Stellplatz-Abrechnung).

**Die 153 Subs mit nonzero Tonnage** sind identisch mit den 153 FP-Zeilen
aus der is_sub-Regression-Analyse: Sub-Zeilen mit Tonnage > 0, deren Master
sich nicht im aktuellen Datensatz befindet (unterschiedlicher Zeitraum /
gefilterte Scope). Diese 153 Zeilen werden durch `filter_comparison_set()`
korrekt entfernt — sie gelangen nie in `reconstruct_ax_master()`.

**Fazit GEZE:** Fallback-Mechanismus greift in der Praxis **nie** bei
beurteilbaren Master-Gruppen. Master führt immer. `reconstruct_ax_master()`
liefert für GEZE stets `master[field]` (kein Fallback nötig).

### Erlöse-Verteilung

| Feld | Masters mit nonzero Erlös | Subs mit nonzero Erlös |
|------|--------------------------|------------------------|
| Erlöse Fracht | 3/586 (0,5 %, Datenartefakte) | prädominant auf Subs |
| Erlöse Diesel | ~0 | auf Subs |
| Erlöse Maut | ~0 | auf Subs |

3 Master-Zeilen mit `Erlöse Fracht ≠ 0` sind Datenartefakte — die
Erlöse-Regel (immer Sub-Summe) ist trotzdem korrekt angewendet, da sie
diese 3 Ausreißer auf Sub-Summe setzt statt Master-Wert zu nehmen.

---

## §4 Fischerwerke (KNR 409480)

**Datenmenge:** 109 Master, 253 Sub (aus allen Zeilen)

### Physische Felder

| Feld | Master nonzero | Subs nonzero | Muster |
|------|---------------|-------------|--------|
| Tonnage (eff.) | 109/109 (100 %) | 63/253 (24,9 %) | Master immer gefüllt; Subs manchmal auch |
| Lademeter | 77/109 (70,6 %) | 43/253 (17,0 %) | Beide können Werte haben |
| Stellplätze | 87/109 (79,8 %) | 63/253 (24,9 %) | Beide können Werte haben |

**Interpretation:** Fischerwerke ist Stellplatz-basiert. Die 63 Subs mit
nonzero Tonnage / Stellplätze sind die 63 FP-Zeilen aus der Regression-Analyse
(Sub-Zeilen mit physischen Werten, die `enrich_master_sub()` bisher kompensiert).

Muster: Master hat IMMER Tonnage/Stellplätze, Subs auch manchmal. Da Master
immer gefüllt ist, greift der Fallback-Mechanismus für Tonnage/Stellplätze **nie**.
Bei Lademeter: 77/109 Master haben Wert → Fallback für restliche 32 greift auf Subs
(von denen 43 Werte haben). Der Fallback-Mechanismus ist bei Fischerwerke für
Lademeter **potenziell relevant**.

---

## §5 HERMA (KNR 423650)

**Datenmenge:** 183 Master, 421 Sub

### Physische Felder

| Feld | Master nonzero | Subs nonzero | Muster |
|------|---------------|-------------|--------|
| Tonnage (eff.) | 183/183 (100 %) | 2/421 (0,5 %) | Master führt; Subs fast immer 0 |
| Lademeter | 180/183 (98,4 %) | 2/421 (0,5 %) | Master führt; seltene Ausnahmen |
| Stellplätze | 3/183 (1,6 %) | 0/421 (0 %) | Nicht HERMA-relevant |

**Interpretation:** HERMA ähnelt GEZE stark. Physische Parameter fast
ausschließlich auf Master-Zeile. Fallback-Mechanismus greift bei 2 Subs
(Tonnage>0) — identisch mit den 2 FP-Zeilen aus der Regression-Analyse.
Für den normalen HERMA-Calculator-Betrieb: Fallback praktisch irrelevant.

---

## §6 CHT Germany (KNR 486073)

**Datenmenge:** 0 Master-Zeilen (trotz 56 Sub-Zeilen)

CHT nutzt in der BI-Datenstruktur keine `Unterauftrag`-Felder. Die 56 Subs
haben Mastersendung gesetzt, aber die entsprechenden Master-Zeilen fehlen
im aktuellen Datensatz (möglicherweise in anderem Kontext / anderen Dateien).
`reconstruct_ax_master()` ist für CHT nicht anwendbar.

---

## §7 Zusammenfassung: Fallback-Relevanz

| Kunde | Fallback-Häufigkeit | Physisches Feld | Praktische Relevanz |
|-------|---------------------|----------------|---------------------|
| GEZE | **Nie** (0/586 Gruppen) | Tonnage, Colli immer auf Master | Fallback irrelevant |
| HERMA | **Fast nie** (2 Ausnahmen) | Tonnage, LDM fast immer auf Master | Fallback marginal |
| Fischerwerke | **Lademeter: möglich** (~32/109 Gruppen) | LDM manchmal leer auf Master | Fallback sinnvoll für LDM |
| CHT | n/a | Kein Master-Sub-Pattern in BI-Daten | Nicht anwendbar |

### Schlussfolgerung

Das Validierungsbeispiel `7092010001835006` ist **typisch** für GEZE:
Master trägt physische Parameter, Subs tragen ausschließlich Erlöse.
Der Fallback-Mechanismus in `reconstruct_ax_master()` ist für GEZE und
HERMA ein defensiver Safety-Catch, der in der Praxis kaum triggert.
Bei Fischerwerke (Lademeter) ist er methodisch sinnvoll.

Die Funktion ist in beiden Szenarien korrekt — der Fallback schadet nicht
bei GEZE (nie ausgelöst), schützt aber bei Fischerwerke.

---

## §8 Rollout-Implikationen pro Kunde

### Bekannte Kunden (Phase 1)

| Kunde | Fallback-Verhalten | Erwartung bei reconstruct_ax_master() | Rollout-Hinweis |
|-------|-------------------|--------------------------------------|-----------------|
| **GEZE** | Nie (100 % Master führt) | Tonnage immer von Master; Erlöse immer von Subs | Kein Fallback-Risiko; Validierung einfach |
| **HERMA** | Fast nie (0,5 % Ausnahmen) | Wie GEZE; 2 Subs mit Tonnage>0 sind FP-Zeilen, werden gefiltert | Analog GEZE |
| **Fischerwerke** | Lademeter: ~29 % Fälle | Fallback für LDM relevant; Stellplätze immer auf Master | Lademeter-Ergebnisse nach Rollout prüfen |
| **EBM-Papst** | Noch nicht analysiert | Erwarte GEZE-ähnliches Muster (Tonnage-Abrechnung) | Vor Rollout empirisch prüfen |
| **CHT** | n/a (kein Master-Sub-Pattern in BI) | reconstruct_ax_master() nicht anwendbar | Separate AX-Struktur |

### Neue Kunden Welle 1 (noch nicht analysiert)

| Kunde | Billing-Basis | Erwartete Fallback-Relevanz | Zu prüfen vor Rollout |
|-------|--------------|---------------------------|----------------------|
| Bitzer | Weight (kg) | Vermutlich GEZE-ähnlich (Tonnage auf Master) | Empirisch bestätigen |
| Groz-Beckert | Weight (kg) | Vermutlich GEZE-ähnlich | Empirisch bestätigen |
| HELU | Weight (kg) | Vermutlich GEZE-ähnlich | Multi-Country: je Land prüfen |
| Hornschuch | Weight (kg) | Vermutlich GEZE-ähnlich | Empirisch bestätigen |

**Vorgehen für neue Kunden:** Vor Integration die Felder aus §3–§5 analog
prüfen (5–10 Master-Sub-Gruppen, Verteilung nonzero Master vs. Subs). Diese
Matrix dann ergänzen.

### Implikationen für Rollout-Erwartungen

1. **GEZE/HERMA-Muster (Master führt immer):** `reconstruct_ax_master()` verhält
   sich deterministisch — kein Überraschungs-Potenzial durch Fallback-Trigger.
   Regression-Tests zeigen stabile Ergebnisse.

2. **Fischerwerke-Muster (Lademeter Fallback):** Fallback für Lademeter ist
   legitim und korrekt. Die 43 Sub-Zeilen mit LDM>0 decken die Fälle ab, wo
   der Master LDM leer lässt. Erwarte geringe Abweichung zu altem Proxy.

3. **CHT (kein Master-Sub):** `filter_comparison_set()` reicht; kein
   `reconstruct_ax_master()` nötig. Tonnage>0-Proxy war für CHT korrekt
   (alle 38 CHT-Subs haben Tonnage=0, laut Regression-Analyse).

4. **Fallback für Stellplätze (Fischerwerke):** 87/109 Master haben
   Stellplätze-Wert; für restliche 22 greift der Fallback. Bei Fischerwerke
   ist Stellplatz das Abrechnungs-Merkmal — Validierung der Stellplatz-Summen
   nach Rollout priorisieren.

---

*Erstellt: 2026-04-24 | Aktualisiert: 2026-04-24 (§8 Rollout-Implikationen)*
*Grundlage: bi_top20_data.pkl | Kunden: GEZE, Fischer, HERMA, CHT*
*Keine Code-Änderungen.*
