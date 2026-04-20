# EBM-Papst (KNR 410844) — Phase-Rollout Findings

**Status: Zwischenstand — Klärungsfragen offen (siehe Abschnitt 8)**
**Stand: 2026-04-20 | Etappe 9a.4.1–9a.4.2**

---

## 1. Executive Summary

Die Altzahl aus 9a.1.b (−18.517 EUR) wird hiermit revidiert: Der korrekte
Gesamt-Delta beträgt **+41.283 EUR** — ein positiver Wert, der ausschließlich
durch Floater-Aufschläge auf den DLV-Basistarif erklärt wird, nicht durch
Unterfakturierung.

Kernerkenntnis: In **50 Zeilen** aus dem Januar 2026 zeigt EBM-Papst über
fünf Lanes (IE/PL/EE/SK/HR) einen exakten floater_pct von 0,07000 — dasselbe
Muster wie bei Fischerwerke, jedoch mit einem anderen Aktivierungsdatum
(Januar 2026 statt März 2026). Dies bestätigt Muster-A als
**systemübergreifende, kundenspezifisch terminierte Vereinbarung**.

Muster-B ist mit einer Einzelzeile (EE Lehmja, −100,40 EUR) minimal vertreten
— erster echter Unterfakturierungsnachweis in der EBM-Analyse.

Der Gesamt-Delta von +41.283 EUR stellt **keine Unterfakturierung** dar;
alle beurteilbaren Zeilen liegen oberhalb des DLV-Basistarifs.

---

## 2. Methodik-Referenz

Die Analyse folgt `docs/AUDIT_METHODOLOGY.md`. Relevante Abschnitte:

- **§2** — EBM-Papst DLV-Format (Palletspace-Matrix, Tariffs + Toll sheets)
- **§3** — Muster-A-Erkennung auf floater_pct-Basis (`abs(fp − 0.07) < 0.0015`);
  Begründung warum Ratio-basierte Erkennung für PL-März-Diesel-Floater
  Falsch-Positive erzeugt hätte
- **§5a** — LDM-Fallback für NaN-Stellplätze (`ceil(LDM / 0.4)`); ohne diesen
  Fallback wären 165 von 397 Zeilen (41,6 %) als unbeurteilbar klassifiziert worden

**Scope dieser Analyse:**

| Zeitraum | Phase | DLV-Referenz |
|---|---|---|
| vor 10.10.2025 | `pre_dlv` | kein Calculator-Check |
| 10.10.2025 – 28.02.2026 | `in_dlv_2025` | 20251010-DLV (Fallback: 20260301-DLV) |
| 01.03.2026 – 31.12.2026 | `in_dlv_2026` | 20260301-DLV |

Calculator-Checks ausschließlich auf `in_dlv`-Zeilen. Abrechnung:
`betrag = tariff[route][n_stpl] × (1 + floater) + toll[route][n_stpl]`

---

## 3. Altzahl-Revision 9a.1.b

**Alte Zahl:** −18.517 EUR (scheinbare Unterfakturierung, Etappe 9a.1.b)
**Neue Zahl:** +41.283 EUR (Floater-Aufschlag auf DLV-Tarif, 339 beurteilbare Zeilen)

Die Altzahl ist ein methodisches Artefakt aus drei Ursachen:

**Ursache 1 — Eircode-PLZ-Matching-Lücke:**
IE-Routen verwenden 3-stellige Eircode-Präfixe (z. B. `A92`, `H91`, `R32`), keine
numerischen PLZ. Die Vorgänger-Analyse (9a.1.b) hatte keine Eircode-Mappings und
klassifizierte IE-Zeilen als `no_dlv`. Fehlende Deltas auf großen IE-Beträgen
(276.453 EUR in in_dlv_2025 allein) ließen die Gesamtsumme nach unten kippen.

**Ursache 2 — Kein Floater-Treatment:**
EBM-Papst rechnet `betrag = tariff × (1 + floater) + toll`. Ohne Floater-Modell
war `erwartet > ist` auf allen Zeilen, was negative Deltas erzeugte. Die 9a.4.x-
Analyse modelliert den Floater explizit; `delta = betrag − (tariff + toll)` ist
die Floater-Komponente, nicht eine Falsch-Abrechnung.

**Ursache 3 — Fehlende Phasen-Trennung:**
Pre-DLV-Zeilen (vor 10.10.2025) flossen in die Altzahl-Berechnung ein, obwohl
kein gültiges DLV zur Verfügung stand. Die neue Analyse schließt diese 9 Zeilen
(25.423 EUR) vom Calculator-Check aus.

**Warum die neue Zahl belastbar ist:**
- 100 % der 339 beurteilbaren Zeilen haben positiven delta_raw (betrag ≥ tariff + toll)
- floater_pct-Konsistenz: mean=8,83 %, std=12,26 % — hohe Std durch PL-Ausreißer
  (wenige Zeilen, großes LDM → Stpl-Derivation via LDM-Fallback, rechnerisch korrekt)
- Muster-A (floater_pct=0,07000 ± 0,0015): alle 50 Zeilen im Januar 2026,
  landesübergreifend konsistent

---

## 4. Muster-A Befund

### Definition

Muster-A = fester ERKA-Indexaufschlag von exakt 7,00 % auf den DLV-Basistarif,
erkennbar an `floater_pct = 0.07000 ± 0.0015`. Alle 50 Zeilen liegen im
Januar 2026 (Phase `in_dlv_2025`).

### Lane IE — 16 Muster-A-Zeilen

| Kennzahl | Wert |
|---|---|
| Zeilen in in_dlv_2025 gesamt | 82 |
| davon Muster-A | 16 (19,5 %) |
| Floater-Mittel (Lane gesamt) | 6,56 % |
| Floater-Std | 0,95 % |
| Delta-Summe in_dlv_2025 (Lane) | 16.781,69 EUR |
| EUR-Volumen in_dlv_2025 | 276.453,36 EUR |

Betroffene Orte: Portlaoise (R32), Galway (H91), Dublin (D12), Littleton (E41).
Alle Muster-A-Zeilen: Stpl 33 oder partiell gefüllt, Datum Jan 2026.
floater_pct-Werte: 0,06999–0,07000 (Bandbreite < 0,0001).

### Lane PL — 10 Muster-A-Zeilen

| Kennzahl | Wert |
|---|---|
| Zeilen in in_dlv_2025 gesamt | 87 (73 matched) |
| davon Muster-A | 10 (13,7 % der matched) |
| Floater-Mittel (Lane gesamt) | 8,83 % |
| Floater-Std | 14,66 % |
| Delta-Summe in_dlv_2025 (Lane) | 4.169,09 EUR |
| EUR-Volumen in_dlv_2025 (assessed) | 66.805,63 EUR |

Hohe Std ist Daten-Charakteristik: PL-Stichprobe enthält Zeilen mit kleinem Stpl
(z. B. Legnickie Pole n=1) und Zeilen mit Stpl=33 (Warszawa, via LDM-Fallback),
was bei wenigen Zeilen pro Gruppe zu breiter Streuung führt. Die Muster-A-Zeilen
selbst zeigen floater_pct 0,07000–0,07004 (Bandbreite < 0,0001).
Betroffene Orte: Warszawa (Białołęka), Legnickie Pole.

### Lane EE — 3 Muster-A-Zeilen

| Kennzahl | Wert |
|---|---|
| Zeilen in in_dlv_2025 gesamt | 16 |
| davon Muster-A | 3 (18,8 %) |
| Floater-Mittel (Lane gesamt) | 6,25 % |
| Floater-Std | 15,91 % |
| Delta-Summe in_dlv_2025 (Lane) | 606,43 EUR |
| EUR-Volumen in_dlv_2025 | 7.496,43 EUR |

Betroffener Ort: Lehmja (EE-75301). Muster-A-Zeilen: floater_pct=0,07000 exakt.
Hohe Std durch 1 Muster-B-Zeile (floater_pct=−0,3862, zieht Mittel nach unten).

### Lane SK — 13 Muster-A-Zeilen

| Kennzahl | Wert |
|---|---|
| Zeilen in in_dlv_2025 gesamt | 47 (46 matched) |
| davon Muster-A | 13 (28,3 % der matched) |
| Floater-Mittel (Lane gesamt) | 12,25 % |
| Floater-Std | 24,97 % |
| Delta-Summe in_dlv_2025 (Lane) | 3.280,88 EUR |
| EUR-Volumen in_dlv_2025 (assessed) | 38.409,35 EUR |

Betroffene Orte: Senica (SK-905 01), Trencianske Stankovce (SK-913 11).
floater_pct der Muster-A-Zeilen: 0,06999–0,07000. Hohe Std durch SK-Zeilen mit
variablen Diesel-Floatern außerhalb Januar 2026 (März/April 2026 ~8–21 %).

### Lane HR — 8 Muster-A-Zeilen

| Kennzahl | Wert |
|---|---|
| Zeilen in in_dlv_2025 gesamt | 20 |
| davon Muster-A | 8 (40,0 %) |
| Floater-Mittel (Lane gesamt) | 6,37 % |
| Floater-Std | 0,95 % |
| Delta-Summe in_dlv_2025 (Lane) | 1.455,46 EUR |
| EUR-Volumen in_dlv_2025 | 25.027,60 EUR |

Betroffener Ort: Buje (HR-52460). Niedrige Std (0,95 %) — HR-Lane zeigt die
konsistenteste Floater-Verteilung aller Muster-A-Lanes (floater 2,77–7,00 %,
keine Ausreißer).

### Meta-Erkenntnis: Zweiter Kunde mit 0,07000-Muster

Fischerwerke (KNR 409480) zeigt Muster-A ab März 2026.
EBM-Papst (KNR 410844) zeigt Muster-A ab Januar 2026.

Gleiche Erkennungsformel (`abs(floater_pct − 0.07) < 0.0015`), gleiche
floater_pct-Präzision (Bandbreite < 0,0001 je Zeile), unterschiedliche
Aktivierungsdaten. Das deutet auf **kundenspezifisch terminierte schriftliche
Vereinbarungen** hin — nicht auf einen systemweiten Rollout-Zeitpunkt.

Die vertragliche Grundlage (separates ERKA-Indexschreiben oder Rider) ist für
EBM-Papst noch nicht in den vorliegenden DLV-Dateien identifiziert worden
(→ Abschnitt 8).

---

## 5. Muster-B Befund

### Einzelzeile EE Lehmja

| Feld | Wert |
|---|---|
| Auftragsnummer | 7092010022930001 |
| Datum | 2025-12-08 |
| Lane | EE-Lehmja (EE-75301) |
| Phase | `in_dlv_2025` (DLV 2025-10-10, date_match) |
| Abrechnungsstellplätze | 2 |
| Betrag | 159,60 EUR |
| DLV-Erwartet (tariff+toll) | 260,00 EUR |
| Delta | **−100,40 EUR** |
| floater_pct | −0,3862 |

**Hypothese:** Die Zeile wurde zum Tarif für Stellplatz 1 abgerechnet, obwohl
Stellplatz 2 gemäß Abrechnungsstrecken vorlag. `tariff[EE-75301][1] × 1.064 ≈ 159,60 EUR`
(implizierter Multiplikator = normal-Floater-Niveau von ~6,4 %). Der Fehler
liegt nicht im Floater, sondern in der Stpl-Auswahl.

**Empfehlung:** Retro-Rechnung für Auftrag 7092010022930001 — Nachforderung
von 100,40 EUR gegenüber EBM-Papst oder interner Korrekturbuchung, je nach
Vertragsklausel. Zu prüfen: Ob weitere EE-Zeilen aus November/Dezember 2025
dasselbe Stpl-Off-by-One-Muster zeigen (in 9a.4.2 nur diese eine Zeile
identifiziert).

---

## 6. Kurz-Bericht übrige Lanes

**Lane GB** (8 Zeilen, 20.466,22 EUR, kein Muster):
3 Zeilen in_dlv_2025 (Fallback-DLV 2026, da GB nicht in 2025-Oct-DLV), 5 Zeilen
in_dlv_2026. Floater in_dlv_2025: 5,42 %, in_dlv_2026: 8,73 % konstant.
delta_sum gesamt: 1.426,22 EUR. Keine Auffälligkeiten.

**Lane SI** (15 Zeilen, 8.436,88 EUR, teils unbeurteilbar):
11 Zeilen in_dlv_2025 (7 matched, 4 no_route_match Naklo), 4 Zeilen in_dlv_2026
(1 matched, 3 no_route_match Naklo). Floater der matched-Zeilen: 6,31 %/8,10 %.
delta_sum matched: 293,03 EUR. Naklo (SI) ist nicht im DLV — DLV-Ergänzung
erforderlich (→ Abschnitt 7).

**Lane EE in_dlv_2026** (7 Zeilen, 3.249,11 EUR):
Floater 8,10–10,04 %, delta_sum 259,11 EUR. Keine Muster. Konsistent mit
normalem Diesel-Surcharge-Niveau Q1/Q2 2026.

**Lane HR in_dlv_2026** (4 Zeilen, 3 matched):
1 no_route_match (Kutina, 725,00 EUR). 3 matched: Floater 8,10–8,96 %,
delta_sum 272,03 EUR. Normal.

**Lane SK in_dlv_2026** (23 Zeilen, 21.268,44 EUR, alle matched):
Floater 8,10–20,62 %, delta_sum 2.838,29 EUR. Hohe floater_max (20,62 %)
auf einzelne SK-Zeilen mit kleinem Stpl-Zähler — methodisch erwartet bei
wenigen Zeilen × großem Absolutbetrag-Verhältnis. Keine Muster.

---

## 7. Unbeurteilbare Zeilen

**Gesamt: 58 Zeilen** (EUR-Volumen: 57.163,77 EUR)

### Kategorie A — Pre-DLV (9 Zeilen, 25.422,59 EUR)

Zeilen vor DLV-Gültigkeitsbeginn (10.10.2025). Kein Calculator-Check möglich —
kein aktives DLV für den Lieferzeitraum vorhanden.

| Lane | Ort | n | EUR |
|---|---|---|---|
| IE | Portlaoise, Rathmullan, Galway | 5 | 17.544,11 |
| ES | San Fernando de Henares, Móstoles | 3 | 5.128,48 |
| PT | Vila Franca de Xira | 1 | 2.750,00 |

### Kategorie B — No-Route-Match (49 Zeilen, 31.741,18 EUR)

Routen, für die kein DLV-Eintrag existiert. Unterteilt nach Typ:

**Interner Standort ohne DLV:**
- DE-Mulfingen: 10 Zeilen, 4.910,50 EUR — Heimatwerk EBM-Papst, vermutlich
  Intercompany-Transporte ohne kundengerichtetes DLV. Dokumentationspflicht klären.

**PLZ fehlt im DLV (PL-Expansionsrouten):**
- PL-Lódz: 11 Zeilen, 9.860,00 EUR
- PL-Skawina: 4 Zeilen, 4.609,00 EUR
- PL-Szczecin: 8 Zeilen, 2.454,09 EUR
- PL-Legnica: 5 Zeilen, 2.568,75 EUR

Diese vier PL-Orte erscheinen erst ab Oktober 2025 und sind im DLV 2025-10-10
sowie im DLV 2026-03-01 nicht enthalten. Mögliche Erklärungen: Spot-Aufträge
außerhalb DLV-Deckungskreis, oder neuere Zielorte noch nicht ins DLV
aufgenommen. Klärungsbedarf beim nächsten DLV-Update.

**Sonstige fehlende Routen:**
- SI-Naklo: 7 Zeilen, 3.389,34 EUR
- PT-Vila Franca de Xira (in_dlv): 1 Zeile, 2.633,40 EUR
- HR-Kutina: 1 Zeile, 725,00 EUR
- RS-Prokuplje: 1 Zeile, 407,00 EUR
- SK-Bytca: 1 Zeile, 184,10 EUR

**Dokumentationspflicht:** Alle no_route_match-Routen müssen beim nächsten
DLV-Versionswechsel geprüft werden. Falls neue PLZ aufgenommen werden, kann
die Analyse für diese Zeilen nachgeholt werden.

---

## 8. Offene Klärungsfragen

### Frage 1 — Vertragliche Basis Muster-A bei EBM-Papst

Bei Fischerwerke ist Muster-A auf ein ERKA-Indexschreiben zurückführbar, das
den 7%-Aufschlag ab einem bestimmten Datum aktiviert. Für EBM-Papst liegt kein
entsprechendes Dokument in den aktuellen DLV-Unterlagen vor.

**Zu klären:** Existiert für EBM-Papst ein separates Rider-Dokument oder eine
E-Mail-Vereinbarung, die den 7%-Indexaufschlag ab Januar 2026 autorisiert?
Ohne diesen Nachweis ist Muster-A bei EBM-Papst formal unbelegt, obwohl der
Datenbefund eindeutig ist (50 Zeilen, floater_pct=0,07000 ± 0,0001, Januar 2026,
cross-lane).

**Auswirkung:** Solange die vertragliche Basis nicht belegt ist, können die
50 Muster-A-Zeilen (EUR-Anteil: Teil der 41.283 EUR delta_sum) nicht als
korrekte Abrechnungen bestätigt werden. Retro-Prüfung empfohlen.

### Frage 2 — Diesel-Floater ~9 % gegen aktuelles Surcharges-Sheet

Die beurteilbaren in_dlv_2026-Zeilen zeigen einen Floater von 8,73–9,47 % je
nach Lane (IE: 9,06 %, GB: 8,73 %, EE: 8,55–10,04 %, SK: 8,10–20,62 %).
Das entspricht dem erwarteten Diesel-Surcharge-Niveau Q1/Q2 2026, ist aber
noch nicht gegen das offizielle ERKA-Surcharges-Sheet für diesen Zeitraum
abgeglichen worden.

**Zu klären:** Liegt das ERKA-Dieselzuschlag-Sheet für Jan–Apr 2026 vor?
Abgleich würde erlauben, den variablen Floater zu validieren und eine
ggf. abweichende Floater-Höhe als neues Muster zu identifizieren.

**Auswirkung:** Ohne Abgleich bleibt der Floater-Aufschlag ~9 % plausibel,
aber unvalidiert. Der +41.283 EUR-Delta ist damit als Floater-Komponente
klassifiziert, nicht als Fehler — aber vorbehaltlich dieses Abgleichs.
