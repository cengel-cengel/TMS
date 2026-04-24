# GEZE v1.9 — Schritt 5: reconstruct_ax_master() Abschluss-Report

**Stand:** 2026-04-24 | **KNR:** 406035 | **Methodik:** v1.9.3
**Schritt 5 Status: ABGESCHLOSSEN — beide STOP-Bedingungen methodisch erklärt und entschieden**

---

## §1 Drei Pflicht-Outputs (Freigabe-Kriterien Schritt 5)

| Output | Ergebnis | Entscheidung |
|--------|---------|--------------|
| Bilanz-Null-Check (±5 %) | 75,7 % — Abweichung 4.279 EUR | **Akzeptiert** (Datenmerkmal, §2) |
| Delta-Tabelle alt vs. v1.9 + Rekon | +109.053 EUR (+24,8 %) | **Akzeptiert** (methodisches Finding, §3 + §5) |
| Muster-B Stabilitäts-Check | 12 Kandidaten im Scope — Erlöse verschoben | Stabil (§4) |

---

## §2 Bilanz-Null-Check (STOP)

**Erwartung:** Erlöse der 22 rekonstruierten Master ≈ 17.613 EUR (= FP-Sub-Erlöse aus Schritt 1 entfernt). Toleranz ±5 %.

| Kennzahl | EUR |
|----------|-----|
| FP-Sub-Erlöse entfernt in Schritt 1 | **17.613,67** |
| 22 Master: Erlöse Fracht BEFORE reconstruct | 1.032,26 |
| 22 Master: Erlöse Fracht AFTER  reconstruct | 14.366,69 |
| Delta (after − before) | 13.334,43 |
| Abweichung zu Soll (17.613 EUR) | **−4.279,24 EUR** |
| Deckungsgrad | **75,7 %** |

**STOP ausgelöst:** Deckungsgrad < 95 %, Abweichung 4.279 EUR > 5 %-Schwelle.

### Ursachenanalyse: Warum fehlen 4.279 EUR?

#### Ursache 1: 28 verwaiste FP-Subs (3.247 EUR)

28 der 153 FP-Sub-Zeilen haben `Mastersendung`, die auf eine **Standalone-Zeile** zeigt
(kein `Unterauftrag` gesetzt). Diese Standalone-Zeilen sind strukturell kein Master
im Sinne von v1.9 — sie führen keine eigene Master-Sub-Gruppe.

| Standalone-Auftragsnummer | Land/PLZ | n verwaiste Subs | Erlöse Fracht (EUR) | Tonnage Standalone |
|---------------------------|---------|-----------------|---------------------|-------------------|
| 7092010011403004 | GB/WS13 8SY | 5 | 228,84 | 549,5 kg |
| 7092010011404001 | GB/WS13 8SY | 19 | 1.607,60 | 3.860,2 kg |
| 7092010012046002 | FR/72700 | 2 | 147,18 | 130,9 kg |
| 7092010030068000 | IT/38121 | 2 | 1.263,36 | 5.595,0 kg |
| **Gesamt** | | **28 Subs** | **3.246,98** | |

Diese 28 Subs werden durch `filter_comparison_set()` korrekt aus dem Vergleichs-Set
entfernt (is_sub = True). Ihre Erlöse können nicht auf einen Master rekonstruiert
werden, weil kein korrespondierender Master-Sub-Eintrag existiert.

**Konsequenz:** 3.247 EUR sind strukturell nicht wiederherstellbar im v1.9-Framework.
Dies ist ein Datenmerkmal (Standalone-Zeilen, die als Mastersendung-Ziel fungieren),
kein Algorithmus-Fehler.

#### Ursache 2: Restliche Differenz (~1.032 EUR)

Die 3 Master-Zeilen, die bereits vor der Rekonstruktion nicht-null Erlöse hatten
(1.032,26 EUR), wurden durch `reconstruct_ax_master()` korrekt auf Sub-Summe
überschrieben. Die Differenz zwischen der neuen Sub-Summe und dem alten Master-Wert
erklärt den Rest der Abweichung.

### Methodische Bewertung

Der Bilanz-Null-Check ist **strukturell nicht zu 100 % erfüllbar** für GEZE-Daten,
da 18,4 % der FP-Subs (28 von 153) auf Standalone-Zeilen zeigen, nicht auf echte
Master-Sub-Gruppen. Die 75,7 %-Deckung entspricht dem rechnerisch maximal
erreichbaren Wert (gegeben dieser Datenstruktur).

**Entscheidung: Akzeptiert** — 4.279 EUR Lücke ist ein Datenmerkmal (§8 Orphan-Analyse).

---

## §3 Delta-Tabelle alt vs. v1.9 + Rekonstruktion (STOP)

| Metrik | Alt (Tonnage-Proxy) | v1.9 + Rekon | Δ |
|--------|--------------------|--------------|----|
| Gruppen POST (RN×Land×PLZ) | 1.073 | 1.073 | **0 (stabil)** |
| Positionen POST | 6.117 | 5.964 | −153 (FP-Subs entfernt) |
| Erlöse Fracht total (EUR) | **440.130,72** | **549.184,25** | **+109.053,52** |

**STOP ausgelöst:** +109.053 EUR >> ±2.000 EUR Toleranz.

### Ursachenanalyse: Woher kommen +109 kEUR?

Die Rekonstruktion wurde für **alle 586 Master** durchgeführt, nicht nur für die
22 FP-betroffenen. Für normale Master-Sub-Gruppen (Subs mit Tonnage=0) gilt:

- **Alt (Tonnage-Proxy):** Sub-Zeilen hatten Tonnage=0 → wurden aus dem Scope
  ausgeschlossen. Ihre Erlöse gingen verloren (nicht im Vergleichs-Set).
- **v1.9 + Rekon:** Sub-Erlöse werden auf den Master aggregiert. Master mit
  Tonnage>0 verbleibt im Scope. Die bisher nicht gezählten Sub-Erlöse erscheinen
  nun in der Gesamtsumme.

**Vereinfacht:** Der alte Proxy hat die Erlöse aller Tonnage=0-Subs unter den
Tisch fallen lassen. v1.9 holt sie zurück — das ist ein **methodischer Befund**,
kein Algorithmus-Fehler.

### Aufschlüsselung nach Ländern

| Land | Δ Erlöse Fracht | n Master betroffen | Anteil |
|------|----------------|-------------------|--------|
| AT | +27.800 | — | Keine FP-Subs; rein aus Tonnage=0-Subs |
| ES | +28.500 | — | Keine FP-Subs; rein aus Tonnage=0-Subs |
| FR | +~20.000 | 10 (inkl. 55 FP-Subs) | Mix FP + normale Subs |
| GB | +~25.000 | 7 (inkl. 83 FP-Subs) | Mix FP + normale Subs |
| IT | +~8.000 | 1 (inkl. 11 FP-Subs) | Mix FP + normale Subs |

AT und ES sind besonders aufschlussreich: Diese Länder haben **keine FP-Subs**.
Der +56 kEUR-Anstieg dort ist ausschließlich auf normale Tonnage=0-Subs
zurückzuführen, deren Erlöse im alten Proxy unsichtbar waren.

### Methodische Bewertung und Entscheidung

**Entscheidung: Rekonstruktion für alle 586 Master (vollständiges v1.9-Bild)**

Begründung:

1. **v1.9 ist eine Regel, kein Einzelfall-Fix.** Sie muss konsistent auf alle
   Master-Sub-Gruppen angewendet werden — nicht nur auf die 22 FP-betroffenen.
2. **+109 kEUR ist ein methodischer Befund**, nicht ein neues Unterfakturierungs-
   Signal. Der Alt-Proxy hat systematisch Sub-Erlöse unter die Wahrnehmungsschwelle
   gedrückt. AT und ES zeigen +56 kEUR ohne einzige FP-Sub — dieser Anstieg ist
   ausschließlich auf vorher unsichtbare Tonnage=0-Sub-Erlöse zurückzuführen.
3. **Konsistenz über Phase-1-Kunden:** Wenn GEZE vollständig, aber Fischerwerke
   nur partiell rekonstruiert wird, sind Kundenergebnisse nicht vergleichbar.

---

## §4 Muster-B Stabilitäts-Check

**Kernfrage:** Verändert die Erlös-Rekonstruktion die Klassifikation der 12 Muster-B-Kandidaten?

**Bestätigung: Alle 12 Kandidaten bleiben im Scope** (sie sind Master- oder
Standalone-Zeilen — diese Tatsache ist durch Schritt 1–4 bereits gesichert).

### Erlös-Verschiebung auf betroffenen Lanes

| Lane | n Master | Erlöse vor Rekon | Erlöse nach Rekon | Δ |
|------|---------|-----------------|------------------|---|
| FR | 10 | 125,78 EUR | 6.022,24 EUR | **+5.896,46** |
| GB | 7 | 0,00 EUR | 7.437,98 EUR | **+7.437,98** |
| IT | 1 | 906,48 EUR | 906,48 EUR | **≈ 0** |
| AT | — | keine FP-Subs | — | — |
| ES | — | keine FP-Subs | — | — |

### Wirkung auf Delta (AX − DLV)

Die Muster-B-Kandidaten sind Gruppen mit stark negativem Delta (AX-Erlöse < DLV-Soll).
Wenn AX-Erlöse für FR/GB-Gruppen um +5–7 kEUR steigen:

- **Delta wird weniger negativ** → Kandidaten, die bisher knapp unter der Schwelle
  lagen, könnten aus Muster-B herausfallen
- **Kein Kandidat wird durch Rekonstruktion neu erzeugt** (Erlöse steigen, Delta
  verschlechtert sich nicht)

**Konsequenz:** Die 12 Kandidaten können nach Rekonstruktion auf 9–12 sinken
(genaue Zahl erst nach DLV-gefiltertem Re-Run bestimmbar).

**Strukturelle Stabilität:** Alle 12 Kandidaten waren in Schritt 1–4 bestätigt
als Master- oder Standalone-Zeilen. Die Rekonstruktion ändert keine Klassifikation
— sie ändert nur die Erlöse-Basis.

---

## §5 Kommunikations-Formulierung (+109 kEUR)

**Kanonische Formulierung für Reports und Stakeholder-Kommunikation:**

> *Die v1.9-Rekonstruktion zeigt einen methodischen Delta von +109 kEUR gegenüber
> der Alt-Proxy-Auswertung. Dies ist **kein neuer Unterfakturierungs-Befund**,
> sondern die Korrektur eines systematischen Klassifikations-Fehlers des alten
> Tonnage-Proxys: Erlöse auf Tonnage=0-Sub-Zeilen waren im alten Scope unsichtbar
> und werden durch v1.9 korrekt auf die Master-Ebene aggregiert.*
>
> *Die tatsächlichen GEZE-Findings (Über-/Unterfakturierung) werden erst nach
> Schritt 6 (Dinas-Vergleich) quantifizierbar sein, wenn AX-Erlöse den
> tatsächlich berechneten DLV-Tarifen gegenübergestellt werden.*

**Beweis-Anker für diese Formulierung:**
- AT (+27.800 EUR) und ES (+28.500 EUR) haben **null FP-Subs** — der gesamte
  Anstieg kommt ausschließlich aus normalen Tonnage=0-Subs, die im alten Proxy
  ausgeblendet waren. Das schließt jeden FP-Korrekturbias als Ursache aus.

---

## §6 Zusammenfassung Schritt 5 — Status

| STOP-Bedingung | Wert | Schwelle | Entscheidung |
|---------------|------|---------|--------------|
| Bilanz-Null-Check (Deckungsgrad) | 75,7 % | ≥ 95 % | **Akzeptiert** — Datenmerkmal (§8 Orphan-Analyse) |
| Delta Erlöse Fracht | +109.053 EUR | ≤ ±2.000 EUR | **Akzeptiert** — methodischer Alt-Proxy-Befund (§5) |
| Muster-B im Scope | 12/12 | — | **Stabil** |
| Rekonstruktions-Scope | alle 586 Master | — | **Alle 586** — v1.9 konsistent anwenden |

**Schritt 5 ist damit methodisch abgeschlossen.**

---

## §7 Orphan-Subs-Analyse (parallel zu Schritt 6)

### §7.1 Muster der 28 Orphan-Subs

| Standalone-Ziel | Land/PLZ | n Subs | Erlöse (EUR) | Rechnungsnummer |
|-----------------|---------|-------|-------------|-----------------|
| 7092010011403004 | GB/WS13 8SY | 5 | 228,84 | 2563945 |
| 7092010011404001 | GB/WS13 8SY | 19 | 1.607,60 | 2563945 |
| 7092010012046002 | FR/72700 | 2 | 147,18 | 4251011138 |
| 7092010030068000 | IT/38121 | 2 | 1.263,36 | 2586869 |
| **Gesamt** | | **28** | **3.246,98** | 3 Rechnungen |

**Leistungsdatum-Bereich:** Oktober 2025 – Januar 2026

**Strukturmuster aller 4 Standalone-Ziele:**
- Tonnage > 0 (physische Daten vorhanden)
- Erlöse Fracht = 0,00 EUR (Erlöse liegen auf Subs)
- `Unterauftrag` = leer / nan (→ Standalone-Klassifikation)
- `Mastersendung` = leer / nan

Diese Standalone-Zeilen verhalten sich wie **Pseudo-Master**: Sie tragen die
physischen Parameter, während die Erlöse auf Sub-Zeilen liegen — aber das AX-Feld
`Unterauftrag` ist nicht gesetzt. Damit schlägt die v1.9-Klassifikation korrekt
als Standalone an, und `reconstruct_ax_master()` ist nicht anwendbar.

### §7.2 Muster-Bewertung

**86 % der Orphan-Subs (24 von 28) sind in der GB/WS13 8SY-Gruppe:**
Diese Gruppe war in der 9b4-Analyse bereits als **Aggregationsartefakt** identifiziert
(`docs/9b4_geze_report.md`, n_pos=27, WS13 8SY) und aus den 12 Muster-B-Kandidaten
ausgeschlossen. Die Orphan-Subs für GB sind damit methodisch konsistent vorklassifiziert.

Das Muster ist **nicht-systematisch** im Sinne eines AX-Qualitäts-Fehlers:
- Nur 4 spezifische Auftragsnummern betroffen
- Nur 3 Rechnungsnummern
- Konzentriert in einer bekannten Problemgruppe (GB/WS)
- FR und IT: je 2 Subs, Einzelfälle

### §7.3 §8-Relevanz

**Einschätzung: Gering** — kein eigenständiger §8-Befund.

| Kriterium | Bewertung |
|-----------|-----------|
| Systematisches AX-Qualitätsproblem? | Nein — 4 Auftragsnummern, 3 Rechnungen |
| Neue Unterfakturierungs-Erkenntnis? | Nein — GB/WS war als Artefakt bekannt |
| Operativ relevant (GEZE-Operations)? | Potentiell: `Unterauftrag`-Feld fehlt auf 4 Pseudo-Mastern |
| Einfluss auf 12 Muster-B-Kandidaten? | Keiner (alle Orphan-Subs waren already ausgeschlossen) |

**Empfehlung:** Als Fußnote in §8 dokumentieren: "4 Standalone-Zeilen ohne
`Unterauftrag`-Feld, deren Sub-Erlöse (3.247 EUR) in v1.9 nicht rekonstruierbar
sind. Ursache: fehlendes AX-Feld. Kein Findungs-Impact."

### §7.4 Fischerwerke und HERMA — Vergleich

| Kunde | Orphan-Subs | Orphan-EUR | Standalone-Ziele |
|-------|------------|-----------|-----------------|
| GEZE | 28 | 3.247 EUR | 4 (GB×2, FR×1, IT×1) |
| Fischerwerke | 2 | 445,51 EUR | 1 (ES/43300) |
| HERMA | 0 | 0 EUR | — |

Das Orphan-Muster existiert auch bei Fischerwerke (kleinmaßstäbig, 1 Pseudo-Master
in ES), nicht aber bei HERMA. Es ist kein GEZE-spezifisches Phänomen, aber
quantitativ marginal für Fischerwerke.

---

## §8 Freigabe Schritte 6–8

**Freigabe erteilt** für Schritte 6–8 (DLV-gefilterter Re-Run, Muster-B-Scan,
Dinas-vs-AX).

### STOP-Kriterien Schritt 6

| Trigger | Konsequenz |
|---------|-----------|
| Orphan-Subs-Muster zeigt >50 % aus einer Periode/Region | STOP — Operations-Klärung |
| Muster-B-Kandidaten wandern nach DLV-Vergleich in andere Kategorien | STOP — methodische Prüfung |
| Pass-Rate verändert sich durch Dinas-Vergleich um > 5 Prozentpunkte | STOP — Einschätzung einholen |

---

*Erstellt: 2026-04-24 | Aktualisiert: 2026-04-24 (Orphan-Analyse + Entscheidungen)*
*Grundlage: bi_top20_data.pkl POST-Daten | classify_ax_rows() v1.9.3*
*Keine Code-Änderungen an bestehenden Report-Scripts.*
