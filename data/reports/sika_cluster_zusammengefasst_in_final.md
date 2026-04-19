# Sika AX-Cluster — „Zusammengefasst in" als autoritative Cluster-Definition

**Quelle:** `data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Sika.xlsx`  
**Rows gesamt:** 3.590  
**Erstellt:** 2026-04-19  
**Scope:** Reine Inventur, kein Code, kein Commit.

---

## 1. Spaltennamen und Cluster-Semantik

| Funktion | Spaltenname | Typ | Non-null |
|----------|-------------|-----|----------|
| Eigene Zeilen-ID | `Abrechnungsstrecke` | int64 | 3.590 (100%) |
| **Cluster-Key** | **`Zusammengefasst in`** | float64 | **3.589** (1 NaN) |
| Eigene Auftragsnummer | `Auftragsnummer` (= `Auftragsnummer2`) | int64 | 3.590 |
| KNR | `Kontonummer` | str | 3.590 |
| Betrag | `Betrag` | float64 | 3.590 |
| Sender-PLZ | *(nicht vorhanden — nur `Von Ort` Freitext + `Von Land`)* | — | — |
| Empfänger-PLZ | *(nicht vorhanden — nur `Nach Ort` Freitext + `Nach Land`)* | — | — |
| Leistungsdatum | `Leistungsdatum` | datetime64 | 3.590 |

> **PLZ fehlt explizit:** Kein PLZ-Feld im Export. Verfügbare Näherungen: `Von Ort`/`Nach Ort`
> (Stadtname-Freitext) und `Ausgangsrelation`/`Eingangsrelation` (4-stellige AX-Routencodes,
> keine Postleitzahlen). Für PLZ-basierte Analysen ist ein JOIN auf die Auftragsebene
> erforderlich.

---

## 2. Cluster-Aufbau nach AX-Regel (`Zusammengefasst in`)

```
cluster_key = Wert in 'Zusammengefasst in'

Drei Row-Typen:
  A) ZGI == eigene Abrechnungsstrecke   → Self-ref Master (Cluster-Träger)
  B) ZGI  ≠ eigene Abrechnungsstrecke   → echte Sub-Row (Cluster-Mitglied)
  C) ZGI  == NaN                         → Standalone (kein Cluster)
```

| Typ | Anzahl |
|-----|--------|
| **Self-ref Masters** (Typ A) | **2.881** |
| **Echte Subs** (Typ B) | **708** |
| **Standalone ZGI=NaN** (Typ C) | **1** |

### Sub-Anzahl Verteilung

| Subs pro Cluster | Cluster-Anzahl |
|-----------------|----------------|
| 1 | 380 |
| 2 | 102 |
| 3 | 19 |
| 4 | 13 |
| 5 | 3 |
| **≥1 (gesamt)** | **517** |
| **0 (Solo-Master)** | **2.364** |

**Betrag im Cluster:** Der Betrag liegt ausnahmslos auf der Master-Row (Typ A).
Alle 708 Sub-Rows haben `Betrag = 0,00`. Die Cluster-Summe ist identisch mit dem Master-Betrag.

---

## 3. Strukturelle Verifikation — alle vier Fragen

### 3a. Dangling Pointers

**Ergebnis: KEINE.**

Jeder der 517 Cluster-Keys (`Zusammengefasst in`-Wert) existiert als `Abrechnungsstrecke`
in der Datei. Es gibt keine „verwaisten" ZGI-Referenzen auf nicht-existente Master.

### 3b. Cross-KNR-Cluster

**Ergebnis: KEINE.**

Kein einziger Cluster enthält Sub-Rows mit unterschiedlichen KNRs. 100% der 517 Cluster
sind streng mono-KNR (Master-KNR === Sub-KNR für alle Mitglieder).

> Die cross-KNR-Verbindung zwischen 413276 und ARA1802357 existiert **nicht innerhalb**
> eines Clusters, sondern auf **Auftragsnummer-Ebene**: dieselbe Auftragsnummer erscheint
> als Master-Row in zwei separaten Clustern unter verschiedenen KNRs (s. Abschnitt 6).

### 3c. Multi-Day-Cluster

**Ergebnis: KEINE.**

Leistungsdatum-Streuung unter Subs desselben Clusters: **0 Tage** in 100% der Fälle.
Ebenso ist der Abstand zwischen Master-Datum und Sub-Datum stets 0. „Pro Tag" ist
in AX exakt 1 Tag — keine ±1-Tag-Toleranz.

### 3d. Multi-Destination-Cluster (Nach Ort)

**Ergebnis: 1 Ausnahme.**

| Cluster-Key | KNR | Master-Betrag | Nach Land | Nach Ort (Subs) |
|-------------|-----|--------------|-----------|-----------------|
| 286727 | ARA_Sika_DE+CH | 3.491,45 EUR | IE | Dublin (Ashtown), Dublin (Ballymun) |

Zwei verschiedene Dublin-Werke desselben Kunden unter einem Cluster (Leistungsdatum,
Von Ort, KNR identisch). Kein Fall von verschiedenen Zielländern. Nach Land: 0 Cluster
mit >1 Zielland.

---

## 4. Standalone-Row (ZGI = NaN)

Genau **1 Row** hat `Zusammengefasst in = NaN`:

| Feld | Wert |
|------|------|
| Abrechnungsstrecke | 509878 |
| Kontonummer | 491063 |
| Hauptabrechnungsstrecke | **Nein** (Sub ohne Cluster-Zuordnung) |
| Betrag | 0,00 EUR |
| Leistungsdatum | 2026-04-17 |
| Route | Stuttgart → Fraserburgh (DE→GB) |
| Gewicht | 21.182,21 kg |
| Auftragsnummer | 7092010049960005 |

Diese Row ist als „Nein" (Sub) markiert, hat aber keinen ZGI-Pointer — möglicherweise
ein Datenfehler oder noch nicht abgeschlossene Buchung (neuestes Datum im Dataset).
Betrag=0, daher kein Erlös-Impact. Für Calculator-Matching: ignorieren.

---

## 5. Spezialfall ARA_Sika_DE+CH

| Merkmal | Wert |
|---------|------|
| Rows gesamt | 1.504 |
| Self-ref Master (Cluster-Träger) | 1.144 |
| Echte Subs (ZGI → andere Abrechnungsstrecke) | 360 |
| Subs zeigen auf welche KNR als Master? | **ARA_Sika_DE+CH** (266 Cluster) |

**ARA_Sika_DE+CH ist ausschließlich Cluster-Master-Träger und Sub seiner eigenen Cluster.**
Es gibt keine Rows dieser KNR, die auf eine andere KNR als Cluster zeigen.

### Die 337 Betrag=0-Master

| Untergruppe | Anzahl |
|-------------|--------|
| Mit ≥1 Sub | 96 |
| Ohne Sub (Solo) | 241 |
| Deren Auftragsnummer in einer anderen Row mit Betrag>0 | 239 von 241 |
| Dieser „Mirror" liegt bei KNR | ARA_Sika_DE+CH (238×), 527406 (1×) |

**Erklärung:** Die 241 Solo-0-Master sind AX-interne Dubletten. Ihre Auftragsnummer
erscheint als eigene separate Master-Row (anderer `Abrechnungsstrecke`-Wert) mit
Betrag>0 unter derselben KNR ARA_Sika_DE+CH. Nicht Storno, nicht Cross-KNR —
AX hat dieselbe Sendung unter zwei Abrechnungsstrecken erfasst (0-Version und
Billing-Version).

**Für Etappe 7/8:** Nur Master-Rows mit `Betrag > 0` heranziehen
(807 von 1.144 ARA-Mastern). Die 337 Null-Master erzeugen keinen Erlös und würden
den Vergleich verfälschen.

---

## 6. Spezialfall KNR 413276 (Spiegelkonto)

| Merkmal | Wert |
|---------|------|
| Rows gesamt | 89 |
| Self-ref Master | 69 — **alle Betrag=0** |
| Eigene Sub-Rows (zeigen auf 413276-Master) | 20 |
| Werden 413276-Master von **anderen KNRs** als ZGI referenziert? | **NEIN** |
| Zeigen ARA1802357-Subs auf 413276-Master? | **NEIN** |

**413276 ist ein komplett in sich geschlossenes Schattenregister.** Die 67/69 Cross-KNR-
Verbindung zu ARA1802357 besteht nur auf Auftragsnummer-Ebene: dieselbe Auftragsnummer
erscheint als Master-Row in Cluster A (413276, Betrag=0) UND als Master-Row in Cluster B
(ARA1802357, Betrag>0). Beide Cluster sind vollständig getrennt — keine ZGI-Pointer
über die KNR-Grenze.

### Cross-KNR-Duplikate auf Auftragsnummer-Ebene (alle Paare)

| KNR-Paar | Gemeinsame Master-Auftragsnummern | Muster |
|----------|----------------------------------|--------|
| **413276 ↔ ARA1802357** | **67** | 413276=0 EUR, ARA1802357>0 EUR |
| 413276 ↔ 527406 | 2 | 413276=0, 527406=0 |
| 527406 ↔ ARA_Sika_DE+CH | 2 | 527406=0, ARA_Sika_DE+CH>0 |
| 527406 ↔ ARA1802357 | 2 | 527406=0, ARA1802357>0 |
| 527406 ↔ 529453 | 1 | 527406=0, 529453>0 |

Ergänzend: 18 Sub-Auftragsnummern tauchen in Clustern beider KNRs 413276 UND ARA1802357 auf
(die Sub-Rows dieser Cluster zeigen auf ihren jeweiligen KNR-spezifischen Master).

---

## 7. Zusammenfassung aller strukturellen Befunde

| Frage | Befund |
|-------|--------|
| Dangling Pointers (ZGI-Wert ohne zugehörige Abrechnungsstrecke)? | **NEIN** — vollständig referenzinteger |
| Cross-KNR innerhalb eines Clusters (Subs verschiedener KNRs)? | **NEIN** — alle Cluster streng mono-KNR |
| Multi-Day-Cluster (Subs auf verschiedenen Leistungsdaten)? | **NEIN** — exakt 0 Tage Streuung, immer |
| Multi-Destination-Cluster (verschiedene Nach Ort)? | **1 Ausnahme** (2 Dublin-Werke) |
| Multi-Land-Cluster (verschiedene Nach Land)? | **NEIN** |
| Standalone-Rows ohne ZGI? | **1** (509878, Betrag=0, wahrscheinl. Datenfehler) |
| Sub-Betrag immer 0? | **JA** — ausnahmslos (alle 708 Subs) |
| Betrag liegt immer auf Master? | **JA** — 100% |
| PLZ-Felder in der Datei? | **NEIN** — nur `Von Ort`/`Nach Ort` (Freitext) und Routencodes |
| ARA_Sika_DE+CH: Sub eines anderen KNR? | **NEIN** — nur eigener Cluster-Master |
| 413276: Von anderen KNRs als ZGI referenziert? | **NEIN** — geschlossenes Schattenregister |

---

## 8. Exemplarische Cluster (10 Beispiele)

### Typ 1 — Normales 5-Sub-Cluster (ARA1802357 → GB)

```
cluster_key = 178023
KNR: ARA1802357 | Billing: Sika Automotive Deutschland GmbH | Datum: 2025-12-04
Route: Stuttgart (Weilimdorf) → Minworth (GB)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 178023 | **481,95 EUR** | 240,4 | 7092010021922007 |
| sub | 178024 | 0,00 | 219,6 | 7092010021925008 |
| sub | 178025 | 0,00 | 550,0 | 7092010021926005 |
| sub | 178026 | 0,00 | 39,2 | 7092010021927002 |
| sub | 178027 | 0,00 | 58,1 | 7092010021929006 |
| sub | 178028 | 0,00 | 40,8 | 7092010021933003 |

---

### Typ 2 — Normales 5-Sub-Cluster (491063 → GB)

```
cluster_key = 379995
KNR: 491063 | Billing: Sika Deutschland CH AG & Co KG | Datum: 2026-02-27
Route: Stuttgart → Newport/MHI Vestas (GB)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 379995 | **2.541,22 EUR** | 1.165,8 | 7092010040174005 |
| sub | 379996 | 0,00 | 682,9 | 7092010040171004 |
| sub | 379997 | 0,00 | 485,0 | 7092010040168004 |
| sub | 379998 | 0,00 | 299,8 | 7092010040172001 |
| sub | 379999 | 0,00 | 582,9 | 7092010040165003 |
| sub | 380000 | 0,00 | 193,0 | 7092010040173008 |

---

### Typ 3 — Normales 4-Sub-Cluster (ARA1802357 → IT)

```
cluster_key = 114896
KNR: ARA1802357 | Datum: 2025-10-27
Route: Stuttgart (Weilimdorf) → Settimo Torinese / PILKINGTON ITALIA (IT)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 114896 | **148,25 EUR** | 56,0 | 7092010011405008 |
| sub | 114899 | 0,00 | 776,0 | 7092010011398003 |
| sub | 114900 | 0,00 | 56,0 | 7092010011400003 |
| sub | 114901 | 0,00 | 47,0 | 7092010011401000 |
| sub | 114902 | 0,00 | 47,0 | 7092010011407002 |

---

### Typ 4 — Normales 4-Sub-Cluster (491063 → GB)

```
cluster_key = 187988
KNR: 491063 | Datum: 2025-12-09
Route: Stuttgart → Newport/MHI Vestas (GB)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 187988 | **2.354,23 EUR** | 352,0 | 7092010023335003 |
| sub | 187989 | 0,00 | 302,0 | 7092010023333009 |
| sub | 187990 | 0,00 | 485,0 | 7092010023332002 |
| sub | 187991 | 0,00 | 463,0 | 7092010023331005 |
| sub | 187994 | 0,00 | 874,0 | 7092010023852005 |

---

### Typ 5 — 2-Sub-Cluster (527406 → IT, Exportroute)

```
cluster_key = 27923
KNR: 527406 | Billing: Sika Automotive AG | Datum: 2025-10-10
Route: Stuttgart → Atessa / FCA Atessa Carrozzerie (IT)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 27923 | **758,80 EUR** | 3.353,0 | 7092010006236006 |
| sub | 27924 | 0,00 | 586,0 | 7092010006237003 |
| sub | 27928 | 0,00 | 87,0 | 7092010006371004 |

---

### Typ 6 — 2-Sub-Cluster (511241, Import IT→DE)

```
cluster_key = 4484
KNR: 511241 | Billing: SIKA SUPPLY CENTER AG | Datum: 2025-09-29
Route: Cerano (IT) → Stuttgart (Weilimdorf) — Importroute
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 4484 | **4.977,43 EUR** | 19.040,0 | 7092010000673005 |
| sub | 4485 | 0,00 | 19.464,0 | 7092010000674002 |
| sub | 4486 | 0,00 | 20.229,0 | 7092010000706000 |

---

### Typ 7 — 0-Betrag-Cluster (413276 Spiegelkonto, 4 Subs)

```
cluster_key = 77089
KNR: 413276 (SHADOW — alle Beträge 0) | Datum: 2025-10-27
Route: Stuttgart (Weilimdorf) → Settimo Torinese / PILKINGTON ITALIA (IT)
HINWEIS: Identische Auftragsnummer wie Cluster 114896 (ARA1802357, 148,25 EUR)
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Auftragsnummer |
|-------|-------------------|--------|-------------|----------------|
| **MASTER** | 77089 | **0,00 EUR** | 56,0 | 7092010011405008 |
| sub | 77418 | 0,00 | 776,0 | 7092010011398003 |
| sub | 77419 | 0,00 | 56,0 | 7092010011400003 |
| sub | 77420 | 0,00 | 47,0 | 7092010011401000 |
| sub | 77421 | 0,00 | 47,0 | 7092010011407002 |

---

### Typ 8 — Multi-Destination-Cluster (einzige Ausnahme, ARA_Sika_DE+CH → IE)

```
cluster_key = 286727
KNR: ARA_Sika_DE+CH | Datum: 2025-12-12
Route: Stuttgart → Dublin — 2 verschiedene Werke im selben Cluster
```
| Rolle | Abrechnungsstrecke | Betrag | Gewicht (kg) | Nach Ort | Auftragsnummer |
|-------|-------------------|--------|-------------|----------|----------------|
| **MASTER** | 286727 | **3.491,45 EUR** | 14.544,0 | Dublin (Ballymun) | 7092010024577006 |
| sub | 286728 | 0,00 | 44,0 | Dublin (Ashtown) | 7092010024616002 |
| sub | 286729 | 0,00 | 1.168,0 | Dublin (Ballymun) | 7092010024579000 |

---

### Typ 9 — ARA_Sika_DE+CH 0-Betrag-Cluster mit Sub (AX-Dublett)

```
cluster_key = 134151
KNR: ARA_Sika_DE+CH (Betrag=0 — AX-Dublett, Billing-Version unter anderer Abrechnungsstrecke)
Datum: 2025-11-19 | Route: Stuttgart → Sassuolo (IT)
```
| Rolle | Abrechnungsstrecke | Betrag | Nach Ort | Auftragsnummer |
|-------|-------------------|--------|----------|----------------|
| **MASTER** | 134151 | **0,00 EUR** | Sassuolo | 7092010018545004 |
| sub | 138332 | 0,00 | Sassuolo | 7092010018862002 |

---

### Typ 10 — Standalone ZGI=NaN (einzige Row ohne Cluster-Zuordnung)

```
Abrechnungsstrecke = 509878
KNR: 491063 | Hauptabrechnungsstrecke: Nein | Betrag: 0,00 EUR
Datum: 2026-04-17 (neuestes Datum im Dataset — mglw. offene Buchung)
Route: Stuttgart → Fraserburgh (DE→GB) | Gewicht: 21.182,21 kg
Auftragsnummer: 7092010049960005
```
*Sub-Row ohne ZGI-Pointer — Datenfehler oder noch nicht abgeschlossene Buchung.
Betrag=0, kein Erlös-Impact.*

---

## 9. Implikationen für Etappe 7/8 Spec

| Regel | Begründung |
|-------|-----------|
| **Cluster-Key = `Zusammengefasst in`** (autoritativ) | Referenzinteger (0 Dangling), exklusiv mono-KNR, exklusiv 1 Leistungsdatum |
| **Nur Master-Rows mit `Betrag > 0` für Soll-Erlös** | Sub-Betrag immer 0; ARA-Duplikate (337×) und 413276-Shadow (69×) würden zählen |
| **413276 aus Erlösvergleich ausschließen** | Reine Spiegelentität — 0 EUR auf allen 69 Mastern; Erlös liegt auf ARA1802357 |
| **ARA_Sika_DE+CH Null-Master filtern** | 337 Rows mit Betrag=0 sind AX-Dubletten; je 239/241 haben Mirror mit Betrag>0 |
| **PLZ-Join erforderlich** | Die Datei enthält keine PLZ-Felder; Destination nur als Ort-Freitext verfügbar |
| **Einzige Anomalie: Cluster 286727** | 2 Dublin-Werke im selben Cluster — bei Destination-Lookup auf Cluster-Ebene ggf. als „Dublin/IE" aggregieren |
| **Standalone-Row 509878** | Betrag=0, Nein-Markierung, kein ZGI → ignorieren |
