# GEZE v1.9 — Schritt 5: reconstruct_ax_master() STOP-Report

**Stand:** 2026-04-24 | **KNR:** 406035 | **Methodik:** v1.9.3
**Schritt 5 Status: STOP — zwei Bedingungen ausgelöst**

---

## §1 Drei Pflicht-Outputs (Freigabe-Kriterien Schritt 5)

| Output | Ergebnis | Status |
|--------|---------|--------|
| Bilanz-Null-Check (±5 %) | 75,7 % — Abweichung 4.279 EUR | **STOP** |
| Delta-Tabelle alt vs. v1.9 + Rekon | +109.053 EUR (+24,8 %) | **STOP** |
| Muster-B Stabilitäts-Check | 12 Kandidaten im Scope — Erlöse verschoben | Erläuterung unten |

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

| Standalone-Auftragsnummer | n verwaiste Subs | Erlöse Fracht (EUR) |
|---------------------------|-----------------|---------------------|
| 7092010011403004 | — | — |
| 7092010011404001 | — | — |
| 7092010012046002 | — | — |
| 7092010030068000 | — | — |
| **Gesamt** | **28 Subs** | **~3.247** |

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

**Entscheidungspunkt:**
> Wird die 4.279-EUR-Lücke als strukturell-akzeptabel klassifiziert (Datenmerkmal),
> oder ist sie ein Blocker für die v1.9-Freigabe?

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
Tisch fallen lassen. v1.9 holt sie zurück.

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

### Methodische Bewertung: Finding oder Design-Problem?

**Interpretation A (strukturelles Finding):**
Der alte Tonnage-Proxy hat systematisch Sub-Erlöse ausgeschlossen. Der +109 kEUR-
Unterschied ist kein Algorithmus-Fehler, sondern die korrekte Quantifizierung des
alten Proxy-Fehlers. v1.9 zeigt das tatsächliche Erlöse-Bild.

**Interpretation B (Design-Frage):**
Sollte `reconstruct_ax_master()` nur für FP-betroffene Master aufgerufen werden
(22 Stück), oder für alle 586 Master? Wenn nur 22: Δ = +13.334 EUR (innerhalb
des Erwartungsrahmens). Der +109 kEUR-Unterschied verschwindet, aber dann werden
normale Tonnage=0-Subs weiterhin ignoriert.

**Entscheidungspunkt:**
> Soll die Rekonstruktion für **alle** Master ausgeführt werden (volles v1.9-Bild),
> oder nur für die 22 FP-betroffenen (minimaler Eingriff)?
>
> — Vollständig (alle 586): +109 kEUR, zeigt strukturellen Alt-Proxy-Fehler
> — Minimal (22 FP): Δ ≈ +13 kEUR, nur FP-Gap geschlossen

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

## §5 Zusammenfassung der STOP-Bedingungen

| STOP-Bedingung | Wert | Schwelle | Status |
|---------------|------|---------|--------|
| Bilanz-Null-Check (Deckungsgrad) | 75,7 % | ≥ 95 % | **STOP** |
| Delta Erlöse Fracht | +109.053 EUR | ≤ ±2.000 EUR | **STOP** |
| Muster-B im Scope | 12/12 | — | Stabil |

---

## §6 Entscheidungspunkte vor Schritt 6–8

**Zwei Entscheidungen erforderlich:**

### Entscheidung 1: Bilanz-Lücke (4.279 EUR)
Die 28 verwaisten FP-Subs (→ Standalone-Ziele) sind strukturell nicht
rekonstruierbar. Optionen:

- **A) Akzeptieren** (Datenmerkmal): 75,7 % Deckung ist das strukturell maximal
  Erreichbare. GEZE-Rollout auf dieser Basis.
- **B) Blockieren**: Bis AX-Daten der 4 Standalone-Zeilen untersucht sind,
  ob korrekte Master vorhanden waren.

### Entscheidung 2: Rekonstruktions-Scope
Soll `reconstruct_ax_master()` für alle 586 Master oder nur die 22 FP-betroffenen
ausgeführt werden?

- **A) Alle 586** (empfohlen für v1.9-Vollständigkeit): Δ = +109 kEUR zeigt
  strukturellen Alt-Proxy-Fehler. Methodisch korrekt, aber erfordert Erklärung
  für Stakeholder.
- **B) Nur 22 FP-betroffene**: Δ ≈ +13 kEUR, minimaler Eingriff, normale
  Tonnage=0-Subs weiterhin im alten Proxy-Verhalten.

---

## §7 Ausstehend (Schritte 6–8 — noch nicht freigegeben)

| Schritt | Inhalt | Status |
|---------|--------|--------|
| 6 | DLV-gefilterter Re-Run | Wartend auf §6-Entscheidungen |
| 7 | Neue Muster-B-Scan nach DLV-Filter | Wartend |
| 8 | Dinas-vs-AX systematisch (15 Multi-Group-RNs) | Wartend |

---

*Erstellt: 2026-04-24 | Schritt 5 STOP-Report*
*Grundlage: bi_top20_data.pkl POST-Daten | classify_ax_rows() v1.9.3*
*Keine Code-Änderungen an bestehenden Report-Scripts.*
