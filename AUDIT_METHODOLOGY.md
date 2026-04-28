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
| 2026-04-28 | Welle-2 | **v1.9.7** — Konsolidierung Groz-Beckert, HELU, Hornschuch. §10 Pre-Flight-Skill-Präzedenz-Mapping. §11 ZGI-Cluster-Aggregation als Pipeline-Standard. §12 Calculator-Bug-Klassen (8 Klassen). §13 Klassifikations-Disziplin. §14 Reporting-Standards v1.9.6+. §15 Sika-Spezifika-Pointer. SKILL.md P17–P19 hinzugefügt. |

---

## 10. Pre-Flight-Skill — Welle-2-Präzedenz-Mapping

Vollständige Pitfall-Beschreibungen in `skills/customer-preflight/SKILL.md §8`.
Nachfolgende Tabelle ordnet jeden Pitfall dem auslösenden Kunden und dem
quantifizierten Schaden (vor Fix) zu.

| Pitfall | Kurzbeschreibung | Präzedenz-Kunde | Schaden vor Fix |
|---|---|---|---|
| P1 | billing_axis im Handover falsch | EBM (stp statt tonnage) | qualitativ (falsche Cluster) |
| P2 | DLV-Sheet-Name abweichend | EBM PT/ES (`DE-EU` statt `Tariffs_DE_EU`) | Coverage 0/5 Lanes |
| P3 | Sika SSC KNR-Normalisierungsbug | Sika (KNR 511241 + Variante) | ~772 TEUR Scheindefizit |
| P4 | Cross-System-Schatten-Einträge (8-stellig) | EBM (62 % DLV-Lücke = Rauschen) | Coverage-Verzerrung |
| P5 | Lane-Discovery: Handover unvollständig | EBM (SI/DE/GB/ES/PT/RS fehlend) | Scope-Unterschätzung |
| P6 | LDM-Fallback fehlt bei Stellplatz=0 | EBM (171 Sendungen, 133 TEUR) | 133 TEUR unbeurteilbar |
| P7 | DLV-Cap-Risiko (Stp-Obergrenze) | EBM (Cap 33 Stp) | stille Fehlklassifikation |
| P8 | Pre-Flight Pool-Schätzung vs. Pipeline | EBM (E3 < 20 % Diskrepanz) | Navigations-Heuristik |
| P9 | Sub-Master Erlöse=0 (administratives Muster) | Fischerwerke (49 Zeilen) | 0 EUR, kein Impact |
| P10 | Return-/Import-Route-Files kontaminieren DLV | Fischerwerke (4 Dateien) | −97 TEUR Scheindefizit |
| P11 | Coverage-Test: kein Sample, immer Full-Run | HERMA GB (10 fehlende UK Area-Codes) | 93 Rows / 62 TEUR OOS |
| P12 | Pricing-Mode-Wechsel zwischen DLV-Versionen | HERMA Gate B (2025→2026) | 2.351 Sendungen falsch |
| P13 | Versender-Name als Routing-Key (Sparten-DLV) | HERMA (Haftmaterial vs. Etiketten) | −560 EUR/Sendung ES |
| P14 | DLV `durch neue Tarife ersetzt` kontaminiert | HERMA Gate A (veraltete NT-Datei) | Schein-Δ bis −560 EUR |
| P15 | `Upload/`-Ordner = aktive Erweiterung, kein Archiv | Bitzer IT (24t FTL-Band) | FTL-Sendungen falsch |
| P16 | Upload-DLV Zonen-Map ≠ Standard-DLV | Bitzer IT Zone 4 (PLZ 32010 etc.) | −21.511 EUR Artefakt |
| P17 | Zone-Lookup-Format-Mismatch (Key-Typ / Stelligkeit) | HELU H1+H2 + Hornschuch G3 | s. §12 |
| P18 | Additiver Zuschlag wird als Ersatz-Tarif behandelt | Hornschuch G2 Castorama (318 Rows) | fp = +∞ (Artefakt) |
| P19 | FTL-Flat-Rate vs. per-kg-Extrapolation (M2-Artefakt) | Hornschuch M2 (7 Rows, −860 EUR) | −860 EUR Schein-M2 |

**Anwendungsregel:** Diagnosen D1–D4 des Pre-Flight-Skills sind für jeden neuen
Kunden vor Step 2 zu durchlaufen. Ergebnis: schriftlicher D1–D4-Output-Block
im Chat als Nachweis. STOP wenn Gate-Bedingung nicht erfüllt.


---

## 11. ZGI-Cluster-Aggregation (v1.9.6 Pipeline-Standard)

### Hintergrund

AX bündelt mehrere physische Sendungen in einer Mastersendung ("zusammengefasst in",
ZGI). Die Erlöse Fracht liegen auf dem Master, nicht auf den Sub-Zeilen. Wird der
Pool auf Positions-Ebene verglichen ohne Sub-Zeilen zu konsolidieren, entsteht ein
systematischer Über-Vergleich: dieselbe DLV-Kalkulation wird mehrfach addiert.

**HERMA-Präzedenz:** Vor Aggregation: Net Δ −142.996 EUR (Weight-Driver-Artefakt).
Nach ZGI-Aggregation: Net Δ −16.374 EUR. Differenz = 126.622 EUR reiner Aggregations-
Artefakt. (9 Cluster mit Sub-Rows Tonnage>0.)

### Pipeline-Implementierung

```python
def aggregate_ax_per_cluster(df: pd.DataFrame) -> pd.DataFrame:
    """
    Konsolidiert AX-Sub-Rows auf Master-Ebene.
    Sub-Row = has_ms=True AND has_ua=False (Mastersendung gesetzt, kein Unterauftrag).
    Master-Row = has_ms=False AND has_ua=True ODER is_standalone.
    Erlöse Fracht auf Sub-Rows = 0 (oder marginal). Tonnage kann >0 sein.

    Rückgabe: DataFrame ohne Sub-Rows (Tonnage des Masters bleibt unverändert).
    """
    is_sub = df['has_ms'] & ~df['has_ua']
    return df[~is_sub].copy()
```

**Hinweis:** In bi_top20_data.pkl fehlen die ZGI-Spalten (`zusammengefasst in`).
Daher ist der ZGI-Aggregations-Ansatz für alle aktuellen Kunden ein **No-Op** —
die Sub-Row-Erkennung läuft über has_ms/has_ua, nicht über ZGI-ID-Matching.
ZGI-Bias = 0 EUR für alle Welle-2-Kunden bestätigt.

### Wann anwendbar

| Bedingung | Behandlung |
|---|---|
| Keine ZGI-Spalten im BI-Export | Tonnage>0-Filter als Proxy (Sub-Rows haben Tonnage=0 bei allen Welle-2-Kunden) |
| ZGI-Spalten vorhanden, Sub-Rows alle Tonnage=0 | is_sub-Filter äquivalent |
| ZGI-Spalten vorhanden, Sub-Rows mit Tonnage>0 | Echter ZGI-Aggregations-Schritt nötig (GEZE: 140 Rows Tonnage>0 latentes Risiko) |

**Entscheidungsregel:** Immer in DIAGNOSE 1 Sub-Row-Tonnage prüfen:
```python
sub_ton_pos = df[df['is_sub']]['Tonnage (eff.)'].gt(0).sum()
```
Wenn `sub_ton_pos > 0`: Aggregations-Schritt vor Step 2 implementieren.
Wenn `sub_ton_pos == 0`: Tonnage>0-Filter reicht.


---

## 12. Calculator-Bug-Klassen (Welle 1 + Welle 2)

Acht identifizierte und gefixte Klassen. Bei jedem neuen Calculator in D2:
Checkliste durchgehen.

### Klasse A — Origin-Match-Bug (Substring statt Origin-Teil)

Calculator matched DE-72-Origin auf vollständigem AFL-String → matcht auch auf
Ziel-Teil von Reverse-Route-Dateien.
**Fix:** AFL-String vor "bis" abschneiden, Match nur auf Origin-Teil.
**Präzedenz:** Fischerwerke P10, Commit 61f229e.

---

### Klasse B — Fehlende Band-Erweiterung (Cap-Sendungen ohne Treffer)

DLV-Jahrestarif endet bei Wert X; Sendungen > X erhalten `None` oder `LookupError`.
Upload-Ordner enthält Erweiterung, wird aber nicht geladen.
**Fix:** Upload-DLV für erweiterte Bänder per Calculator-Konstante explizit laden (P15).
**Präzedenz:** Bitzer IT FTL-Band bis 24 000 kg, Commit 93dc7c1.

---

### Klasse C — Upload-DLV Zonen-Reform ohne shipment_date-Dispatch (P16)

Upload-DLV enthält andere Zonen-Zuordnung als Standard-DLV. Calculator verwendet
Upload universal → falsche Zonen für Sendungen im Standard-Zeitraum.
**Fix:** `shipment_date`-Parameter + Cutoff-Datum + Dispatch auf beide Versionen.
**Präzedenz:** Bitzer IT Zone 4 vs. Zone 2 (PLZ 32010), Commit 93dc7c1.

---

### Klasse D — Pricing-Mode-Wechsel zwischen DLV-Versionen (P12)

DLV-Jahr 2025 und 2026 haben unterschiedliche Pricing-Logik (z. B. andere Spalten-
bedeutungen). Calculator hat kein `shipment_date`-Dispatch.
**Fix:** `_CUTOFF`-Datum + `use_2026`-Flag + separater Sheet-Pfad pro Version.
**Präzedenz:** HERMA Gate B, Commit c26dbe1.

---

### Klasse E — Versender-Name-Routing fehlt (P13)

Kunde hat mehrere Sparten-DLVs, Calculator kennt nur die Hauptsparte.
Nebensparten-Sendungen werden mit falschen Raten bepreist.
**Fix:** Calculator-Parameter für Sparten-DLV + Dispatcher im Build-Script auf
`Versender Name`.
**Präzedenz:** HERMA Etiketten, Commit c26dbe1.

---

### Klasse F — Zone-Lookup-Format-Mismatch (P17, neu Welle 2)

Drei Varianten:
- **F1 (Key-Wert):** zone_fn gibt `"ES-20870"` zurück; DLV-Dict-Key ist `"ES"`.
  Regex in `_parse_vertical` extrahiert nur den Teil vor dem Bindestrich.
  **Fix:** zone_fn an Regex-Extraktion anpassen (`return "ES"`).
  **Präzedenz:** HELU H1 ES-Mendaro, Commit 897a2c6.

- **F2 (Key-Typ):** Dict mit `int`-Spalten-Indices, zone_fn gibt `str` zurück.
  `dict.get("1")` auf int-Key-Dict → immer `None`.
  **Fix:** Dict mit `str(c)`-Keys aufbauen.
  **Präzedenz:** HELU H2 GB rates_by_col, Commit 897a2c6.

- **F3 (PLZ-Stelligkeit):** DLV hat 1-stellige Zonen (1–9), Calculator extrahiert
  2-stelligen PLZ-Prefix → kein Match.
  **Fix:** Länderspezifische Stelligkeit im `_zone()`-Dispatcher berücksichtigen.
  **Präzedenz:** Hornschuch G3 AT (PLZ 4191 → Zone "4" statt "41"), Commit a0a9822.

**Erkennung:** Bei 100 % LookupError auf einer Lane obwohl DLV vorhanden →
zone_fn-Return vs. DLV-Dict-Keys ausgeben.

---

### Klasse G — Additiver Zuschlag als Ersatz-Tarif behandelt (P18, neu Welle 2)

DLV definiert einen per-Sendung-Aufschlag ZUSÄTZLICH zum per-kg-Tarif. Calculator
addiert beide → fp massiv positiv. Oder: Calculator nutzt Aufschlag-DLV als
Haupt-Tarif → fp massiv positiv.
**Korrekte Behandlung:** AX bucht nur den per-kg-Anteil in Erlöse Fracht; Aufschlag
erscheint in separaten Buchungszeilen. → per-kg bleibt Vergleichsbasis, fp = 0,0000
empirisch validieren.
**Erkennung:** Alle Rows einer Empfänger-Gruppe (z. B. Castorama) zeigen fp ≈ 0
nach Herausfiltern der Aufschlag-Zeilen.
**Präzedenz:** Hornschuch G2 Castorama/LM 318 Rows, fp = 0,0000 bestätigt.

---

### Klasse H — FTL-Flat-Rate vs. per-kg-Extrapolation (P19, neu Welle 2)

AX rechnet Großsendungen (13 000–18 000 kg) als Vollfahrzeug-Festpreis (FTL-Flat).
Calculator extrapoliert per-kg-Tarif linear → DLV-Soll deutlich höher als Flat.
→ Systematische M2-Rows bei Großsendungen, die kein Abrechnungsfehler sind.
**Erkennung:** M2-Cluster mit ton > 12 000 kg und konstantem ef (z. B. 1.120 EUR für
alle ~14 000 kg-Sendungen). fp negativ (−8 bis −17 %).
**Behandlung:** Nicht korrigieren. M2 als FTL-Flat-Rate-Artefakt dokumentieren.
**Präzedenz:** Hornschuch M2 (7 Rows, −860 EUR netto, fp = −7 bis −17 %).


---

## 13. Klassifikations-Disziplin

### DLV-Lücke vs. Out-of-Scope vs. Operativer Klärungsbedarf

Drei unterschiedliche Situationen, die klar getrennt dokumentiert werden müssen:

| Kategorie | Definition | Reporting |
|---|---|---|
| **DLV-Lücke** | ERKA-Vertrag deckt Lane ab, aber Calculator findet keinen Tarif (PLZ nicht in DLV, fehlendes Zone-Mapping) | In-Scope, unbeurteilbar. Δ-Aussage nicht möglich. DLV-Nachforderung empfohlen. |
| **Out-of-Scope** | ERKA-Vertrag deckt Lane strukturell nicht ab (z. B. Inlandssendung, Drittland-Sanktion) | Aus Pool herausnehmen. Kein Audit-Statement. |
| **Operativer Klärungsbedarf** | AX rechnet und liefert aus, aber Tarif-Grundlage ist unklar (ERKA führt aus, DLV-Raten leer) | Separat ausweisen. Kein Migrationsschaden-Statement möglich bis zur Klärung. |

**Typische Verwechslung:** Leere ERKA-Raten werden als DLV-Lücke klassifiziert,
obwohl der operative Betrieb normal läuft → das ist Operativer Klärungsbedarf
(möglicherweise separater Carrier-Vertrag außerhalb ERKA-Nominierung).

**Präzedenzfall:**
- DLV-Lücke: HELU EE (1 Row) + LU (1 Row) — Carrier fährt, DLV-Eintrag fehlt
- Out-of-Scope: Hornschuch DE-Inland (116 Rows), UA (2 Rows) — kein intl. Tarif
- Operativer Klärungsbedarf: Hornschuch PL (726 Rows, 204 TEUR) — ERKA führt
  99 PL-Zonen, alle Freight-Raten leer; Hypothese C (separater PL-Vertrag)

---

### Mx-DQ vs. M2 — Datenqualitäts-Issues nicht als Befund klassifizieren

**Mx-DQ-Definition:** Rows, bei denen der Fehler in der BI-Datenqualität liegt
(falsche oder fehlende Tonnage, Duplikat-Zeilen, Cross-System-Schatten), nicht in
der Abrechnung oder dem Tarif.

**Regel:** Mx-DQ-Rows vor der M-Klassifikation aus dem Pool entfernen. Sie sind
weder M1 noch M2 noch M_over — sie sind unbeurteilbar aus Daten-Gründen.

**Abgrenzung:**
- ton=0 bei Standalone (Non-Sub) → Mx-DQ (fehlende Tonnage) → herausfiltern
- ton=0 bei Sub-Row → korrekt (Erlöse auf Master) → herausfiltern als is_sub
- Erlöse=0 bei Sub-Master (has_ms AND has_ua) → P9-Muster → herausfiltern

**Gefahr:** Werden Mx-DQ-Rows als M2 gewertet, entsteht ein künstliches Defizit.


---

## 14. Reporting-Standards v1.9.6+

### Pflicht-Inhalt Executive Summary

Jeder Kunden-Report muss im Executive Summary enthalten:

1. **Headline:** Net Δ absolut + %, Bewertung (Kein Migrationsschaden / Befund)
2. **Pool-Tabelle:** Pool roh → Sub-Rows → OOS → In-Scope → DLV-Lücke → Beurteilbar
3. **M-Klassen:** M1/M2/M_over absolut + Prozent
4. **Σ ef + Σ dlv + Net Δ** (alle auf beurteilbarem Pool)
5. **DLV-Lücke:** Explizit ausgewiesen, auch wenn 0. Wenn > 0: Klärungsempfehlung.

Materielle Befunde (Net Δ > 5 %, M2-Cluster > 1 TEUR) müssen in der Headline
erscheinen, nicht nur im Anhang. Anhang dient der Detail-Dokumentation, nicht der
Erstinformation.

### Fußnoten-Pflicht für Artefakt-Befunde

Wenn Net Δ % methodisch erklärbar ist (Charter-Artefakt, FTL-Flat-Rate, DLV-Extrapolation),
muss die Tabelle eine Fußnote enthalten:

```
¹ Fischerwerke +24,8 %: Charter-Artefakt. Non-Charter-Pool: ~0 %.
² Hornschuch M2: FTL-Flat-Rate-Artefakt. Kein Abrechnungsfehler.
```

Ohne Fußnote wirken hohe Net-Δ-%-Werte wie Migrationsschäden.

### Net-Δ-Hierarchie

| Ebene | Pflicht |
|---|---|
| Kunden-Net-Δ | Immer (Executive Summary) |
| Land-Net-Δ | Immer (Land-Aufschlüsselung) |
| Tarifgruppen-Top-12 | Wenn M2 oder M_over vorhanden |
| Detail-Cluster-Beschreibung | Wenn einzelne Tarifgruppe > 200 EUR Δ |
| Konsolidierte 9-Kunden-Lage | In consolidated_audit_status.md pflegen, NICHT in Kunden-Report |

### Separate Headline für DLV-Lücke

Wenn DLV-Lücke > 10 % des In-Scope-Pools:
```
⚠ DLV-Lücke-Hinweis: X Rows, Y TEUR ohne verifizierbaren Carrier-Tarif.
[Ursache]. Operative Klärung empfohlen.
```
Diese Headline muss VOR der allgemeinen Audit-Aussage erscheinen.

**Präzedenz:** Hornschuch PL-Audit-Hinweis (726 Rows, 204 TEUR, ⚠ prominent in §1).

### Consolidated Audit Status — Pflegepflicht

Nach jedem abgeschlossenen Kunden-Audit:
1. `docs/v1_9_6_consolidated_audit_status.md` aktualisieren
2. Neue Zeile in Haupt-Tabelle (KNR, Calculator-Commit, Cache-Datei, Pool-Zahlen, Net Δ)
3. Fußnote wenn Artefakt
4. Section 2 (Methodik-Anmerkungen) um Kunden-spezifische Notes erweitern
5. Section 6 (Gesamtbild) — Kunden-Zahl und Totale aktualisieren
6. Sika: bleibt BLOCKIERT bis Pipeline-Script gebaut, NICHT in Haupt-Tabelle


---

## 15. Sika-Spezifika (v1.9.7 Vorbereitung)

Vollständige Pre-Flight-Analyse in `docs/sika_preflight_briefing.md`.
Nachfolgend die methodischen Kernpunkte für den Step-2-Pipeline-Bau.

### 3-KNR-Behandlung

| KNR | Entität | BI-Quelle | Status |
|---|---|---|---|
| 491063 | Sika Deutschland GmbH / CH AG | bi_top20_data.pkl | 1.407 Rows ef>0, 1.291 TEUR |
| 511241 | SIKA SUPPLY CENTER AG (SSC) | bi_top20_data.pkl | 415 Rows ef>0, 682 TEUR |
| 527406 | Sika ATM CH / Automotive | bi_cache_sika_527406.pkl | Nicht in bi_top20; separates BI-Loading |

Pipeline-Script: KNR 491063 + 511241 gemeinsam (wie Groz-Beckert multi-KNR-Pattern).
KNR 527406 separater Lauf wegen abweichender BI-Quelle + Stellplatz-NaN-Problem.

### SSC-Identifikation

SSC-Zeilen in bi_top20_data.pkl haben KNR 511241. Identifikation über:
```python
is_ssc = df['Kunden Nr BK'] == 511241
# ALTERNATIV wenn KNR-Normalisierung greift (P3):
is_ssc = df['Von Name'].str.contains('Supply Center', na=False)
```
Beide Methoden gemeinsam prüfen, ob sie auf denselben Pool konvergieren.

### ARA-Mapping (nur DE-Zielland)

Sika DE verwendet ARA-Lieferbedingungen (Ab-Werk). Calculator muss die
ARA→Empfänger-PLZ-Normalisierung nur für DE-Destinations anwenden.
Für alle anderen Destinationsländer: Standard-Empfänger-PLZ verwenden.
**Pitfall:** ARA-Mapping universell anwenden → falsche PLZs für IT/FR/ES.

### 527406 Einschränkungen

- Nicht in bi_top20_data.pkl → `bi_cache_sika_527406.pkl` laden
- `Abrechnungsstellplätze` = NaN für alle Rows (gewichtsbasiert, EUR/100kg)
- Dinas-Vergleich: `dinas_cache_491063.pkl` (geteilt mit KNR 491063)
- Separater DLV: sika_atm.py Calculator (Commit f005e63)
- Stellplatz-Vergleich nicht möglich → DLV-Basis = Gewicht, kein stp_eff

### Retroaktiv-Punkte aus §7 (Update)

Bestehende Punkte in §7 gelten weiterhin. Ergänzung für v1.9.7:
- P17-P19-Checkliste vor Calculator-Build anwenden
- ZGI-Sub-Row-Prüfung (§11): sub_ton_pos in DIAGNOSE 1 erheben
- Klassifikations-Disziplin (§13): DLV-Lücke vs. OOS klar trennen
- Reporting-Standard §14: Pool-Tabelle + Headline-Format einhalten

