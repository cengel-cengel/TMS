# AUDIT_METHODOLOGY.md

**Zweck:** Verbindliche Methodik für das TMS-Billing-Audit nach Dinas→AX Migration (27.09.2025). Jeder Chat und jeder Claude-Code-Run startet mit Lesen dieses Files, bevor ein Etappen-Command ausgeführt wird.

**Pflegezyklus:** Nach jedem Kunden-Audit auf Aktualität prüfen. Neue Muster, Retroaktiv-Punkte und Edge Cases hier eintragen, nicht in Chat-Handovers.

---

## 1. Phasen-Konzept

Die Migration 27.09.2025 teilt jede Sendung in eine von drei Phasen. Die Phase bestimmt, gegen welche Referenz die Abrechnung geprüft wird.

| Phase | Zeitraum | Referenz |
|---|---|---|
| `pre_dlv` | Leistungsdatum < DLV-Gültigkeitsbeginn | Dinas-Parquet (falls vorhanden) |
| `in_dlv_2025` | DLV-Gültigkeit 2025 aktiv | DLV-Datei 2025 |
| `in_dlv_2026` | Leistungsdatum ≥ 01.03.2026 | DLV-Datei 2026 |
| `post_dlv` | DLV-Gültigkeit abgelaufen, kein Folge-DLV | Fallback: jüngste DLV-Version, geloggt |

**DLV-Gültigkeitsbeginn:** Idealerweise explizites Feld im DLV. Wenn nicht dokumentiert, Dateiname als Proxy (z.B. `20251010` → dlv_start=10.10.2025). Proxy-Nutzung in jedem Report offenlegen.

**Grenze 01.03.2026:** Harte Grenze. Februar-Sendungen dürfen nicht versehentlich gegen 2026er DLV gerechnet werden, sonst entstehen Fake-Unterfakturierungen.

**Varianten-Test (pre_dlv-Sensitivität):** Bei Kunden mit wenigen pre_dlv-Zeilen parallel mit zwei dlv_start-Annahmen rechnen (z.B. Dateiname vs. Migrationsdatum). Wenn Delta identisch → pre_dlv-Zeilen fallen nicht ins Gewicht, Entscheidung kann offen bleiben. Wenn Delta divergiert → dlv_start muss vor Report geklärt werden.

---

## 2. Floater-Detection (Pflicht vor Delta-Interpretation)

**Historischer Kontext:** Die 9a.1.b-Altzahl für EBM war –18.517 EUR Unterfakturierung. Nach korrekter Floater-Bereinigung: +20.866 EUR (Überfakturierung bzw. neutral). Ursache: Der Betrag enthält systematisch einen Diesel-Floater-Aufschlag auf den Tarif, der in der Altlogik als Unterfakturierung fehlinterpretiert wurde.

**Konsequenz:** Floater-Check kommt VOR jedem Delta-Statement. Ausnahmslos.

**Formel:**
```
Betrag = Tariff × (1 + Floater%) + Toll
```

**Berechnung pro Zeile:**
```python
floater_pct = (betrag - toll) / tariff - 1
expected    = tariff * (1 + floater_pct) + toll
delta       = betrag - expected
```

**Plausibilitäts-Range:** Floater 5–12 % entspricht aktuellem Diesel-Preisband (Surcharges-Sheet). Werte außerhalb → Formel greift nicht, Lane manuell inspizieren.

**Referenz-Validierung:** Die Floater-Höhe pro Kunde ist mit dem aktuellen Diesel-Preisband aus dem Surcharges-Sheet abzugleichen. Abweichung ist Klärungsfrage, nicht Rechnungsfehler.

**Bekanntes Kunden-Profil:**
- EBM IE: Floater mean 9,06 %, σ=0,003, Range 8,70–9,69 %
- Fischerwerke: KEIN Floater, stattdessen Muster-A (siehe §3)
- Sika: offen, retroaktiv zu prüfen (→ §7)

---

## 3. Muster-A vs Muster-B

Nach Floater-Bereinigung werden Deltas klassifiziert.

### Muster-A: Systematischer Aufschlag
Fixer prozentualer Aufschlag, der lane-übergreifend und NICHT im DLV dokumentiert ist. Indiz: **exakt konstanter `floater_pct`** (nicht nur ungefähre Ratio) über mehrere Lanes, Phasen oder Monate.

**Wichtig — Erkennung auf `floater_pct`-Basis, nicht auf Ratio `betrag/(tariff+toll)`:** Der reine Ratio-Check klassifiziert variable Diesel-Floater als Muster-A fehl. Beispiel EBM: PL-März-Zeilen haben `floater_pct=8,1 %` — das ist ein normaler monatlicher Diesel-Floater, kein Muster-A. Erst wenn `floater_pct` über viele Zeilen auf denselben exakten Wert (z.B. 0,07000 ± 0,00005) einrastet, liegt Muster-A vor.

**Bestätigte Kunden-Profile:**
- Fischerwerke: `floater_pct = 0,07000` ab März 2026, 62 Zeilen, pending ERKA-Indexschreiben-Klärung
- EBM: `floater_pct = 0,07000` Januar 2026, 50 Zeilen, Lanes IE/PL/EE/SK/HR (9a.4.2)

**Meta-Erkenntnis:** Muster-A ist mit zwei bestätigten Kunden systemübergreifend, nicht kunden-spezifisch. Unterschiedliche Aktivierungsmonate pro Kunde (Fischerwerke März, EBM Januar) deuten auf einen gemeinsamen Mechanismus mit kundenabhängigem Einführungstermin hin.

**Detektions-Threshold:** ≥3 Zeilen pro Lane mit `floater_pct` auf einem gemeinsamen exakten Wert (Binning 0,00005). Bei Treffer → Flag `muster_a_suspected`, Deep-Dive vor Aggregation.

**Abgrenzung zu Floater:** Diesel-Floater variiert (σ > 0,001) und ist im Surcharges-Sheet dokumentiert. Muster-A hat σ ≈ 0 über die betroffenen Zeilen und ist undokumentiert.

### Muster-B: Echte Unterfakturierung
Nach Floater-Bereinigung: `delta < -10 EUR`. Das sind die tatsächlichen Findings für den Retro-Bill-Prozess.

**Ausschluss:** DLV-Lücken-Zeilen (kein Referenztarif) werden als `unbeurteilbar` klassifiziert, nicht als Muster-B.

---

## 4. Cluster-Anforderung (ursprüngliche User-Spec)

Die ursprüngliche Anforderung lautet: Pro Kunde und unterfakturierter Lane je 5 AX-POST-Aufträge gegen 5 Dinas-PRE-Aufträge gegenüberstellen. Gruppierung nach:
- Sender-PLZ (2-stellig)
- Empfänger-PLZ (2-stellig)
- Tarifgruppe gemäß DLV
- Sendungs-/Leistungsdatum → passende DLV-Version

Bei mehr als 5 AX-POST-Aufträgen im Cluster: die 5 mit größter Frachterlös-Abweichung. Bei keiner Unterfakturierung im Cluster: Cluster nicht darstellen. Nebenkosten beidseitig aufgeschlüsselt (Frachterlös + alle auf Rechnung ausgewiesenen Nebenkosten).

**DLV-Fallback:** Wenn weder 2025- noch 2026-DLV für Datum passt, aktuellste verfügbare Datei, explizit geloggt.

**Anwendbarkeit:** NUR bei Kunden mit Dinas-PRE-Daten. In der aktuellen Kundenlage ist das ausschließlich **Sika**. Für Fischerwerke, EBM und alle Post-Umstellungs-only-Kunden ist das Cluster-Format strukturell nicht anwendbar — dort gilt der Phasen-Report als primäres Format.

**Umsetzungs-Status:** Cluster-Format in 8i-Sika und 9a.3.3-Fischerwerke NICHT als Output realisiert. Offener Arbeitsblock für 9a.6 Sika-Re-Run.

---

## 5. DLV-Fallback-Logging

Jede Zeile im Output muss die verwendete DLV-Version nachvollziehbar machen.

**Pflichtfelder:**
| Feld | Werte |
|---|---|
| `dlv_version_used` | `2025-10-10` / `2026-03-01` / `latest_fallback` |
| `dlv_fallback_reason` | `date_match` / `fallback_latest` / `no_dlv` |
| `tariff_source` | `exact` / `no_match` → Zeile wird `no_dlv` |

**Audit-Regel:** Bei Report-Erstellung Anteil `fallback_latest` und `no_dlv` separat ausweisen. Wenn `no_dlv` > 10 % der Zeilen → DLV-Stammdaten-Lücke, muss vor Aggregation geschlossen werden.

### Daten-Fallbacks für fehlende Abrstrecken-Felder

**Stpl-NaN-Fallback (ab 9a.4.2):** Wenn `Abrechnungsstellplätze` NaN ist, aus LDM herleiten:
```
stpl_fallback = ceil(LDM / 0.4)
```
Begründung: 1 Stellplatz ≈ 0,4 Lademeter. Der Ceil stellt sicher, dass bei Bruchwerten nicht unter-gerundet wird.

**Pflichtfeld für betroffene Zeilen:**
| Feld | Werte |
|---|---|
| `stpl_source` | `direct` / `ldm_fallback` / `no_data` |

**Audit-Regel:** Anteil `ldm_fallback` im Report ausweisen. Wenn `ldm_fallback` > 30 % der Zeilen → Datenqualität Abrstrecken-Export prüfen, bevor Findings aggregiert werden.

---

## 6. Sanity-Check-Gates

Vor jedem Delta-Statement müssen diese Checks durchlaufen sein. Hartes STOP bei Fehlschlag, keine automatische Fortsetzung.

**Gate 1 — Route-Match-Quote:** Anteil der Abrstrecken-Zeilen, die gegen eine DLV-Route gemappt wurden. Unter 85 % → PLZ-/Ort-Mapping ist unvollständig, Parser-Bug wahrscheinlich.

**Gate 2 — Floater-Range-Plausibilität:** Nach erster Lane-Iteration Floater-Range ausgeben. Außerhalb 5–12 % → Formel-Annahme greift nicht, manuelle Inspektion vor Rollout.

**Gate 3 — Exact-Match-Quote:** 0 Exact-Matches gegen `tariff+toll` ist nur dann unkritisch, wenn Floater im Spiel ist. 0 Exact-Matches ohne erkennbaren Floater → Logik-Fehler.

**Gate 4 — Phasen-Verteilung Sanity:** Wenn >95 % einer Phase → Kundenprofil prüfen. Post-Umstellungs-only-Kunden haben 0 pre_dlv, aber in_dlv/post_dlv sollten realistisch verteilt sein.

---

## 7. Retroaktiv-Liste

Findings, die nachträgliche Re-Runs bereits abgeschlossener Audits erfordern. Bei jedem Re-Run alle Punkte anwenden.

**Für 9a.6 Sika-Re-Run:**
- `parse_dlv_auto` auf GEZE-CH-Struktur testen
- Kern- vs. kundengerichtete DLV unterscheiden
- Phasen-Logik auf 8i-Gap-Zahl anwenden (war ohne Phasen-Konzept gerechnet)
- Matrix-DLV-Support prüfen (Tariffs × Palletspaces in Spalten) falls relevant
- **Floater-Detektion vor Delta-Interpretation** (neu aus 9a.4.1): Falls Sika ebenfalls systematischen Aufschlag im Betrag hat, sind bestehende 8i-Findings potenziell verzerrt und müssen analog zur EBM-Altzahl-Revision neu gerechnet werden
- Cluster-Format (§4) explizit als Output realisieren — in 8i nicht vorhanden. Bei Kunden ohne Dinas-PRE-Overlap als N/A dokumentieren, nicht stillschweigend weglassen

**Für 9a.3.3 Fischerwerke:**
- Muster-A ERKA-Indexschreiben-Klärung pending
- GR/GB/IT-Verona-Lanes unbeurteilbar wegen DLV-Lücken, DLV-Nachforderung

---

## 8. Report-Format-Regeln

Der Report-Stil richtet sich nach dem Findings-Profil, nicht nach Kunden-Größe.

**Kurz-Bericht** (Headline + Kontext, keine Detail-Tabellen):
- 0 Muster-A UND 0 Muster-B über alle Lanes
- Altzahl-Revision als Headline (falls Altzahl vorhanden war)
- Floater-Dokumentation, DLV-Lücken-Liste
- Beispiel: 9a.4 EBM nach 9a.4.1-Ergebnissen

**Fischerwerke-Stil** (Detail-Tabellen pro Lane):
- Muster-A oder Muster-B auf mindestens einer Lane
- Betroffene Lanes mit Zeilen-Detail, restliche Lanes kurz
- Beispiel: 9a.3.3 Fischerwerke

**Cluster-Stil** (5-vs-5-Struktur, §4):
- Kunde mit Dinas-PRE-Overlap, Lanes mit Muster-B
- Beispiel: 9a.6 Sika (pending)

---

## 9. Handover-Protocol

Jeder neue Chat startet mit dem gleichen Gerüst:

```
Kontext: TMS-Billing-Audit Dinas→AX, Branch: <branch>
Zuerst: Lies AUDIT_METHODOLOGY.md.

Etappe: <9a.X.Y Name>
Letzter Commit: <hash>
Offene Punkte: <kurze Liste>
Retroaktiv-Liste siehe §7 der Methodologie.

Command folgt.
```

**Kein Methodik-Reißbrett im Handover.** Wenn der Handover-Prompt Muster-A/B/Cluster/Floater neu erklärt, ist das ein Signal, dass dieses File aktualisiert gehört.

**Kernzahlen des letzten Etappen-Ergebnisses** als Screenshots oder Klartext anhängen — nur die Zahlen, nicht die Interpretation.

---

## Changelog

| Datum | Etappe | Änderung |
|---|---|---|
| 2026-04-20 | 9a.4.1 | Initial draft. Floater-Detection als Pflicht-Schritt aufgenommen, Muster-A/B-Abgrenzung präzisiert, Cluster-Scope auf Sika eingegrenzt, Sanity-Gates definiert. |
| 2026-04-20 | 9a.4.2 | §3 Muster-A-Detektion von Ratio- auf `floater_pct`-Basis umgestellt (Ratio klassifiziert variable Diesel-Floater fehl). EBM als zweiter Muster-A-Kunde bestätigt (50 Zeilen Jan 2026, 5 Lanes). §5 um Stpl-NaN-Fallback `ceil(LDM/0.4)` erweitert mit Pflichtfeld `stpl_source`. |
