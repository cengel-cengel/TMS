# HERMA GmbH — Tarif-Audit Cluster-Report v1.9.6

**Erstellt:** 2026-04-27  
**Ladedatum-Bereich:** 2025-04-01 — 2026-03-30  
**Methodik-Version:** v1.9.6  
**KNR:** 423650  
**Analyse-Skript:** `src/build_herma_report.py`  
**Vorgänger-Report:** `docs/v1_9_4_herma_cluster_report.md`

---

## 1. Executive Summary

### Reconciliation v1.0 → v1.9.4 → v1.9.6

| Version | Net Δ (EUR) | Δ gg. Vorgänger | Methodische Änderung |
|---------|------------:|----------------:|----------------------|
| v1.0 Schätzung | −167.000 | — | Vorläufig, ohne DLV-Jahr-Dispatch, ohne Etiketten-Trennung |
| v1.9.4 | −142.996 | +24.004 | Gate-A+B: korrekte 2025/2026-DLV-Zuweisung |
| **v1.9.6** | **−16.374** | **+126.622** | §2f-Cluster-Aggregation: DLV(Σ bw) statt Σ DLV(bw_i) |

**Hauptbefund:** Der im v1.9.4-Report ausgewiesene Weight-Driver-M2*-Block von −142.996 EUR
enthielt einen Aggregations-Artefakt von **~126.622 EUR** (89 %). Nach Korrektur beträgt der
verbleibende Netto-Schaden **−16.374 EUR**.

### Pool-Übersicht v1.9.6

| M-Klasse | Rows | Anteil | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) |
|----------|-----:|-------:|--------------:|------------:|--------:|
| M1 \|fp\| ≤ 5 % | 2.842 | 78,0 % | 1.785.091 | 1.782.287 | +2.804 |
| M2\* fp < −5 % | 384 | 10,5 % | 417.370 | 485.129 | −67.758 |
| M\_over fp > +5 % | 416 | 11,4 % | 226.275 | 177.694 | +48.581 |
| **Σ beurteilbar** | **3.642** | | **2.428.736** | **2.445.110** | **−16.374** |
| DLV-Lücke (nicht beurteilbar) | 139 | — | — | — | — |
| **Pool gesamt** | **3.781** | | | | |

*Pool-Ursprung: 4.770 AX-Rows → 3.781 nach ZGI-Cluster-Aggregation (635 Multi-Row-Cluster zusammengefasst, 3.146 Singletons unverändert).*

---

## 2. Methodik-Änderung v1.9.6: ZGI-Cluster-Aggregation (§2f)

### Ausgangsproblem

Die v1.9.4-Pipeline berechnete den DLV-Soll **pro Einzelzeile**:

```
DLV-Soll(v1.9.4) = Σ_i  DLV(billing_weight_i)
```

Bei degressivem Tarif gilt jedoch `DLV(Σ bw_i) < Σ DLV(bw_i)`, da höhere Gewichte
günstigere Tarifstufen erreichen. Werden mehrere AX-Zeilen über dasselbe
"Zusammengefasst in"-Cluster (ZGI) gemeinsam abgerechnet, muss der DLV-Soll auf
dem **Cluster-Gesamtgewicht** basieren — nicht auf Einzelgewichten.

### Korrektur

```
DLV-Soll(v1.9.6) = Σ_cluster  DLV(Σ billing_weight innerhalb Cluster)
```

Implementiert in `src/tms/billing/aggregation.py` → `aggregate_ax_per_cluster()` (v1.9.6).

### Quantifizierung des Artefakts

| Kennzahl | Wert |
|----------|-----:|
| Multi-Row-Cluster (≥2 AX-Rows) | 635 |
| Singleton-Cluster | 3.146 |
| DLV-Überschätzung gesamt | +123.295 EUR |
| davon auf Weight-Driver M2* (v1.9.4) | +71.499 EUR (57 %) |
| Tatsächliche Pool-Schrumpfung 4770 → 3781 | −989 Rows |

---

## 3. Detailbefunde

### 3.1 M2* Weight-Driver-Analyse

| Kennzahl | v1.9.4 | v1.9.6 | Δ |
|----------|-------:|-------:|--:|
| M2*-Rows | 1.584 | 384 | −1.200 |
| Σ M2* Δ (EUR) | −193.422 | −67.758 | +125.664 |
| M1-Rows | 2.581 | 2.842 | +261 |
| M_over-Rows | 467 | 416 | −51 |
| Net Δ (EUR) | −142.996 | −16.374 | +126.622 |

Die starke Reduktion der M2*-Rows (−1.200) erklärt sich daraus, dass nach Cluster-Aggregation
viele Einzelzeilen mit kleinen Gewichten — die degressiv überhöhte DLV-Solls generierten —
in Cluster-Zeilen mit größeren Gesamtgewichten und korrekt niedrigeren Tarifstufen aufgehen.

### 3.2 DLV-Lücke (nicht beurteilbar)

139 Pool-Rows konnten keinem DLV-Eintrag zugeordnet werden (unbekannte Ziel-PLZ oder
Tarif-Datum außerhalb verfügbarer DLV-Versionen). Diese Rows sind in den M-Klassen
nicht enthalten und werden als Lücke separat ausgewiesen.

### 3.3 Verbleibende M2*-Befunde (−67.758 EUR)

| Sub-Treiber | Rows | Σ Δ (EUR) | Anteil |
|-------------|-----:|----------:|-------:|
| LDM-basiert (billing_det="ldm") | ca. 230 | ca. −45.000 | 66 % |
| Tonnage-basiert (billing_det="ton") | ca. 154 | ca. −22.758 | 34 % |

*Sub-Treiber-Aufteilung: Schätzung basierend auf billing_det-Verteilung im Pool.*

Die LDM-Lücke ist der dominante verbleibende Treiber: DLV-Tarif für Lademeter-bepreiste
Sendungen liegt systematisch über den abgerechneten AX-Erlösen. Dies deckt sich mit dem
v1.9.4-Befund (Gate-C Lademeter-Sonderpreis nicht vollständig in DLV abgebildet).

### 3.4 M_over-Befunde (+48.581 EUR)

416 Rows, bei denen AX-Erlöse den DLV-Soll übersteigen. Dies kann auf:
- Zuschläge (Diesel-Floater, Maut-Korrekturen) die separat im AX-EF enthalten sind
- Manuelle Preiserhöhungen oberhalb Tarif
- Fehlzuordnungen im DLV (zu niedrige Tarifstufe)

---

## 4. Cross-Customer-Relevanz (§2f Re-Run-Bedarf)

Die Cluster-Aggregations-Korrektur betrifft alle Kunden mit degressivem Tarif und
Multi-Row-ZGI-Clustern. Folgende Kunden benötigen Re-Run:

| Kunde | KNR | Geschätzte Artefakt-Größe | Re-Run-Status |
|-------|-----|-------------------------:|---------------|
| GEZE GmbH | 406035 | ~52.000 EUR | Offen |
| Fischerwerke GmbH | 409480 | ~52.000 EUR | Offen |
| CHT Germany | 486073 | ~6.000 EUR | Offen (minor) |
| EBM-Papst | — | 0 EUR | Nicht betroffen (Flat-Tarif) |

*Schätzungen basieren auf anteiliger Hochrechnung der HERMA-Cluster-Dichte.*

---

## 5. Fazit

Der verbleibende Netto-Schaden nach vollständiger Methodik-Korrektur beträgt **−16.374 EUR**
für den Zeitraum 2025-04-01 bis 2026-03-30.

Der deutlich größere v1.9.4-Wert von −142.996 EUR war zu **89 %** ein Messartefakt durch
positions-weise DLV-Berechnung bei degressivem Tarif. Die Cluster-Aggregation gemäß §2f
korrigiert diesen systematischen Bias.

**Empfehlung:** Re-Run für GEZE und Fischerwerke vor Übergabe an Controlling.

---

*Generiert mit `aggregate_ax_per_cluster()` (src/tms/billing/aggregation.py, v1.9.6)*  
*Methodik-Referenz: docs/AUDIT_METHODOLOGY.md §2f*
