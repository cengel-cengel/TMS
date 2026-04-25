# TMS Billing Audit — Methodik-Referenz

**Projekt:** Migration Dinas → AX (ERP-Wechsel)
**Scope:** Billing-Accuracy-Audit für Kundentarife (Etappe 9a.x)
**Stand:** 2026-04-24 | **Version:** v1.9.4

---

## §1 Grundprinzip

Jede Abrechnungszeile aus den **Abrechnungsstrecken** (AX-System) wird gegen den
**kundengerichteten DLV-Tarif** geprüft — nicht gegen den Einkaufstarif des
Unterfrachtführers (z. B. Kern). Ziel: Nachweis von Über- oder Unterfakturierung
gegenüber der vertraglich vereinbarten Offerte.

Die Prüfung ist **phasen-bewusst**: Jede Zeile wird einem Zeitfenster zugeordnet:
- `pre_dlv` — vor DLV-Gültigkeitsbeginn (kein aktives DLV; kein Calculator-Check)
- `pre_dlv_2026` — Leistungsdatum vor 01.01.2026 bei Kunden, deren ältestes
  verfügbares DLV erst 2026 beginnt (z. B. CHT: DLV-Start 2026-01-01). Diese
  Zeilen sind nicht unbeurteilbar — sie benötigen ein 2025-DLV, das ggf. noch
  nicht extrahiert/gepflegt ist. fp-Werte zeigen systematischen Versatz vs.
  2026-DLV, der als DLV-Version-Gap zu dokumentieren ist, nicht als Abweichung.
- `in_dlv` / `in_dlv_2025` / `in_dlv_2026` — innerhalb eines Gültigkeitsfensters
- `in_dlv_2025_fallback` — Datum nach DLV-Ablauf, aber kein Nachfolge-DLV
  vorhanden; 2025-DLV bleibt aktiv (z. B. GEZE: kein 2026-DLV)
- `post_dlv` — nach DLV-Ablauf mit Nachfolge-DLV (Fallback explizit deaktiviert)

Calculator-Checks laufen **ausschließlich** auf `in_dlv`-Zeilen. `pre_dlv_2026`-
Zeilen werden im Report mit Versatz-Kennzeichnung ausgewiesen (kein Calculator-
Befund, aber Indikator für fehlendes 2025-DLV).

---

## §2 DLV-Tarif-Formate

### §2.0 Standard-Formeln (ab v1.5)

#### Diesel-Regel (methodikweit verbindlich)

**Diesel ist IMMER eine separate Komponente** — sie erscheint in den BI-Daten als
eigene Spalte `Erlöse Diesel` und fließt **nie** in `floater_pct` ein.

```
# Fracht-Abweichung:
floater_pct  = (Erlöse_Fracht − basispreis) / basispreis

# Diesel-Abweichung (separat):
diesel_delta = Erlöse_Diesel − diesel_soll
# diesel_soll = 0, wenn DLV keinen Diesel-Satz modelliert
# diesel_soll = calculierter Satz, wenn DLV Dieselfloater enthält
```

Diese Trennung verhindert, dass variable Dieselzuschläge als Muster-A-Treffer
fehlinterpretiert werden (vgl. §3 Begründung, PL-Zeilen März 2026).

#### Zwei-Fall-Regel für weitere Komponenten (Maut, Surcharges, Währung)

| Fall | Bedingung | Behandlung |
|---|---|---|
| **A — unbundled** | Komponente im Calculator als eigener Wert UND BI-Spalte zuverlässig gefüllt | Eigenes Delta: `komponente_delta = Erlöse_X − soll_X` |
| **B — all_in** | Komponente im Calculator inkludiert (z. B. Maut in basispreis) ODER BI-Spalte leer/unzuverlässig | In `floater_pct` enthalten; Komponentenliste dokumentieren |

**Pflichtfelder pro Kunden-Block:**

| Feld | Werte | Bedeutung |
|---|---|---|
| `pricing_mode` | `unbundled` \| `all_in` \| `hybrid` | Dominant angewendete Behandlung |
| `all_in_components` | Liste | Welche Komponenten in `floater_pct` eingebettet sind |

Beim Modus `hybrid` gilt `unbundled` für die aufgeführten Einzelkomponenten und
`all_in` für den Rest.

---

### Fischerwerke (Stellplatz-basiert)
- Lookup-Tabelle: Anzahl Stellplätze → Flat-Rate per Sendung
- Per-Route-Dateien (eine Datei pro Abrechnungsrelation)
- Quelle: `Fischerwerke/DLVs & Tarife/`
- `pricing_mode: all_in` — kein separates Maut/Diesel im DLV modelliert
- `all_in_components: [maut, diesel]`

### EBM-Papst (Palletspace-Matrix, LDM-basiert)
- Breite Matrix: Zeile = Route (PLZ-Key), Spalte = Stellplätze 1–33 + FTL
- Zwei Sheets pro DLV-Datei: `Tariffs_DE_EU` (Frachtpreis) + `Toll_DE_EU` (Maut)
- Datenquelle: **Abrechnungsstrecken** `EBM.xlsx` (nicht BI-Daten) — Spalten:
  `betrag` (Fracht + Floater, kein Diesel), `toll` (DLV-Maut)
- `pricing_mode: hybrid` — Maut unbundled (aus `Toll_DE_EU`); Diesel fehlt in
  Abrechnungsstrecken-Quelle (kein `Erlöse_Diesel`-Äquivalent), muss retroaktiv
  geprüft werden (→ §7 EBM-Diesel-Retroaktiv)
- Abrechnungsformel (Abrechnungsstrecken):
```
floater_pct = (betrag − toll) / tariff − 1
# toll aus DLV-Matrix; tariff aus DLV-Matrix
# Diesel: Abrechnungsstrecken-Quelle hat keine separate Diesel-Spalte
#         → falls Diesel in betrag eingebettet: floater_pct enthält Diesel-Anteil
#         → falls Diesel nicht verrechnet: floater_pct = reiner Floater
```
- `all_in_components: [diesel]` — bis Retroaktiv-Check (§7) bestätigt ob diesel=0

### Route-Key-Extraktion (EBM)
- **IE/GB** (Eircode-Länder): 3-stelliger Alpha-Code — `'IE-A92 FY90'` → `'A92'`
- **PLZ-Länder** (PL/SK/SI/HR/EE): Vollständiger PLZ-String — `'PL-03-236'` → `'PL-03-236'`
- **Merged-Einträge**: Pipe-separated → nimm erstes — `'EE-75301|EE-75306'` → `'EE-75301'`

### GEZE GmbH (Gewichts-basiert, EUR/100 kg, Maut all_in)
- `pricing_mode: hybrid`
- `all_in_components: [maut]` — Maut in `basispreis` inkludiert, kein separates `Erlöse_Maut`
- Diesel: Fall A unbundled — `Erlöse_Diesel` in BI-Daten vorhanden; `diesel_soll = 0`
  (DLV modelliert keinen Diesel-Satz); `diesel_delta = Erlöse_Diesel − 0`
- CHF-Floater: Fall B all_in — in `Erlöse_Fracht` eingebettet; via Reverse-Engineer
  auf CHF-Band-Tabelle gemappt

**DLV-Struktur:** Sheet "Exporttarife" — Country-Blocks mit Zonen-Zeilen.
Pro Zone: Minimum-Betrag + Gewichtsbänder (bis 300 kg, bis 500 kg, … bis 3.000 kg)
mit Rate EUR/100 kg. Länder: PT, GB, IE, IT, FR, AT, ES, CH.
Gültig: 2025-01-01 – 2025-12-31 (kein separates 2026-DLV; 2025-Fallback bleibt aktiv).

**Abrechnungsformel:**
```
billing_kg   = max(100, ceil(tonnage_kg / 100) * 100)
basispreis   = max(minimum_zone, rate_per_100kg × billing_kg / 100)   # EUR, Maut inkl.
chf_amount   = basispreis × chf_floater_fraction                       # EUR, nur CH
fracht_soll  = basispreis + chf_amount

floater_pct  = (Erlöse_Fracht − basispreis) / basispreis
# non-CH: floater_pct ≈ CHF-Neutralband (≈0) + variabler Diesel-Floater
# CH:     floater_pct ≈ CHF-Floater-Fraktion (Diesel separat in Erlöse_Diesel)
diesel_delta = Erlöse_Diesel − 0     # diesel_soll=0, DLV hat keinen Diesel-Block
```

**CHF-Floater (nur Empfänger Land = CH):**
Der CHF/EUR-Wechselkurs zum Sendungsdatum dient als **Lookup-Key** in die
Prozentband-Tabelle (Sheet "CH-Währungsfloater" im DLV). Die Tabelle gibt eine
EUR-Prozent-Fraktion auf `basispreis` zurück — kein Währungsumtausch, alles in EUR.

Bandbreite: **CHF/EUR 1,021 – 0,88** in 14 Stufen;
Stückgut (≤ 3.000 kg): 0 % – 9,18 %; Komplett (> 3.000 kg): separates Staffel.

**Reverse-Engineer-Ansatz für 9b.3:** `floater_pct` aus Billing-Daten berechnen →
CHF-Bandtabelle rückwärts → konsistente Bandeinordnung. 9b.3-Ergebnis: 51/95
CH-Gruppen im Neutralband, 3 aktive Bänder, 41 Diesel-Überlagerung.

**Zone-Lookup:** Länderspezifische PLZ-Präfix-Tabellen im Calculator (`geze.py`);
IE = immer Zone 1; GB = Postcode-Area (WS/B/CV… → Zone 1, G/EH… → Zone 3, BT → Zone 4).

### CHT Germany GmbH (Gewichts-basiert, Dual-Mode, Maut unbundled)
- `pricing_mode: hybrid`
- Maut: Fall A unbundled — 0,56 EUR/100 kg (DE-Maut 0,50 + AT-Maut 0,06)
  aus Calculator; `Erlöse_Maut` in BI-Daten vorhanden (empirisch zu prüfen)
- Diesel: `Erlöse_Diesel` laut Calculator-Code = 0 in BI-Daten; Diesel via
  separaten Sonder-Dieselfloater (nicht im DLV modelliert) → `diesel_delta = 0`
- `all_in_components: []` — keine Komponente all_in (außer Diesel=0)

**DLV-Struktur:** Sheet "Ex- und Import Italien" — 8 Zonen, 2 Preismodi.
Gültig: 2026-01-01 – 2026-12-31. Herkunft: DE-72072 Tübingen.
Länder in Scope: IT (cht.py), weitere (AT/BE/ES/GR via dlv_tariffs.py).

**Dual-Mode-Umschaltpunkt: 1.000 kg (Aktual-Gewicht, nicht Billing-Gewicht)**
```
if actual_kg ≤ 1000:   # per-Sendung (Pauschalpreis je Gewichtsband)
    basispreis = band.rates[zone]
else:                   # per-100-kg
    billing_kg = max(100, ceil(actual_kg / 100) * 100)
    basispreis = rate_per_100kg × billing_kg / 100
maut_soll = 0.56 × billing_kg / 100                   # EUR

floater_pct  = (Erlöse_Fracht − basispreis) / basispreis
maut_delta   = Erlöse_Maut − maut_soll
diesel_delta = Erlöse_Diesel − 0
```

**Zone-Lookup (IT):** Erste 2 Stellen der 5-stelligen IT-PLZ → Zone 1–8.
Override: PLZ-Präfix 238/239 → Zone 1 (vor generischem Präfix 23 → Zone 4 geprüft).

**Sonder-PLZ (all_in_special):** PLZ 20052 (Arcor Monza) und 20098 (Sesto Ulteriano)
→ eigene DLV-Datei; immer per-100-kg mit Mindestgebühr 55,46 EUR/Sendung.

**CHT Diesel/Maut-Vereinbarung per Land (B-Check 9c.0, empirisch):**

| Land | `diesel_mode` | `maut_mode` | Erlöse_Diesel >0 | Erlöse_Maut >0 |
|---|---|---|---|---|
| IT | `not_contracted` | `unbundled` | 0/158 (0 %) | 157/158 (99 %) |
| AT | `not_contracted` | `unbundled` | 0/36 (0 %) | 34/36 (94 %) |
| ES | `not_contracted` | `unbundled` | 0/114 (0 %) | 111/114 (97 %) |
| DE | `not_contracted` | `unbundled` | 0/11 (0 %) | 3/11 (27 %) |
| BE | `contracted` | `unbundled` | 256/258 (99 %) | 256/258 (99 %) |
| GR | `contracted` | `unbundled` | 102/102 (100 %) | 102/102 (100 %) |

Maut ist kunden-weit Fall A (unbundled) bei CHT — `Erlöse_Maut` zuverlässig gefüllt
für alle relevanten Länder. Maut-Delta für IT (9c.0): mean=−0,29 EUR, p50=0,000.

**9c.0 IT fp-Befund (pre_dlv_2026-Diagnose):**

| Cluster | n | fp-Bereich | Datum | Interpretation |
|---|---|---|---|---|
| fp ≈ 0,000 | 64 | ±0,001 | Jan–Mär 2026 | In-DLV exakter Match |
| fp ≈ −0,020 | 80 | −0,022 bis −0,018 | Okt–Dez 2025 | `pre_dlv_2026`: 2025-Raten ~2 % günstiger |
| fp ≈ +0,070 | 0 | — | — | Kein Muster-A bei CHT |

---

## §2a Positions-Level vs Sendungs-Level

### Hintergrund

Die **Abrechnungsstrecken**-Daten aus dem AX-System liefern je nach Datenquelle und
Kundenkonfiguration entweder:
- **Positions-Level:** Eine Zeile pro Auftragsposition (Auftragsnummer). Mehrere
  Positionen können zur selben Sendung (Ausgangsbordero) gehören.
- **Sendungs-Level:** Eine Zeile pro Sendung. Tonnage und Betrag sind bereits
  sendungsseitig aggregiert.

Der Unterschied ist **nicht sofort sichtbar** — beide Formate haben die gleichen
Spaltennamen. Erkennbar erst beim Quervergleich: mehrere Auftragsnummern auf
gleicher Rechnungsnummer/Ausgangsbordero → Positions-Level.

### GEZE-Befund (9b.3)

GEZE BI-Daten sind **Positions-Level**: 3.120 beurteilbare Positionen entsprechen
1.098 Gruppen nach Aggregation auf `Rechnungsnummer × Empfänger Land × PLZ-norm`.
Extremfall GB: 591 Positionen auf 8 Gruppen (Ø 74 Positionen/Gruppe, 2 eindeutige
Ausgangsbordero). Auf Positions-Ebene wäre `floater_pct` stark verzerrt
(Einzelminimumgebühren dominieren → fp ≈ −0,996).

### Aggregations-Key-Hierarchie

| Priorität | Key | Verwendbar wenn |
|---|---|---|
| 1 | `Ausgangsbordero` | Vorhanden und eindeutig pro Sendung |
| 2 | `Mastersendungs-Key` (RN × Land × PLZ-norm) | Ausgangsbordero fehlt oder dünn besetzt |
| 3 | `Position-Level mit Caveat` | Keine Aggregation möglich; fp-Werte als "unvalidiert" kennzeichnen |

**Aktuell (9b.3):** Aggregations-Key = Mastersendungs-Key (Rechnungsnummer ×
Empfänger Land × PLZ-norm), da `Ausgangsbordero` in den GEZE BI-Daten nicht
konsistent befüllt ist.

### Konsequenzen für Muster-A / Muster-B

- **floater_pct** und daraus abgeleitetes **Muster-A** sind nur auf
  **Sendungs-Ebene** belastbar. Auf Positions-Ebene (ohne Aggregation) sind alle
  fp-Werte als **unvalidiert** zu markieren.
- **Muster-B** (delta_raw < −10 EUR) reagiert empfindlich auf die
  Aggregationsebene: Eine große Sendung mit 50 Positionen, die korrekt
  abgerechnet wurde, kann auf Positions-Ebene 49× als Muster-B erscheinen
  (Einzelposition << DLV-Minimum der aggregierten Sendung).
- **Aggregationsartefakt-Flag (streng):** Muster-B-Kandidaten mit `n_pos > 5`
  und `fp > 0` auf Gruppenebene sind als "Aggregationsartefakt — Sendungs-
  Aggregation erforderlich" zu kennzeichnen und **nicht** als bestätigte
  Unterfakturierung zu werten. (GEZE 9b.3: GB/WS13 8SY, n_pos=27, fp=−0,395)
- **Aggregationsartefakt-Flag (weich):** Muster-B-Kandidaten mit
  `n_pos > 20 AND |delta_raw| < positions_min_fee × n_pos` sind als
  "Aggregation-Minimalgebühren-Verdacht — manuelle Sendungs-Disaggregation
  empfohlen" zu markieren. Hintergrund: Wenn eine Gruppe aus 30 kleinen
  Positionen besteht, von denen jede einzeln die DLV-Mindestgebühr ausgelöst
  hätte, ist der aggregierte Soll-Basispreis systematisch zu niedrig. Erst wenn
  `delta_raw_per_sendung > delta_raw_per_positions` kann auf echte
  Unterfakturierung geschlossen werden. Anwendungsfall: HERMA/Hornschuch-
  Rollouts mit vielen kleinen Positionen je Rechnungsempfänger.

### Pflichtfelder (ab v1.4)

| Feld | Werte | Bedeutung |
|---|---|---|
| `aggregation_level` | `sendung` \| `position` | Ebene der Billing-Kalkulation |
| `aggregation_key_source` | `bordero` \| `mastersendung` \| `position_group` \| `none` | Welcher Key für die Aggregation verwendet wurde |

Diese Felder sind in den Lane-Summary-CSVs ab 9b.3 implizit vorhanden
(9b.3 verwendet `mastersendung`-Key) und werden ab 9b.4 explizit ausgewiesen.

### Diesel/Maut-Modus pro (Kunde, Land) (ab v1.6)

Diesel und Maut sind **nicht kunden-global**, sondern **landen-spezifisch** vereinbart.
Innerhalb eines Landes gilt: entweder immer verrechnet (`contracted`) oder nie (`not_contracted`).

**Regel:**
```
diesel_mode(kunde, land) ∈ {"contracted", "not_contracted"}
maut_mode(kunde, land)   ∈ {"unbundled", "all_in"}
```

**Sanity-Check:**
- `diesel_mode = "contracted"` UND `Erlöse_Diesel = 0` in > 5 % der Zeilen
  → Flag `"diesel_expected_missing"` — manuelle Prüfung (Storno? Korrekturbuchung?)
- `diesel_mode = "not_contracted"` UND `Erlöse_Diesel > 0` in > 0 Zeilen
  → Flag `"diesel_unexpected"` — mögliche Falschbuchung

**Einzelfall-all_in-Ausnahme:** Innerhalb eines `(kunde, land)` mit
`diesel_mode = "contracted"` können einzelne Zeilen `Erlöse_Diesel = 0`
**und** `Erlöse_Maut = 0` aufweisen, während `Erlöse_Fracht` dem Gesamtbetrag
vergleichbarer Zeilen entspricht. Diese Zeilen erhalten das Flag
`pricing_mode: all_in_exception` — kein Datenfehler, sondern Buchungsformat-
Ausnahme (Fracht+Diesel+Maut in einem einzigen Fracht-Betrag gebündelt).

Schwelle: ≤ 1 % der Zeilen im `(kunde, land)`-Scope → Einzelfall-Ausnahme.
Bei > 1 %: keine Ausnahme mehr, sondern Hinweis auf strukturelle Änderung →
`diesel_mode` für diese Kombination neu evaluieren.

**Präzedenzfall CHT (9c.0 B-Check):** BE PE PLZ 8550 (0,78 % von 258 BE-Zeilen)
hat Diesel=0 und Maut=0 bei `Erlöse_Fracht = 167,91` ≈ Split-Gesamtbetrag
vergleichbarer Zeilen (PLZ 8560: 146,96+14,64+6,38 = 167,98). Flag
`all_in_exception` gesetzt.

**Präzedenzfall CHT (9c.0 B-Check):** BE und GR haben Diesel vereinbart (Erlöse_Diesel
immer > 0); IT, AT, ES, DE nicht (immer = 0). 2 BE-Zeilen ohne Diesel (von 258) →
Flag `"diesel_expected_missing"`, Einzelfall-Abweichungen (Storno/Korrektur), kein Blocker.

---

## §2b Billing-Scope (ab v1.8)

### Parameter `billing_scope`

Jeder Calculator deklariert einen `billing_scope`-Parameter, der beschreibt, auf
welcher Aggregationsebene die Tarifberechnung stattfindet:

| Wert | Bedeutung | Calculator-Signatur |
|---|---|---|
| `"position"` | Jede Position wird separat berechnet mit ihrer eigenen Rate-/Band-Zuordnung. Default für Single-Stage-Länder. | `calculate(empf_plz, tonnage_kg) → TariffResult` |
| `"rn"` | Alle Positionen einer Rechnungsnummer bilden ein Billing-Aggregat. HL und Maut einmalig pro RN; NL pro Empfänger-Gruppe. Resultat proportional zu `actual_kg` verteilt. | `calc_rn(list[RNPosition]) → dict[position_id → TariffResult]` |

### Prorating-Logik (`billing_scope = "rn"`)

```python
# Schritt 1: RN-Level-Berechnung
rn_total_kg   = sum(pos.actual_kg for pos in positions)
rn_billing_kg = max(100, ceil(rn_total_kg / 100) * 100)
rn_hl         = max(HL_MIN, min(HL_MAX, hl_rate(rn_billing_kg) * rn_billing_kg / 100))
rn_maut       = MAUT_PER_100KG * rn_billing_kg / 100

# Schritt 2: NL pro Empfänger-Gruppe
groups = group_by(positions, key='empfaenger_name')
for name, grp:
    grp_billing_kg = max(100, ceil(sum(p.actual_kg for p in grp) / 100) * 100)
    zone           = lookup_zone(grp[0].empf_plz)
    group_nl[name] = max(NL_MIN[zone], nl_rate(zone, grp_billing_kg) * grp_billing_kg / 100)

# Schritt 3: Prorating auf Positions-Ebene
hl_per_position   = rn_hl   × (tonnage_i / rn_total_kg)
maut_per_position = rn_maut × (tonnage_i / rn_total_kg)
nl_per_position   = group_nl[empfaenger_name_i] × (tonnage_i / group_total_kg)
```

### Empfänger-Gruppe

**Schlüssel: `(Rechnungsnummer, Empfänger_Name)` — nicht `(Rechnungsnummer, PLZ)`.**

Begründung (empirisch 9c.2c GR): Zwei Empfänger mit identischer PLZ 57013
(„Apothikes Makedonias", „TEX-FIN Sidiropoulou") erhalten separate NL-Berechnungen.
Gleicher Empfänger an selber PLZ (Baxevanidis S.A., 57022, verschiedene Positionen)
wird zu einer Gruppe zusammengefasst → eine NL-Berechnung.

### Bekannte `billing_scope`-Zuordnungen

| Kunde | Land | `billing_scope` | Belegt in |
|---|---|---|---|
| CHT Germany | IT | `position` | 9c.1 |
| CHT Germany | BE | `position` | 9c.2a |
| CHT Germany | ES | `position` | 9c.2b |
| CHT Germany | GR | `rn` | 9c.2c (empirisch \|Δ\|<0,001 EUR) |
| CHT Germany | AT | `position` | 9c.2d (empirisch \|Σ_Δ\|<0,002 EUR) |

### Retroaktiv-Empfehlung Welle-2/3

Bei HELU (Two-Stage-Depots), Hornschuch (29 Lane-Sheets), HERMA (VL-Split):
`billing_scope` muss in der Findings-First-Phase empirisch geprüft werden.
Schnelltest: Multi-Positions-RN identifizieren → Maut-Summe auf RN-Ebene vs
Position-Ebene vergleichen. Wenn RN-Maut = `0.XX × billing_kg(RN_total) / 100`
→ `billing_scope = "rn"`.

---

## §2c Gewichtsrundungs-Regel (ab v1.8.1)

### Parameter `kg_rounding_rule`

Pro `(Kunde, Land)`-Kombination wird eine `kg_rounding_rule` empirisch bestätigt,
die beschreibt, wie `actual_kg` vor dem Tarif-Band-Lookup behandelt wird:

| `kg_rounding_rule` | Formel | Bekannte Fälle |
|---|---|---|
| `"ceil_to_100"` | `billing_kg = max(100, ceil(actual_kg / 100) * 100)` | CHT/IT, CHT/BE, CHT/ES, CHT/GR (HL+NL) |
| `"actual_kg"` | `billing_kg = actual_kg` (direkt gegen Schwellen) | — |
| `"actual_kg_fracht_only"` | Fracht: `actual_kg` direkt; Maut: `ceil(actual_kg / 100) * 100` | CHT/AT |

### Strukturbefund CHT/AT (9c.2d)

AT-DLV enthält zwar die Angabe `"Gewichtsrundung: 100:100"`, diese gilt jedoch
**nur für die DE-Maut-Berechnung**, nicht für den Fracht-Band-Lookup:

```
# CHT/AT Fracht (kg_rounding_rule = "actual_kg_fracht_only"):
band = first band where actual_kg ≤ band.weight_limit
basispreis = band.flat_rate   # flat EUR pro Sendung, NICHT per-100kg

# CHT/AT Maut:
maut_kg    = max(100, ceil(actual_kg / 100) * 100)
maut       = 0.56 EUR × maut_kg / 100
```

Empirisch bestätigt: 32,10 kg → bis-50-Band → 40,1574 EUR (nicht 51,70 EUR
der bis-100-Band, die bei `ceil_to_100` entstünde).

### Wichtig: AT-Fracht ist FLAT, nicht per-100kg

Alle CHT/AT-Bänder sind `"pro Sendung"` (Pauschale), nicht `"per 100 kg"`:

| Band | Zone 6 Rate | Interpretation |
|---|---|---|
| bis 50 kg | 40,16 EUR | 40,16 EUR flat, egal ob 1 kg oder 50 kg |
| bis 100 kg | 51,70 EUR | 51,70 EUR flat für 50,001–100 kg |
| bis 600 kg | 144,51 EUR | 144,51 EUR flat für 500,001–600 kg |

Dies unterscheidet AT grundlegend von BE/ES/IT/GR (alle per-100-kg-Raten).

### Pflicht-Prüfpunkte vor Calculator-Build

Neben `ax_rate_precision` (§6c) und `billing_scope` (§2b) jetzt auch:
1. Ist `kg_rounding_rule` `ceil_to_100` oder `actual_kg(_fracht_only)`?
2. Sind Raten `flat` (pro Sendung) oder `per 100 kg`?
3. Gibt es Split-Raten (unterschiedliche Logik für Fracht vs. Maut)?

### Bekannte `kg_rounding_rule`-Zuordnungen

| Kunde | Land | `kg_rounding_rule` | Fracht-Einheit | Belegt in |
|---|---|---|---|---|
| CHT Germany | IT | `ceil_to_100` | per 100 kg | 9c.1 |
| CHT Germany | BE | `ceil_to_100` | per 100 kg (+ flat ≤100 kg) | 9c.2a |
| CHT Germany | ES | `ceil_to_100` | per 100 kg | 9c.2b |
| CHT Germany | GR | `ceil_to_100` | per 100 kg (HL+NL) | 9c.2c |
| CHT Germany | AT | `actual_kg_fracht_only` | flat per Sendung | 9c.2d |

---

## §2e Aggregations-Regel für Dinas-AX-Vergleich (ab v1.9)

### A — AX-Sub-Filter

`is_sub` wird ausschließlich über das Feld `Mastersendung` ("zusammengefasst in")
bestimmt. Kein Tonnage-Proxy. Sub-Zeilen werden nicht isoliert verglichen, sondern
in ihre Master-Zeile aggregiert.

```python
has_ms = df['Mastersendung'].apply(
    lambda v: bool(v and str(v).strip() not in ('', 'nan', 'NaN')))
has_ua = df['Unterauftrag'].apply(
    lambda v: bool(v and str(v).strip() not in ('', 'nan', 'NaN')))

is_sub        = has_ms & ~has_ua   # Sub-Zeile: Mastersendung gesetzt, kein eigener UA
is_master     = has_ua             # Master-Zeile: hat Unterauftrag
is_standalone = ~has_ms & ~has_ua  # Einzelzeile: kein Master, kein Sub
```

Vergleichs-Set = `is_master | is_standalone`.
Sub-Zeilen werden herausgefiltert; ihre Erlöse liegen auf der Master-Zeile.

**Implementations-Detail Sub-Klassifikation:**
Das AX-Feld `Unterauftrag` enthält eine Liste von Sub-Auftragsnummern als
**komma-separierter String** (z.B. `"7091200280103007, 7091200280104004"`),
nicht als numerischen Wert. Die Klassifikation muss mit einem String-Check
erfolgen (non-empty string nach Whitespace-Strip), nicht mit einem numerischen
Check. Ein numerischer Check (`float()`) würde auf komma-separierten Strings
mit `ValueError` scheitern und Master-Zeilen fehlerhaft als Sub klassifizieren.

`classify_ax_rows()` verwendet korrekt `_nonempty()` (string-check).
`_nonempty_numeric()` ist ausschließlich für physische Parameter relevant
(Tonnage, Lademeter etc.), wo numerische Gültigkeit über den Fallback entscheidet.

Empirisch bestätigt: Alle 586 GEZE-Master-Zeilen haben komma-separierte
Unterauftrag-Strings. Ein `float()`-Check hätte alle als Sub klassifiziert
(→ `docs/master_sub_empirical_patterns.md`).

### B — Dinas-Aggregation pro Rechnung

Die Aggregation erfolgt **rechnungsweise**. Innerhalb jeder Rechnung werden Positionen
mit gleichem `(Sender_PLZ, Empfänger_PLZ, Ladedatum)` zu einer Dinas-Aggregations-
Einheit zusammengefasst. Positionen aus verschiedenen Rechnungen werden **nie**
zusammengefasst.

```python
key = ['Rechnungsnummer', 'Sender_PLZ', 'Empfänger_PLZ', 'Ladedatum']
dinas_aggregat = dinas_pos.groupby(key, dropna=False).agg(
    n_positionen=('Rechnungsnummer', 'count'),
    gewicht_kg=('Gewicht_kg', 'sum'),
    lademeter=('Lademeter', 'sum'),
    stellplaetze=('Stellplätze', 'sum'),
    erloese_fracht=('Erlöse_Fracht', 'sum'),
    erloese_diesel=('Erlöse_Diesel', 'sum'),
    erloese_maut=('Erlöse_Maut', 'sum'),
).reset_index()
```

### C — Vergleich

Dinas-Aggregations-Einheit ↔ AX-Master-aggregierte Zeile.
Matching über `Sender_PLZ + Empfänger_PLZ + Ladedatum`.

Einzelsendungen (Dinas ohne gleich-geschlüsselte Partner in derselben Rechnung,
AX ohne Sub-Struktur) werden als Einzelvergleich gegen AX-Einzelzeilen geführt.

### D — Zweistufigkeit der AX-Filterung (ab v1.9.1)

`filter_comparison_set()` (Rule A) ist die **erste notwendige Stufe** — sie entfernt
Sub-Zeilen. Sie entfernt aber **nicht** unbeurteilbare Standalone-Zeilen
(Tonnage = 0 UND Lademeter = 0, §5.0).

Für jeden neuen Kunden-Rollout ist eine **zweite Stufe** obligatorisch:

```python
# Stufe 1: Sub-Rows entfernen (v1.9 §2e Rule A)
df = filter_comparison_set(df)

# Stufe 2: Unbeurteilbare entfernen (§5.0)
is_unbeurteilbar = (
    (pd.to_numeric(df['Tonnage (eff.)'], errors='coerce').fillna(0) <= 0) &
    (pd.to_numeric(df['Lademeter'],      errors='coerce').fillna(0) <= 0)
)
df_vergleich = df[~is_unbeurteilbar]
```

Die zweite Stufe wird bei bestehenden Kunden durch `enrich_master_sub()` oder
äquivalente Schutzlogik abgedeckt. Fehlt sie in neuen Scripts, landen
Standalone-Zeilen mit Tonnage = 0 im Calculator-Vergleich und produzieren
falsche Pass-Raten.

**Obligatorische Prüfpunkte bei jedem neuen Kunden-Rollout:**

| Prüfpunkt | Methode | Fehlermodus bei Fehlen |
|-----------|---------|------------------------|
| Stufe 1: `filter_comparison_set()` aktiv? | `is_sub` via Mastersendung | Sub-Erlöse fälschlich in Pass-Rate |
| Stufe 2: `~unbeurteilbar`-Filter aktiv? | Tonnage ≤ 0 AND LDM ≤ 0 | Tonnage=0-Zeilen scheitern im Calculator |

**Empirischer Befund (v1.9 Regression-Analyse):** Bei GEZE (153 FP), Fischerwerke
(63 FP) und HERMA (30 FN) wurden Proxy-Fehler durch `enrich_master_sub()` ohne
sichtbaren Pass-Rate-Effekt kompensiert. Ohne diese Schutzlogik wären signifikante
Pass-Rate-Verschiebungen aufgetreten (→ `docs/is_sub_regression_analysis.md`).

### E — Master-Rekonstruktion (ab v1.9.2)

Wenn eine Master-Zeile mit Sub-Zeilen in den Calculator eingespeist wird, gelten
folgende Vorrangregeln:

```
für jeden physischen Parameter (Tonnage, LDM, Stellplätze, Volumen, Colli):
    wenn master[feld] ist nicht NaN und nicht None:
        wert = master[feld]          # Master führt; 0 ist ein gültiger Wert
    sonst:
        wert = sum(sub[feld])        # Fallback nur bei leerem Master-Feld

für jeden Erlös-Parameter (Erlöse Fracht, Diesel, Maut, …):
    wert = sum(sub[erlös])           # Immer aus Subs — Master trägt keine Erlöse

Rechnungsnummern:
    rns = deduplizierte, sortierte Liste aller RNs aus Sub-Zeilen
```

**Inkonsistenz Master-Wert ≠ Sub-Summe ist kein Finding.** Sie ist strukturelle
Datenredundanz in AX (Master speichert aggregierte physische Parameter der
Gesamtsendung; Subs tragen die Einzel-Rechnungsbeträge).

Implementierung: `reconstruct_ax_master()` in `src/tms/billing/aggregation.py`.

```python
from tms.billing import reconstruct_ax_master

result = reconstruct_ax_master(
    master_row=master,   # pd.Series
    sub_rows=subs,       # pd.DataFrame
)
# result["Tonnage (eff.)"]   → master-Wert (falls vorhanden), sonst sum(subs)
# result["Erlöse Fracht"]    → sum(subs) immer
# result["rechnungsnummern"] → sortierte RN-Liste aus Subs
```

**Validierungsbeispiel (GEZE, Auftrag 7092010001835006):**

| Feld | Master | Sub-Summe (3 Subs) | Rekonstruiert |
|------|--------|--------------------|---------------|
| Tonnage (eff.) | **361,9 kg** | 0,0 kg | **361,9 kg** (Master führt) |
| Lademeter | 0,0 | 0,0 | 0,0 |
| Erlöse Fracht | 0,0 EUR | **97,28 EUR** | **97,28 EUR** (immer Subs) |
| Rechnungsnummern | — | 2557006-2 | `['2557006-2']` |

---

### F — Vergleichs-Cluster-Format (ab v1.9.4)

Definiert das Ausgabeformat für systematische AX-vs-Dinas-Vergleiche.

#### Vergleichseinheiten

| Seite | Einheit | Beschreibung |
|-------|---------|-------------|
| AX | Master-aggregierte Sendung | `reconstruct_ax_master()` Output (physisch Master-primär, Erlöse aus Sub-Summe) oder AX-Einzelsendung ohne Master |
| Dinas | Rechnungs-aggregierte Sendung | `aggregate_dinas_per_invoice()` Output: alle Positionen gleicher (RN, Sender-PLZ, Empf-PLZ, Datum) summiert |

#### Cluster-Key

```
(Sender-PLZ, Empfänger-PLZ, Tarifgruppe, Gewichtsklasse)
```

Gewichtsklasse basiert auf aggregierter Tonnage (Master-Ebene bei AX,
Rechnungs-Aggregat bei Dinas). Tarifgruppe entspricht dem DLV-Tarifzonenschlüssel
des Kalkulators.

#### Stichproben-Regel (Top-5 × Top-5)

Pro Cluster werden dargestellt:
- **AX-Seite:** Top-5 Einheiten nach größter Unterfakturierung (Δ = Ist − DLV-Soll,
  aufsteigend sortiert, d.h. negatives Δ zuerst)
- **Dinas-Seite:** Top-5 Einheiten nach Ähnlichkeit zum AX-Median im Cluster

Falls < 5 Einheiten: alle darstellen. Cluster ohne AX-Unterfakturierung werden
nicht in die Darstellung aufgenommen (Cluster-Ausschluss-Kriterium).

#### Ähnlichkeits-Score Dinas (kundenseitig)

Primär-Sortierung nach Abstand im **Billing-Basis-Parameter**, Sekundär-Sortierung
nach Gesamtgewicht:

```python
# billing_axis je Kunde:
# GEZE, EBM:       'kg_rechnung'      (Tonnage-Billing)
# Fischerwerke:    'stellplaetze'     (Stellplatz-Billing)
# HERMA:           'ldm'              (Lademeter-Billing)

dinas_sorted = dinas_cluster.assign(
    _dist=abs(dinas_cluster[billing_axis] - ax_median[billing_axis])
).sort_values(['_dist', 'kg_rechnung'])
top5_dinas = dinas_sorted.head(5)
```

#### Spalten-Struktur (identisch für AX- und Dinas-Tabelle)

```
Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ
```

- **Identifier:** Auftragsnummer (AX) oder Rechnungsnummer (Dinas)
- **NK_Total:** Summe aller Nebenkosten; Einzelaufschlüsselung im Anhang
- **DLV-Soll:** Für AX und Dinas berechnet via `calc.calculate(plz, land, tonnage_kg=kg)`.
  Tarif-Datum = `leistungsdatum` der Sendung für Phase-Bestimmung.
- **Δ:** `Fracht − DLV-Soll` (negativ = Unterfakturierung, positiv = Überfakturierung)

Beide Tabellen haben identische Spalten-Reihenfolge. Für Dinas ist DLV-Soll/Δ
vollständig berechnet (nicht leer) — ermöglicht `Dinas-Δ ≈ 0 / AX-Δ < 0`
als Root-Cause-Muster: Dinas hat korrekt abgerechnet, AX-Buchung fehlt oder
ist fehlerhaft.

#### Report-Struktur

```
1. Cluster-Übersicht (sortiert nach AX-Δ aufsteigend):
   Land | S-PLZ | E-PLZ | TarifGruppe | GewKlasse | n_AX | n_Dinas | Δ_AX | Δ% |

2. Pro Cluster (Detail):
   Cluster: [Land] | [S-PLZ→E-PLZ] | [Zone] | [Gewichtsklasse]
   AX-Unter-Delta: [EUR] | n_AX: [x] | n_Dinas: [y] | billing_axis: [Tonnage/LDM/Stp]

   AX-Sendungen (Top-5 Unterfakturierung):
   [Tabelle mit 13 Spalten]

   Dinas-Vergleich (Top-5 Ähnlichkeit):
   [Tabelle mit 13 Spalten]
```

#### Periodenversatz PRE-Dinas / POST-AX (strukturell)

Der Cluster-Vergleich ist als **Migrations-Audit** konzipiert: Dinas-Einheiten
stammen aus der PRE-Phase (Dinas-System), AX-Einheiten aus der POST-Phase
(AX-System). Dies ist kein methodisches Problem, sondern die Kernanforderung
des Audits.

> *"Die Dinas-Einheiten stammen aus der PRE-Migrations-Phase, die AX-Einheiten
> aus der POST-Migrations-Phase. Für jede Einheit wird das DLV-Soll anhand
> des zur jeweiligen Leistungsperiode gültigen Tarifs berechnet. Beide Δ-Werte
> sind damit innerhalb ihres Zeitraums tariftreu bewertet.*
>
> *Abweichungen zwischen Dinas-Erlös und AX-Erlös bei gleichen Cluster-Parametern
> sind nur dann durch Tarif-Änderung erklärbar, wenn eine solche Änderung zwischen
> dem gültigen PRE-DLV und dem gültigen POST-DLV dokumentiert ist. Ansonsten
> deuten sie auf AX-Konfigurations-Fehler hin."*

Periodenversatz-Hinweis ist im Cluster-Header explizit auszuweisen.

#### Root-Cause-Klassifikation (vier Muster)

| Muster | Dinas-Δ | AX-Δ | Diagnose |
|--------|---------|------|---------|
| 1 | ≈ 0 | ≈ 0 | Korrekt — Cluster nicht im Report (Ausschluss-Kriterium) |
| 2 | ≈ 0 | < 0 | **AX-Konfigurations-Fehler** — Dinas war korrekt, AX rechnet falsch |
| 3 | < 0 | < 0 | Tarif-Problem oder systematische Abweichung auf beiden Seiten |
| 4 | < 0 | ≈ 0 | Migration hat Unterfakturierung behoben (Dinas war bereits unter DLV) |

Pro Cluster ist das zutreffende Muster auszuweisen.

---

## §2f Pipeline-Integrations-Flow (ab v1.9)

Standardisierter Ablauf für alle AX-vs-Dinas-Vergleiche (generalisiert aus GEZE-Integration).

### Ablauf-Übersicht

```
AX-Rohdaten
    ▼
[1] classify_ax_rows()          → Spalten: is_sub, is_master, is_standalone
    ▼
[2] Sub-Rows trennen, Master-Gruppen bilden
    ▼
[3] reconstruct_ax_master()     → physisch: Master-primär; Erlöse: Sub-Summe (§2e Rule E)
    ▼
[4] Vergleichs-Set: rekonstruierte Master + Standalones zusammenführen
    ▼
[5] Stage-2-Filter ~unbeurteilbar: Tonnage ≤ 0 AND LDM ≤ 0 (§2e Rule D)
    ▼
[6] Dinas-Matching: aggregate_dinas_per_invoice() + Routing-Key-Join (§2e Rule C)
    ▼
[7] Calculator + Muster-A/B-Erkennung + §8-Kandidaten
```

### STOP-Kriterien mid-Integration

| Trigger | Nach Schritt | Konsequenz |
|---------|-------------|------------|
| Scope-Δ > 5 kEUR nach Sub-Exclusion | 5 | STOP — methodische Abstimmung |
| > 3 Muster-B-Kandidaten sind Sub-Rows | 2 | STOP — Findings-Review |
| > 5 % der Master: `reconstruct_ax_master()` liefert NaN | 4 | Datenproblem untersuchen |
| Stage-2-Filter entfernt > 200 Zeilen | 6 | STOP — Legitimität prüfen |

**Wichtig (§2e Rule A):** `Unterauftrag` ist ein String-Feld (komma-separierte Liste).
`_nonempty()` (string-check) verwenden, nicht `float()` — sonst werden Master fälschlich
als Sub klassifiziert. Empirisch bestätigt an 586 GEZE-Master-Zeilen.

Detaillierter Schritt-für-Schritt-Flow mit Datentypen: `docs/v1_9_pipeline_integration_flow.md`

---

## §2g Billing-Axis-Tabelle per Kunde (ab v1.9.4)

Definiert die primäre Billing-Dimension für Cluster-Ähnlichkeits-Scores (§2e Rule F)
und DLV-Kalkulationen. `billing_axis` bestimmt, nach welchem Merkmal Dinas-Einheiten
zum AX-Median sortiert werden.

| Kunde | KNR | `billing_axis` | Einheit | Tarifbasis |
|-------|-----|----------------|---------|------------|
| GEZE GmbH | 406035 | `tonnage` | kg | EUR/100 kg pro Zone |
| EBM-Papst | 410844 | `lademeter` | LDM | Stellplatz-Matrix (1 Stp = 0,4 LDM) |
| Fischerwerke | 409480 | `stellplaetze` | Stp | Stellplatz-Pauschal |
| HERMA GmbH | 423650 | `ldm` | LDM | LDM-Progressiv |
| CHT Germany | 486073 | `tonnage` | kg | EUR/100 kg pro Zone |
| Sika DE | 491063 | `tonnage` | kg | EUR/100 kg |

**Pflicht vor Kunden-Rollout:** `billing_axis` empirisch bestätigen:
1. §5.0 `tonnage_source`-Prüfung (Gate-1: ≤ 20 % Tonnage=0)
2. BI-Daten: welche Spalte hat die geringste Null-Quote?
3. DLV-Kalkulator-Parameter: welche Dimension ist der Pflicht-Eingabe?

---

## §3 Muster-A-Erkennung

### Definition
Muster-A = **Fester ERKA-Indexaufschlag** von exakt 7,00 % auf den DLV-Basistarif
(nicht Teil des DLV, sondern separates Rider-Dokument / Email-Vereinbarung).

### Erkennungsformel
```
# Standard (BI-Daten, ab v1.5):
floater_pct = (Erlöse_Fracht − basispreis) / basispreis
muster_a    = abs(floater_pct - 0.07) < 0.0015

# EBM-Sonder-Block (Abrechnungsstrecken-Quelle, kein Erlöse_Fracht):
floater_pct = (betrag − toll) / tariff − 1
# betrag = Fracht+Floater; toll = DLV-Maut; tariff = DLV-Tarif
# Retroaktiv offen: ob Diesel in betrag eingebettet (→ §7 EBM-Diesel)
```

**Begründung für floater_pct-Basis (nicht Ratio-Basis):**

Die nahe liegende Alternative — `ratio = Erlöse_Fracht / basispreis` mit Fenster
`[1.0645, 1.0755]` — ist **zu breit** und erzeugt Falsch-Positive:
- PL-Zeilen März 2026 haben einen variablen Diesel-Floater von ~8,1 %
- Deren Ratio fällt ebenfalls in das Fenster, obwohl es sich um regulären
  Dieselzuschlag (kein ERKA-Indexaufschlag) handelt
- Der floater_pct-Ansatz (`Erlöse_Fracht − basispreis`) trennt sauber: Diesel
  ist in §2.0 aus `floater_pct` herausdefiniert; 7,00 % ± 0,15 % = ERKA-
  Indexaufschlag; Diesel-Floater erscheint ausschließlich in `diesel_delta`

**Kreuzvalidierung:** Alle 50 bestätigten Muster-A-Zeilen liegen im Januar 2026
und stammen aus 5 Lanes (IE/PL/EE/SK/HR) — konsistent mit einem systemweiten
Aktivierungsdatum.

### Kundenbelegte Muster-A-Funde (Stand 9b.0)

| Kunde | KNR | Aktivierungsmonat | n Zeilen | Lanes |
|---|---|---|---|---|
| Fischerwerke | 409480 | März 2026 | ~31 | IT-Padova, IT-Copiano, FR, GB |
| EBM-Papst | 410844 | Januar 2026 | 50 | IE, PL, EE, SK, HR |
| GEZE GmbH | 406035 | nicht nachweisbar (9b.3) | 0 | kein Treffer in POST-Daten |
| CHT Germany | 486073 | offen (9c.3) | — | alle Lanes zu prüfen |

Unterschiedliche Aktivierungszeitpunkte pro Kunde deuten auf kundenspezifische
Vereinbarungen hin — gleicher Mechanismus, unterschiedliches Roll-out-Datum.
GEZE zeigt keinen Muster-A-Befund in POST-Daten (mögliches Roll-out nach April 2026
oder keine ERKA-Vereinbarung).

---

## §3a Sonder-PLZ-Aufschlag (ab v1.7.1)

### Definition

Ein **Sonder-PLZ-Aufschlag** ist ein PLZ-spezifischer Festaufschlag auf den
DLV-Basispreis, der **nicht im DLV-Dokument ausgewiesen** ist. Er erscheint als
konsistenter positiver `fp`-Wert bei ≥ 2 Positionen derselben PLZ, während andere
PLZs desselben Kunden/Landes keinen oder geringen fp zeigen.

**Abgrenzung zu Muster-A:**

| Merkmal | Muster-A | Sonder-PLZ-Aufschlag |
|---|---|---|
| Granularität | Kunden-/Lane-übergreifend | PLZ-spezifisch |
| Wert | exakt +7,00 % ± 0,15 % | variabel +6–8 % (beobachtet) |
| Ursache | ERKA-Indexvereinbarung | Thermo-/Sondergebiets-/Gefahrgut-Zuschlag |
| Erkennung | abs(fp − 0.07) < 0.0015 | ≥ 2 Pos. derselben PLZ, abs(fp − fp_plz) < 0.005 |

### Erkennungsregel

```python
# Pro (Kunde, Land, PLZ): wenn ≥ 2 Positionen mit fp-Konsistenz
plz_fp_mean = mean(fp für Positionen mit dieser PLZ)
plz_fp_std  = std(fp für Positionen mit dieser PLZ)
if plz_fp_std < 0.005 and abs(plz_fp_mean) > 0.03 and n >= 2:
    flag = "sonder_plz_aufschlag"
```

Positionen mit `sonder_plz_aufschlag` werden als **§8 (Klärungsfrage)** markiert,
nicht als bestätigte Billing-Abweichung. Hypothese: Thermozuschlag,
Gefahrgut-Handling oder PLZ-gebundener Sondertarif, der im DLV-Basispreis
fehlt — mögliche Calculator-Lücke.

**Retroaktiv-Check bei HELU/HERMA/Hornschuch:** PLZ-Cluster mit fp > 0.03 und
Std < 0.005 prüfen. Falls gefunden: §8-Eintrag analog zu den CHT-Fällen.

### Bekannte Sonder-PLZ-Fälle (Stand 9c.2a)

| Kunde | Land | PLZ | fp | n | Hypothese |
|---|---|---|---|---|---|
| CHT | IT | 20098 | +0,061 | 3 | Thermozuschlag Sesto Ulteriano / Milan |
| CHT | BE | 8540 | +0,063 | 1 | Thermozuschlag Kortrijk-West / Westflandern |
| CHT | BE | 8560 | +0,063 | 1 | Thermozuschlag Kortrijk-West / Westflandern |
| CHT | BE | 8400 | +0,064 | 1 | Thermozuschlag Kortrijk-West / Westflandern |

Alle drei BE-PLZ liegen im Großraum Kortrijk (Westflandern) und zeigen
konsistent +6,3–6,4 %. Zusammen mit IT/20098 (+6,1 %) deutet das auf
einen **Thermo-/Sondergebietszuschlag von 75 EUR** hin, der auf den
DLV-Basispreis prozentual skaliert wirkt, aber im DLV-Dokument nicht
aufgeführt ist.

**Sonderfall 924248/PLZ 7700 (+18,7 %, 1 Position):** Abweichend von den
+6 %-Fällen — zu hoch für Sonder-PLZ-Aufschlag, zu konsistent für Rauschen.
Mögliche FTL-/Gefahrgut-/Priority-Sondertarifebene. Im 9c.4-Report als
eigenständige Prioritäts-§8-Position, nicht mit Sonder-PLZ-Fällen zusammengeführt.

### AX-Raten-Präzision (Hinweis ab v1.7.1)

AX speichert DLV-Tarifsätze möglicherweise mit reduzierter Dezimalstellenpräzision
(2dp statt 4dp des DLV-Dokuments). Dieses Muster wurde für CHT/BE bestätigt, für
CHT/IT nicht (IT-Raten in AX: volle 4dp-Präzision). Konsequenz:

- **Pro Land validieren:** Integration-Test zeigt, ob AX-Raten 2dp oder 4dp haben.
  Indikation: Systematisches fp ≈ −0,0002 (nicht zufällig) bei `exact_dlv`-RNs.
- **Calculator anpassen:** Wenn AX 2dp speichert, Calculator-Raten auf 2dp runden
  (damit ±0,01-EUR-Kriterium anwendbar bleibt).
- **§8-Dokumentation:** "AX speichert <Land>-Tarifsätze mit 2 Dezimalstellen;
  DLV notiert 4dp. Calculator folgt AX-Präzision. KLÄRUNGSFRAGE: 2dp vertragskonform?"
- **Retroaktiv-Prüfung:** Für alle weiteren CHT-Länder (AT/ES/GR) und Welle-3-
  Kunden im Integration-Test prüfen, ob AX-Präzision 2dp oder 4dp.

---

## §3b Empirische Master-Sub-Muster (ab v1.9.2)

Beschreibt, wie physische Parameter und Erlöse zwischen Master- und Sub-Zeilen in AX
verteilt sind. Empirisch bestätigt an GEZE (586 Master), Fischerwerke (109), HERMA (183), CHT.

### Normalmuster: Physische Parameter

| Feld | Master | Sub | Muster |
|------|--------|-----|--------|
| Tonnage (eff.) | Immer vorhanden | Meist 0 | **Master führt** |
| Colli | Immer vorhanden | Meist 0 | Master führt |
| Lademeter | Manchmal leer (Fischerwerke: 29 %) | Manchmal gefüllt | Fallback greift bei LDM |
| Stellplätze | Meist vorhanden | Manchmal gefüllt | Master führt; Fallback möglich |
| Erlöse Fracht | Meist 0 (Artefakte) | Prädominant | **Immer Sub-Summe** |
| Erlöse Diesel | Meist 0 | Auf Subs | Immer Sub-Summe |

### Fallback-Relevanz per Kunde

| Kunde | Fallback-Häufigkeit | Praktische Relevanz |
|-------|---------------------|---------------------|
| GEZE | **Nie** (0/586 Gruppen) | Irrelevant; defensiver Safety-Catch |
| HERMA | **Fast nie** (2/183) | Marginal; 2 FP-Subs werden gefiltert |
| Fischerwerke | **Lademeter: ~29 %** (32/109) | Methodisch sinnvoll für LDM |
| CHT | **n/a** | Kein Master-Sub-Pattern in BI-Daten; reconstruct nicht anwendbar |

**Schlussfolgerung:** `reconstruct_ax_master()` ist für GEZE und HERMA ein defensiver
Safety-Catch (nie ausgelöst). Bei Fischerwerke ist der LDM-Fallback methodisch korrekt.

**Neue Kunden:** Vor Integration 5–10 Master-Sub-Gruppen prüfen und in diese Tabelle eintragen.
Datenbasis: `docs/master_sub_empirical_patterns.md`

---

## §3c Orphan-Sub-Pattern (ab v1.9.2)

### Definition

Ein **Orphan-Sub** ist eine Sub-Zeile, deren `Mastersendung`-Wert auf eine Zeile zeigt,
die im Datensatz als **Standalone** klassifiziert ist — d.h. die Ziel-Zeile hat kein
`Unterauftrag`-Feld gesetzt und führt keine eigene Master-Gruppe.

### Ursache

AX kann Sendungen als "Teil einer Mastersendung" markieren, ohne dass die Ziel-Auftragsnummer
im vorliegenden Export eine eigene Master-Gruppe führt. Typische Ursachen:
- Ziel liegt in anderem Abrechnungszeitraum / gefiltertem Export-Scope
- Einzelsendung, die nachträglich als Master referenziert wurde

Kein Bug in `classify_ax_rows()` — Datenmerkmal des AX-Exports.

### Empirischer Befund: GEZE (v1.9.2)

28 von 153 FP-Sub-Zeilen sind Orphan-Subs (Mastersendung zeigt auf 4 Standalone-Zeilen):

| Standalone-Auftragsnummer | Land/PLZ | n Orphan-Subs | Erlöse Fracht |
|---------------------------|---------|---------------|---------------|
| 7092010011403004 | GB/WS13 8SY | 5 | 228,84 EUR |
| 7092010011404001 | GB/WS13 8SY | 19 | 1.607,60 EUR |
| 7092010012046002 | FR/72700 | 2 | 147,18 EUR |
| 7092010030068000 | IT/38121 | 2 | 1.263,36 EUR |
| **Gesamt** | | **28** | **3.246,98 EUR** |

### Behandlung im v1.9-Framework

`filter_comparison_set()` entfernt Orphan-Subs korrekt (is_sub = True).
Die Erlöse der Orphan-Subs können **nicht** auf einen Master rekonstruiert werden.

**Konsequenz für Bilanz-Null-Check:** Deckungsgrad strukturell < 100 % wenn Orphan-Subs
vorhanden. Abweichung durch Orphan-Subs ist als **Datenmerkmal** zu dokumentieren,
nicht als Algorithmus-Fehler. GEZE: −4.279 EUR (75,7 % Deckung) = erwartet.

### Pflicht-Check bei neuen Kunden

Wenn Bilanz-Null-Check < 95 %: Orphan-Sub-Analyse durchführen:
```python
standalone_keys = set(standalones['Auftragsnummer'].apply(
    lambda v: round(float(v)) if pd.notna(v) else None
).dropna())
orphans = subs[subs['Mastersendung'].apply(
    lambda v: round(float(v)) in standalone_keys if pd.notna(v) else False
)]
print(f"Orphan-Subs: {len(orphans)}, EUR: {orphans['Erlöse Fracht'].sum():.2f}")
```

---

## §4 Muster-B-Erkennung

### Definition
Muster-B = **Echte Unterfakturierung** — abgerechneter Betrag liegt deutlich
unterhalb des DLV-Erwartungswerts (tariff + toll) ohne erklärendes Floater-Muster.

### Erkennungsformel
```
delta_raw = betrag - (tariff + toll)
muster_b  = delta_raw < -10.0          # EUR
```

Der Schwellwert −10 EUR filtert Rundungsartefakte heraus.

### Bestätigte Muster-B-Funde (Stand 9a.4.2)

| Kunde | Lane | Datum | n_stpl | Betrag | Erwartet | Delta |
|---|---|---|---|---|---|---|
| EBM-Papst | EE-Lehmja | 2025-12-08 | 2 | 159,60 € | 260,00 € | −100,40 € |

Hypothese: Abrechnung erfolgte auf Basis von Stellplatz 1 statt Stellplatz 2
(159,60 € ≈ tariff[EE-75301][1] × 1.064).

---

## §5 Billing-Dimension-Ermittlung

### §5.0 Pflichtfeld `tonnage_source` und Audit-Schwelle

Jede beurteilte Zeile muss ein Pflichtfeld `tonnage_source` (bzw. allgemein
`billing_dim_source`) führen, das dokumentiert, woher die Billing-Dimension
(Tonnage, Stellplätze, LDM) stammt:

| Wert | Bedeutung |
|---|---|
| `direct` | Wert direkt aus Abrechnungsstrecken-Spalte, plausibel (>0) |
| `ldm_fallback` | Tonnage=0, Wert aus LDM abgeleitet (EBM-Konvention) |
| `unbeurteilbar` | Tonnage=0 UND LDM=0 → keine Billing-Basis vorhanden |

**20 %-Audit-Schwelle:** Wenn `unbeurteilbar`-Anteil > 20 % der Core-Zeilen,
ist der Befund mit einem Gate-Hinweis zu versehen. Der Befund ist **nicht gesperrt**
— die beurteilbaren Zeilen werden normal ausgewertet — aber der Report muss die
Lücke explizit ausweisen.

**GEZE 9b.2 Befund:** 1.109/4.349 Zeilen (25,5 %) haben Tonnage=0 und LDM=0.
Alle sind `unbeurteilbar`. Gate-1-Hinweis ist aktiv; 3.120 Zeilen (71,7 %) bleiben
für 9b.3 beurteilbar. Ursache der Tonnage=0-Zeilen ist unklar (möglicherweise
Positions-Aggregationsartefakt im AX-Export); Klärung bei ERKA/IT offen.

### Direkt aus Abrechnungsstrecken
Bevorzugte Quelle: Spalte `Abrechnungsstellplätze` (integer) bzw. `Tonnage (eff.)`.

### §5a LDM-Fallback bei NaN-Stpl

**Hintergrund:** In den EBM-Abrechnungsstrecken haben 165/397 Zeilen (41,6 %) den
Wert `NaN` in `Abrechnungsstellplätze`. Diese Zeilen haben aber gültige
`Abrechnungslademeter`-Werte. Ohne Fallback wären sie `unbeurteilbar`.

**Formel:**
```python
if pd.isna(stpl) and not math.isnan(ldm):
    n_stpl = max(1, math.ceil(ldm / 0.4))
n_stpl = max(1, min(n_stpl, 33))   # auf DLV-Maximum kappen
```

**Umrechnungsregel:** 1 Stellplatz = 0,4 LDM (EBM-Papst DLV-Konvention).

**Effekt:** Unbeurteilbar-Zeilen sinken von 208 → 58 (−75 %).

**Betroffene Routen (EBM 9a.4.2):**

| Route | NaN-Stpl / gesamt | LDM-Beispiel | abgeleiteter Stpl |
|---|---|---|---|
| Warszawa (Białołęka) | 74 / 82 | 13,6 | 34 → cap 33 |
| Senica | 40 / 47 | variabel | 1–33 |
| Buje | 16 / 23 | variabel | 1–33 |
| Lehmja | 3 / 23 | variabel | 1–33 |
| Logatec | 2 / 3 | variabel | 1–33 |

**Hinweis:** Diese Formel ist auf alle LDM-basierten DLV-Kunden übertragbar (z. B.
künftige HERMA-, CHT-Analyse), sofern die Konvention 1 Stpl = 0,4 LDM gilt.

---

## §6 DLV-Versions-Fallback

Bei Zeilen im Zeitfenster `in_dlv_2025` (10.10.2025 – 28.02.2026) wird zuerst das
DLV vom 10.10.2025 geprüft. Falls die Route dort nicht vorhanden ist (z. B. GB,
F92/Rathmullan), wird auf das aktuellste verfügbare DLV (`fallback_latest`) zurück-
gegriffen. Zeilen ohne jede DLV-Abdeckung erhalten `dlv_fallback = 'no_dlv'` und
fließen nicht in Calculator-Checks ein.

---

## §6a Sanity-Gates für Calculator-Binnentests

Ein Calculator gilt erst dann als **validiert**, wenn alle fünf Gates bestanden sind:

| Gate | Prüfung | Fehlermodus |
|---|---|---|
| 1 | Mindest-Abdeckung: ≥ 2 Fälle pro Land/Zone-Kombination | Blind Spots in Zonen-Lookup |
| 2 | Minimum-Floor: mind. 1 Fall, der durch das Minimum gedeckelt wird | Minimum-Logik nie aktiviert |
| 3 | Rate-Bereich: mind. 1 Fall mit rate×billing_kg > minimum | Rate-Berechnung nie aktiv |
| 4 | Gewichtsband-Grenze: mind. 1 Fall exakt auf einer Band-Grenze (z. B. billing_kg=300) | Off-by-one in Band-Lookup |
| 5 | **Bedingte Komponenten nicht-null**: Alle optionalen Surcharges/Floater/Währungen müssen in mind. 1 Testfall einen Wert > 0 liefern | Stille Nullen durch Parser-Bug |

**Gate 5 — Hintergrund (Präzedenzfall GEZE 9b.1):**

Etappe 5e validierte den GEZE-Calculator mit 6/6 grünen Tests. Der CHF-Floater
schien zu funktionieren. Tatsächlich las `_parse_chf_floater` Spalten 0–3 statt
der korrekten 2–5, lieferte eine leere Tabelle, und `chf_amount` war immer 0.
Die 6 Testfälle enthielten einen CH-Fall mit Rate 1.065 — der fällt in das
Null-Prozent-Band (≥ 1.021), sodass auch mit korrektem Parser `chf_amount=0`
erwartet worden wäre. Grüner Test, falscher Grund.

**Konsequenz für künftige Calculator-Validierungen:**

| Calculator | Bedingte Komponente | Gate-5-Testanforderung |
|---|---|---|
| GEZE | CHF-Floater | mind. 1 CH-Fall mit CHF/EUR < 1.021 (nicht-null Band) |
| HERMA | VL-Aufschlag (Vorlauf) | mind. 1 Fall mit VL > 0 |
| HELU | Country-Fallback | mind. 1 Fall, der Fallback auslöst |
| CHT | Dual-Mode-Umschalt + Maut | mind. 1 Fall per-Sendung + 1 Fall per-100kg + 1 Fall mit Maut-Delta ≠ 0 |
| Hornschuch | Formel-Varianten | mind. 1 Fall je Formelzweig |

---

## §6c AX-Raten-Präzisions-Check (Pflichtschritt ab v1.7.2)

### Motivation

AX (Microsoft Dynamics) speichert Tarifraten nicht notwendigerweise mit voller
DLV-Präzision. CHT/IT-Raten sind nativ 4-stellig in AX; CHT/BE-Raten werden
mit 2 Dezimalstellen gespeichert (z. B. DLV-Rate 10.7120 → AX: 10.71).
Wenn der Calculator volle DLV-Präzision benutzt, entstehen systematische
Deltas für große Tonnagen (z. B. ×21 Hundertergewicht × 0.002 = 0.042 EUR
überschreitet das ±0.01-Kriterium).

### Pflicht-Vorgehensweise vor jedem neuen Calculator-Build

Für jede neue (Kunde, Land)-Kombination:

**Schritt 1 — DLV-Rate ablesen**
```
Aus DLV-Excel-Datei: 3–5 Bänder notieren (4dp exakt)
```

**Schritt 2 — AX-Rate rückrechnen**
```python
# Für 3–5 BI-Beispielrechnungen:
ax_implied_rate = erloes_fracht / (billing_kg / 100)
# Vergleich mit DLV-Rate:
#   ax_implied_rate ≈ dlv_rate          → "native" (volle Präzision)
#   ax_implied_rate ≈ round(dlv_rate,2) → "2dp"
#   Sonstiges                           → "other" (Klärungsfrage §8)
```

**Schritt 3 — ax_rate_precision festlegen**

| Befund | ax_rate_precision | Calculator-Konsequenz |
|---|---|---|
| AX-Rate = DLV-Rate (volle dp) | `"native"` | Keine Rundung, DLV-Rate direkt |
| AX-Rate = round(DLV-Rate, 2) | `"2dp"` | `round(float(col2), 2)` in `_parse_bands()` |
| AX-Rate = round(DLV-Rate, 3) | `"3dp"` | `round(float(col2), 3)` in `_parse_bands()` |
| Kein klares Muster erkennbar | `"other"` | §8-Klärungsfrage, Calculator verwenden und Befund dokumentieren |

**Schritt 4 — Dokumentation in Calculator-Docstring**

```python
"""
...
AX-Raten-Präzision: <ax_rate_precision>  (empirisch geprüft, 9c.2x)
  DLV nativ: <beispiel_4dp>  →  AX gespeichert: <beispiel_ax_dp>
  §8-Hinweis: "AX speichert <Land>-Raten mit <precision>. Calculator folgt AX-Praxis."
"""
```

### Bekannte Befunde

| Kunde | Land | ax_rate_precision | Belegt in | Referenz |
|---|---|---|---|---|
| CHT Germany | IT | `native` (4dp) | 9c.1: 63/63 match | 9c.2a IT-Retroaktiv-Check |
| CHT Germany | BE | `2dp` | 9c.2a: 65/65 match nach Rundung | Backrechnung 924035/924148 |
| CHT Germany | ES | `2dp` | 9c.2b: 28/30 match | Backrechnung Zone-1-Raten |
| CHT Germany | GR | `2dp` | 9c.2c: HL/NL |Δ|<0,001 | Backrechnung RN 4251017331/4251019887 |
| CHT Germany | AT | `2dp` | 9c.2d: all \|Δ_pos\|<0,004 | Backrechnung Schritt-1 Spot-Check (4 RNs, 9 Pos.) |

### Zeitbezug-Befund CHT/BE rn_level_adjustment (§8-Daten)

Aus Etappe 9c.2a, Gate-6-Klassifikation — Abrechnungsdaten der 4 adjustment-RNs
versus 4 exact_dlv-RNs:

| RN | Kategorie | Leistungsdaten | Monat | factor |
|---|---|---|---|---|
| 924035 | exact_dlv | 2026-01-12–13 | 2026-01 | 0.0000 |
| 924069 | rn_adj | 2026-01-12–19 | 2026-01 | −0.0069 |
| 924081 | rn_adj | 2026-01-19–23 | 2026-01 | +0.0296 |
| 924102 | rn_adj | 2026-01-27–30 | 2026-01 | +0.0050 |
| 924148 | exact_dlv | 2026-02-09–12 | 2026-02 | 0.0000 |
| 924187 | exact_dlv | 2026-02-16–20 | 2026-02 | 0.0000 |
| 924225 | exact_dlv | 2026-02-24–03-02 | 2026-02/03 | 0.0000 |
| 924234 | rn_adj | 2026-03-02–06 | 2026-03 | +0.0042 |

**Befund**: Kein sauberes temporales Clustering. Januar 2026 enthält sowohl
exact_dlv (924035) als auch drei rn_adj-RNs. Februar 2026 ist vollständig exact_dlv.
März 2026 hat einen rn_adj-Ausreißer (924234). Die Faktoren variieren pro RN
(−0.69% bis +2.96%) ohne erkennbares Muster.

**Konklusion**: Hypothese "AX-Konfigurations-Drift pro Abrechnungsperiode" nicht
bestätigt. Mechanismus unbekannt. Klärungsfrage an Operations/Fachabteilung
(Abrechnungskorrektur? Manuelle Nachbuchung? Konditionsübersteuerung im AX-System?).

---

## §6b RN-Level-Faktor-Detection (Gate 6, ab v1.7)

### Motivation

In einigen Kunden-Ländern (erstmals CHT/BE, 9c.2a) weichen die tatsächlichen
Erlöse_Fracht-Werte systematisch vom 2026-DLV ab — aber nicht über alle Zeilen
gleichmäßig, sondern **pro Rechnungsnummer (RN) konsistent**. Das heißt: innerhalb
eines RN haben alle Positionen denselben relativen Abstand zum berechneten
Basispreis. Ursache: unbekannter Mechanismus auf Rechnungsebene (möglicherweise
eine quartalsbezogene Frachtraten-Anpassung, die in AX je Invoice-Batch
unterschiedlich eingestellt wurde).

Dieses Muster ist **kein Calculator-Bug** und **kein Muster-A-Treffer** — es ist ein
strukturelles Billing-Artefakt, das vor der Pass-Rate-Berechnung identifiziert und
separat ausgewiesen werden muss.

### Abgrenzung zu anderen Mustern

| Muster | Granularität | Wert | Richtung | Bedeutung |
|---|---|---|---|---|
| Muster-A | Lane-übergreifend | exakt +7,00 % ± 0,15 % | positiv | ERKA-Indexaufschlag |
| RN-Level-Faktor | pro RN | beliebig (beobachtet: −0,7 % bis +3,0 %) | positiv oder negativ | Unbekannter RN-Mechanismus |
| Rundungsartefakt | pro Position | < 0,01 EUR absolut | beliebig | Dezimalstellen-Differenz |
| Aggregationsartefakt | pro Gruppe | fp > 0 bei n_pos > 5 | positiv | Sendungs-Ebene fehlt |

### Classifier-Logik (Gate 6)

Vor der Pass-Rate-Berechnung wird **pro RN** geprüft:

```python
rn_factor = median(erloes_fracht / basispreis)   # ≈ 1 + fp
rn_std    = std(erloes_fracht / basispreis)

if rn_std < 0.0005:                        # alle Positionen im RN gleichmäßig
    if abs(rn_factor - 1.0) < 0.0005:     # Faktor ≈ 1 → exaktes DLV
        flag = "exact_dlv"                 # → zählt in Pass-Rate
    else:
        flag = "rn_level_adjustment"       # → aus Pass-Rate exkludiert
else:                                      # heterogene Abweichungen im RN
    flag = None                            # → per-Position ±0.01 EUR Check
```

**Pass-Kriterium (Gate 6):** ≥ 90 % der Positionen mit `flag is None` oder
`flag == "exact_dlv"` haben `|Erlöse_Fracht − basispreis| ≤ 0,01 EUR`.

Positionen mit `flag == "rn_level_adjustment"` werden:
1. **Aus dem Pass-Rate-Zähler exkludiert** (weder Zähler noch Nenner)
2. **Im §8-Abschnitt des Kunden-Reports gelistet** (pro RN: Faktor, n, delta_sum)
3. **Nicht als Unterfakturierung gewertet**, solange keine Kontext-Information
   (z. B. ein abweichendes Sonder-DLV) vorliegt

### §8-Listenformat für RN-Level-Adjustment-Fälle

```
RN <xxx>: rn_factor=<f>, n=<n>, delta_sum=<EUR>
  → Faktor <f-1:+.2%> auf alle <n> Positionen
  → Hypothese: [quarterly_fracht_adjustment | AX_config_drift | andere]
  → Priorität: [hoch (|f-1| > 2%) | mittel | niedrig]
```

**CHT/BE 9c.2a Befund:**

| RN | rn_factor | n | delta_sum | Prio |
|---|---|---|---|---|
| 924081 | 1.0295 | 11 | +49,8 EUR | hoch (Overbilling) |
| 924248 | 1.0290 | 13 | +60,0 EUR | hoch (Overbilling) |
| 924069 | 0.9931 | 16 | −20,6 EUR | niedrig (Underbilling) |
| 924102 | 1.0050 | 7 | +7,6 EUR | mittel |
| 924234 | 1.0042 | 14 | +6,9 EUR | mittel |
| 924132 | gemischt | 20 | variabel | §8 pos-Level |

### Retroaktiv-Anwendung auf Welle-1/2 Kunden

Gate 6 muss **retroaktiv** auf alle abgeschlossenen Calculator-Tests angewendet
werden, sobald der zugehörige Kunden-Report erstellt wird. Indikation für
RN-Level-Adjustments:
- `rn_std < 0.0005` in mehr als 20 % der RNs im Testset
- Systematische fp-Cluster in der Verteilung (Bimodalität oder Multimodalität)

GEZE (9b.3): Muster-A-Treffer: 0. Aggregationsartefakt-Flags gesetzt für GB.
→ Kein RN-Level-Adjustment erkannt. Gate 6 retroaktiv: bestanden.

---

## §7 Altzahl-Validierung und Retroaktiv-Liste

### EBM-Papst — Revision 9a.1.b

Bekannte Altzahl aus Vorgänger-Analyse 9a.1.b: **−18.517 EUR** (scheinbare Unter-
fakturierung EBM gesamt).

Ursache des Artefakts:
1. IE Eircode-PLZ-Matching-Lücke → viele Zeilen als `no_dlv` geführt → fehlende
   Delta-Einträge → negative Gesamtsumme
2. Kein Floater-Treatment → Erwartet > Ist auf allen Zeilen mit positivem Floater

Korrekte Gesamt-Delta (9a.4.2, 339 beurteilbare Zeilen): **+41.283 EUR** — alle
positiv, erklärt durch Floater-Aufschlag auf DLV-Tarif. Keine systematische
Unterfakturierung auf Lane-Ebene außer Muster-B (1 Zeile, −100,40 EUR).

### GEZE — Retroaktiv-Eintrag 5e (Commit 23d6a1a)

**Status: Funktional invalide, obwohl Tests grün.**

Commit 23d6a1a ("Etappe 5e: GEZE calculator, 6/6 within 2%") wurde im
CHF-Parser-Bug-State freigegeben. Die 6 Validierungssendungen enthielten einen
CH-Fall (PLZ 5436, CHF-Rate 1.065), der zufällig in das Null-Prozent-Band fällt.
Kein Testfall prüfte einen nicht-null CHF-Floater.

**Post-9b.1-Prüfung erforderlich:**
- Waren die 6 Validierungssendungen aus 5e allesamt non-CH oder im Null-Band?
  → Wenn ja: keine echte Drift in den 5e-Zahlen, nur stille Null für CH.
  → Wenn nein: 5e-Ergebnisse für CH-Zeilen nach unten verzerrt (chf_amount fehlte).
- Die 9b.3-Analyse wird zeigen, ob AX-Abrechnungszeilen für CH einen
  floater_pct > 0 aufweisen — das ist der indirekte Nachweis, dass ERKA
  den CHF-Floater korrekt berechnet hat (und 5e ihn nur nicht prüfte).

**Empfehlung:** 5e-Commit nicht rückwirkend ändern; stattdessen 9b.1-Fix
(dd3d558) als Nachfolge-Commit dokumentieren. Keine Zahlen aus 5e zitieren,
bis 9b.3 den CH-Floater im AX-Betrag bestätigt hat.

**9b.3-Ergebnis:** 54/95 CH-Gruppen zeigen Band-Match (51 × Neutralband
1.021–1.075 → chf_amount=0; 3 × aktive Bänder < 1.021 → CHF-Floater aktiv).
41 CH-Gruppen ohne Band-Match: Diesel-Überlagerung oder multiperiodische Batches.
→ Bestätigt: ERKA hat CHF-Floater korrekt in `Erlöse Fracht` eingerechnet;
5e-Commit-Bug hatte keine Auswirkung auf die tatsächliche Abrechnung (ERKA
rechnete korrekt), nur auf die Validator-Prüfung.

### EBM-Papst — Retroaktiv-Check Diesel-Einbettung (post-v1.5)

**Offene Frage:** Ist Diesel in den EBM-Abrechnungsstrecken-`betrag`-Werten
eingebettet, oder wurde für EBM kein Diesel-Floater verrechnet?

**Kontext:** Die EBM-9a.4.2-Analyse verwendete Abrechnungsstrecken (`EBM.xlsx`)
mit Spalten `betrag` und `toll` — keine separate Diesel-Spalte. Die
`floater_pct = (betrag − toll) / tariff − 1`-Interpretation kann daher zwei
verschiedene Dinge bedeuten:

| Szenario | Bedeutung von floater_pct | Muster-A-Interpretation |
|---|---|---|
| **Diesel = 0** (EBM hat keinen Diesel-Floater) | Reiner ERKA-/Vertragsfloater | Muster-A-Treffer sind valide; 7 % = ERKA-Aufschlag |
| **Diesel in betrag** (EBM-Diesel in `betrag` eingebettet) | ERKA-Floater + Diesel | Muster-A-Treffer könnten Diesel+Floater-Kombination sein |

**Schärfung durch CHT-B-Check (v1.6):** Die diesel_mode-Regel besagt: Diesel ist
pro (Kunde, Land) vereinbart — entweder immer oder nie. EBM-Prüfschema daher:

**Prüfschema:**
1. EBM BI-Daten (bi_top20_data.pkl, KNR 410844): `Erlöse_Diesel` per Land abfragen
   - Wenn für alle EBM-Länder `Erlöse_Diesel = 0`: EBM hat **keinen Diesel-Floater**
     → diesel_mode = `"not_contracted"` für alle EBM-Länder → floater_pct ist reiner
     Vertragsfloater → Muster-A-Narrative (7 % = ERKA-Aufschlag) bleibt valide
   - Wenn für einige Länder `Erlöse_Diesel > 0`: EBM hat Diesel für jene Länder
     → die Abrechnungsstrecken-`betrag`-Spalte enthält ggf. keinen Diesel (eigene
     Spalte im BI-System, nicht in Streckenabrechnung) → betrag = Tariff + Floater
     (Diesel separat im BI, nicht im `betrag`)
2. Cross-Check: `floater_pct = (betrag − toll) / tariff − 1` für EBM-Zeilen vor
   Jan 2026 (vor Muster-A-Aktivierungsdatum): Wenn Ratio ≈ 0,000 → kein Floater
   vor Jan 2026 → 7 % exakt im Jan 2026 = struktureller Switch = ERKA bestätigt

**Konsequenzbaum:**
- `Erlöse_Diesel = 0` für alle EBM-Länder in BI + fp ≈ 0 vor Jan 2026 → Muster-A valide
- `Erlöse_Diesel > 0` für EBM-Länder, `betrag` ohne Diesel + fp ≈ 0 vor Jan 2026 → Muster-A valide
- fp ≈ konstant vor Jan 2026 (nicht Null) → Diesel in `betrag` oder anderer Floater vorher

**Status:** Offen. Hohe Priorität. Prüfung in Etappe 9c.x als eigenständiger Retroaktiv-Commit.

### EBM-Papst und Fischerwerke — Retroaktiv-Prüfung Aggregationsebene (post-9b.3)

**Offene Frage:** Wurden EBM Muster-A-Treffer (50 Zeilen, Jan 2026) und Fischerwerke
Muster-A-Treffer (~31 Zeilen, März 2026) auf Positions- oder Sendungs-Ebene berechnet?

**EBM 9a.4.2-Analyse (Commit c4bcad9):**
- Eingabedaten: Abrechnungsstrecken `EBM.xlsx`, eine Zeile pro Eintrag
- Aggregations-Key: `Nach Ort` (Ortsname) → DLV-Route-Key
- Muster-A-Check: direkt auf Zeilen-Level (nicht aggregiert)
- Risiko: Falls EBM-Daten Positions-Level sind, könnten die 50 Muster-A-Treffer
  auf denselben 10–15 Sendungen basieren (Zahl des Findings wäre identisch, aber
  fp-Statistik wäre sendungsseitig robuster darzustellen)

**Fischerwerke (Muster-A ~31 Zeilen, März 2026):** Aggregationsebene noch nicht
dokumentiert; Risiko analog EBM.

**Prüfschema:**
1. Zähle eindeutige `Ausgangsbordero` in den EBM/Fischerwerke Muster-A-Zeilen
2. Wenn `n_unique_bordero << n_zeilen`: Positions-Level → retroaktiv auf
   Sendungs-Ebene aggregieren, Muster-A und delta_sum neu berechnen
3. Wenn `n_unique_bordero ≈ n_zeilen`: Sendungs-Level → kein Retroaktiv-Bedarf

**Wichtig:** Das Muster-A-Zählkriterium (`abs(fp − 0.07) < 0.0015`) ist auf
Positions-Ebene identisch anwendbar, sofern der 7 %-Floater sendungseinheitlich
aufgeschlagen wird (alle Positionen derselben Sendung haben denselben Floater).
In diesem Fall ändert Sendungs-Aggregation die Anzahl Treffer nicht, nur die
Granularität der delta_sum-Darstellung.

**Status:** Offen. Prüfung in Etappe 9c.x (EBM Retroaktiv) oder als separater
Retroaktiv-Commit vor Abschluss-Report.

### Welle-3-Kunden — Retroaktiv-Prüfung RN-Level-Faktor (post-9c.2a, v1.7)

**Hintergrund:** Das in CHT/BE (9c.2a) entdeckte RN-Level-Adjustment-Muster
(konsistente per-RN Faktoren ≠ 1.0 bei rn_std < 0.0005) kann potenziell auch
bei Welle-3-Kunden auftreten. Insbesondere bei Kunden mit:
- Quarterly-Floater-Mechanismen (ähnlich CHT BE-Dieselfloater)
- Kundenspezifischen Preisanpassungs-Vereinbarungen
- AX-Invoice-Batch-Konfigurationen, die pro Periode leicht variieren

**Pflicht-Prüfschema für Welle-3-Integration-Tests (HELU, HERMA, Hornschuch u.a.):**

Vor Pass-Rate-Berechnung jedes neuen Calculator-Tests:
1. Berechne pro RN: `rn_factor = median(erloes_fracht / basispreis)`, `rn_std`
2. Falls `rn_std < 0.0005 AND |rn_factor − 1| > 0.001`:
   → RN als `rn_level_adjustment` flaggen, §6b-Classifier aktivieren
3. Falls ≥ 3 RNs im Testset mit `rn_level_adjustment`:
   → Muster-Report: welche Faktoren, welche Periodizität, Richtung
   → Im Kunden-Report §8 ausweisen; nicht als Calculator-Bug werten

**Besondere Aufmerksamkeit bei Sonder-PLZ-Konsistenz:**
Analog zum CHT-IT-Befund (PLZ 20098: +6,1 % in 3 Zeilen, Calculator-Coverage-Frage)
sollten bei HELU/HERMA/Hornschuch ähnliche Sonder-PLZ-Muster (z. B. Industriegebiete
mit Thermozuschlag oder PLZ-gebundene Sondertarife) gesondert auf fp-Konsistenz
geprüft werden. Falls ≥ 2 Zeilen mit identischer PLZ konsistent fp ≠ 0 zeigen →
§8-Flag "Sonder-PLZ-Muster", manuelle Klärung ob Calculator-Lücke oder DLV-Sondertarif.

**Status:** Offen. Wird bei erstem Welle-3-Integration-Test aktiviert.

---

## §8 Kunden-Report-Format — Klärungsposten (Standard ab v1.7)

### Zweck und Abgrenzung

§8 ist der Abschnitt jedes Kunden-Reports, der **offene Befunde** zusammenfasst,
die manuelle Klärung oder Operations-Abstimmung erfordern.

**NICHT in §8 (methodisch erklärt):**
- Muster-A (ERKA-Floater 7 %; erwartet)
- `rn_level_adjustment` als solches (Gate 6 erklärt den Typ; aber die Tabelle erscheint in §8)
- Rundungsartefakte ≤ ±1 EUR
- AX-Raten-Präzisions-Δ wenn Calculator bereits angepasst (nur noch Klärungsfrage)

**IN §8:**
- Sonder-PLZ-Aufschlag (unbekannte Ursache)
- RN-Level-Adjustment-Übersicht (kompakte Tabelle aller RNs)
- AX-Raten-Präzisions-Klärungsfrage (vertragskonform?)
- Muster-B-Funde ohne Erklärung
- M2-Cluster-Befund (AX-Konfigurations-Fehler nach Migration)

### §8-Eintrag-Typen

| Typ | Auslöser | Priorität |
|-----|----------|-----------|
| Sonder-PLZ-Aufschlag | `plz_fp_std < 0,005` UND `|fp_mean| > 0,03` UND n ≥ 2 | Normal |
| Sonder-PLZ PRIORITY | `|fp_mean| > 0,15` ODER Ursache unklar nach Klärung | **PRIORITY** |
| RN-Level-Adjustment-Tabelle | rn_std < 0,0005 UND `|rn_factor − 1| > 0,001` (§6b) | Tabelle |
| AX-Raten-Präzision | `ax_rate_precision ≠ "native"` (§6c) | Klärungsfrage |
| Muster-B unerklärt | `delta_raw < −10 EUR` UND NOT Muster-A | Klärungskandidat |
| M2-Cluster-Befund | Dinas-Δ ≈ 0 UND AX-Δ < 0 (§2e Rule F Muster 2) | Höchste Priorität |

### Standard-Einzeleintrag-Format

```
### §8.x — [Typ]: [Kunde] / [PLZ oder RN-Nummer]
Datum: [Leistungsdatum]  | Δ: [EUR]  | n: [Anzahl betroffene Positionen]
Befund: [1–2 Sätze was beobachtet]
Klärungsfrage: [konkrete Frage an Operations / ERKA]
Status: offen | bestätigt | abgeklärt
```

### RN-Level-Adjustment §8-Listenformat

Für Kunden mit ≥ 1 `rn_level_adjustment` (§6b): kompakte Tabelle aller betroffenen RNs:

```
§8 RN-Ebene-Anpassungen (Gate 6, n=[Anzahl RNs])
| RN       | rn_factor | n_pos | delta_sum_EUR | Periodizität | Status |
|----------|-----------|-------|---------------|-------------|--------|
| [RN-Nr]  | [Faktor]  | [n]   | [EUR]         | [jan/mix]   | offen  |
```

Wenn Faktor als Diesel-Floater operationsseitig bekannt: Gate 6 schließt,
Eintrag mit "bestätigt" markieren — kein Calculator-Bug.

---

## §9a Multi-Agent-Workflow-Regeln (ab v1.8.2)

### Hintergrund

Bei der Zwischenstand-Erstellung 2026-04-21 wurde ein Read-only-Explore-Agent gebeten,
numerische Werte aus Python-Build-Scripts zu extrahieren. Der Agent kann Scripts lesen,
aber nicht ausführen. Er produzierte plausibel wirkende, aber falsche Zahlen
(Incident-Details: `docs/qa_agent_hallucination_2026-04-21.md`).

### Regeln

**R1 — Ground-Truth-Pflicht:**
Alle numerischen Werte in Audit-Dokumenten (Scope-Kaskaden, Match-Raten, EUR-Summen)
müssen aus direkten Script-Ausführungen stammen:
```bash
python src/build_9c*.py 2>&1
```
Niemals aus Agent-Inferenz oder Code-Lektüre ohne Ausführung.

**R2 — Keine numerische Delegation an Read-only-Agenten:**
Aufträge wie "extrahiere die Zahlen aus diesem Script" dürfen nicht an Explore-,
claude-code-guide- oder andere Read-only-Agenten delegiert werden, wenn das Script
zur Laufzeit auf externe Daten (pickle-Dateien, Excel-Sheets) zugreift.
Erlaubt: statische Konfigurationswerte (Konstanten, Schwellenwerte direkt im Code).

**R3 — Unsicherheits-Kennzeichnung:**
Nicht erhobene Werte werden explizit als `nicht erhoben` markiert — nie als
berechnete Schätzung.

**R4 — Cross-Check vor Dokument-Commit:**
Vor dem Commit eines numerischen Zwischenstand-Dokuments: mindestens 3 Stichproben
aus dem Dokument gegen die direkten Script-Ausgaben verifizieren.

### Erlaubte Agent-Aufgaben

| Aufgabe | Erlaubt für Read-only-Agent |
|---|---|
| Code-Struktur erklären | ja |
| Statische Konstanten lesen | ja |
| Datei-Existenz prüfen | ja |
| Build-Script-Ausgaben extrahieren | **nein** |
| Numerische Zusammenfassungen aus Laufzeit-Daten | **nein** |
| Plotting/Visualisierung aus Laufzeit-Daten | **nein** |

---

## Changelog

| Version | Datum | Etappe | Änderung |
|---|---|---|---|
| 1.0 | 2026-04-20 | 9a.4.2 | Initiale Erstellung; §3 floater_pct-Basis für Muster-A; §5a LDM-Fallback |
| 1.1 | 2026-04-20 | 9b.0 | §2 GEZE-Block: Maut-inklusiv, CHF-Floater als EUR-Surcharge, Reverse-Engineer-Ansatz; §3 GEZE-Zeile + engeres Muster-A-Binning für 9b.3 |
| 1.2 | 2026-04-20 | 9b.1 | §6a Sanity-Gate 5 (bedingte Komponenten nicht-null); §7 Retroaktiv-Eintrag GEZE 5e (23d6a1a im Parser-Bug-State freigegeben) |
| 1.3 | 2026-04-20 | 9b.2 | §5.0 tonnage_source-Pflichtfeld + 20%-Audit-Schwelle; GEZE-Befund 25,5% Tonnage=0 dokumentiert |
| 1.4 | 2026-04-20 | 9b.3 | §2a Positions-Level vs Sendungs-Level: Aggregations-Key-Hierarchie, Muster-B-Aggregationsartefakt-Flag, Pflichtfelder aggregation_level/key_source; §7 EBM+Fischerwerke Retroaktiv-Aggregationsebene-Prüfung; §7 GEZE 9b.3-Ergebnis (CHF-Band-Match) |
| 1.5 | 2026-04-20 | 9c.0 | §2.0 Standard-Formeln: Diesel-always-separate, Zwei-Fall-Regel (unbundled/all_in), Pflichtfelder pricing_mode + all_in_components; §2 Kunden-Blöcke realigned (Fischerwerke/EBM/GEZE) + CHT-Block neu; §3 Muster-A-Formel auf neue Notation + EBM-Sonder-Block; §3 Kundentabelle GEZE+CHT aktualisiert; §7 EBM-Diesel-Retroaktiv-Check (Szenario Diesel=0 vs Diesel-in-betrag) |
| 1.6 | 2026-04-20 | 9c.0 | §1 pre_dlv_2026-Phase + in_dlv_2025_fallback präzisiert; §2 CHT Diesel/Maut-Tabelle per Land (B-Check empirisch) + 9c.0 IT fp-Befund; §2a diesel_mode/maut_mode pro (Kunde, Land) mit Sanity-Check-Regel; CHT-Präzedenzfall BE/GR contracted vs IT/AT/ES not_contracted |
| 1.6.1 | 2026-04-20 | 9c.0 | §2a Einzelfall-all_in-Ausnahme: Diesel=0+Maut=0 bei Fracht≈split_sum → all_in_exception-Flag; Schwelle ≤1%; CHT-BE-Präzedenzfall PLZ 8550/3600 |
| 1.7 | 2026-04-20 | 9c.2a | §6b neu: RN-Level-Faktor-Detection (Gate 6); Classifier-Logik (rn_std<0.0005, rn_factor); §8-Listenformat für RN-Adjustment-Fälle; CHT/BE 9c.2a Befundtabelle; GEZE retroaktiv Gate-6-bestanden; §7 Welle-3-Retroaktiv-Pflichtprüfschema RN-Level-Faktor + Sonder-PLZ-Konsistenz |
| 1.7.1 | 2026-04-20 | 9c.2a | §3a neu: Sonder-PLZ-Aufschlag — Definition, Abgrenzung zu Muster-A, Detection-Regel (plz_fp_std<0.005, abs(fp_mean)>0.03, n≥2), Known-Cases-Tabelle (CHT/IT/20098 +6.1%, CHT/BE/8540+8560+8400 +6.3-6.4% Kortrijk West), PRIORITY-§8-Eintrag 924248/7700 (+18.7%); AX-Raten-Präzisions-Hinweis: IT=4dp, BE=2dp, Pflicht-per-Land-Validierung |
| 1.7.2 | 2026-04-20 | 9c.2a | §6c neu: AX-Raten-Präzisions-Check — Pflichtschritt vor jedem neuen Calculator-Build; ax_rate_precision (native/2dp/3dp/other); Backrechnung-Methode; Known-Befunde-Tabelle (CHT/IT=native, CHT/BE=2dp); Zeitbezug-Befund CHT/BE rn_level_adjustment: kein temporales Clustering (Jan-2026 hat mix aus exact+rn_adj), Faktoren variieren pro RN, Mechanismus unbekannt → Klärungsfrage Operations |
| 1.8 | 2026-04-21 | 9c.2c | §2b neu: billing_scope Parameter ("position"\|"rn"); Prorating-Logik (HL+Maut on RN-Level, NL pro Empfänger-Gruppe, Verteilung by actual_kg); Empfänger-Gruppe = (RN, Empfänger_Name) nicht (RN, PLZ) — empirisch bestätigt GR 9c.2c, \|Δ\|<0,001 EUR über alle Positionen; §6c Known-Befunde aktualisiert: CHT/ES=2dp (9c.2b), CHT/GR=2dp (9c.2c); billing_scope-Tabelle (CHT/IT/BE/ES=position, CHT/GR=rn); Retroaktiv-Empfehlung HELU/HERMA/Hornschuch |
| 1.8.1 | 2026-04-21 | 9c.2d | §2c neu: kg_rounding_rule Parameter ("ceil_to_100"\|"actual_kg"\|"actual_kg_fracht_only"); Strukturbefund CHT/AT: "Gewichtsrundung 100:100" gilt nur für DE-Maut, Fracht nutzt actual_kg direkt gegen Schwellen; AT-Fracht ist FLAT pro Sendung (nicht per-100-kg); Pflicht-Prüftabelle (kg_rounding_rule + Fracht-Einheit + Split-Logik); Known-Befunde-Tabelle CHT/AT=actual_kg_fracht_only (9c.2d); §2b billing_scope-Tabelle: CHT/AT=position (9c.2d, empirisch \|Σ_Δ\|<0,002 EUR, 4 RNs); §6c Known-Befunde: CHT/AT=2dp (9c.2d, \|Δ_pos\|<0,004 EUR) |
| 1.8.2 | 2026-04-21 | QA | §9a neu: Multi-Agent-Workflow-Regeln; Halluzinierungsincident dokumentiert (Explore-Agent produzierte falsche Build-Script-Zahlen: GR n_total 1074→102, ES Match 100%→93.3%, BE rn_adj 18→111); Ground-Truth-Regel: numerische Werte ausschließlich aus direkten python-Ausgaben; Keine Delegation numerischer Extraktion an Read-only-Agenten |
| 1.9 | 2026-04-24 | v1.9 | §2e neu: Aggregations-Regel für Dinas-AX-Vergleich — A) AX-Sub-Filter via Mastersendung-Feld (is_sub = has_ms & ~has_ua), kein Tonnage-Proxy; B) Dinas-Aggregation pro Rechnung: innerhalb jeder Rechnung nach (Sender_PLZ, Empf_PLZ, Ladedatum) gruppieren, nie rechnungsübergreifend; C) Vergleich Dinas-Aggregat ↔ AX-Master über Sender+Empfänger+Ladedatum |
| 1.9.1 | 2026-04-24 | v1.9 | §2e Rule D neu: Zweistufigkeit der AX-Filterung — filter_comparison_set() (Stufe 1, Sub-Rows) ist nicht ausreichend ohne nachgelagerte Unbeurteilbar-Filterung (Stufe 2, Tonnage=0 UND LDM=0); obligatorische Prüftabelle für neue Kunden-Rollouts; empirischer Befund aus Regression-Analyse dokumentiert |
| 1.9.3 | 2026-04-24 | v1.9 | §2e Rule A Implementations-Detail: Unterauftrag ist komma-separierter String, kein numerischer Wert; _nonempty() (string-check) korrekt, _nonempty_numeric() (float-check) würde Master fälschlich als Sub klassifizieren; empirisch bestätigt an 586 GEZE-Master-Zeilen |
| 1.9.2 | 2026-04-24 | v1.9 | §2e Rule E neu: Master-Rekonstruktion — Master führt bei physischen Parametern (Tonnage, LDM, Stellplätze, Volumen, Colli); Sub-Summe als Fallback nur bei NaN/None-Master-Feld; 0 ist gültiger Master-Wert (kein Fallback-Trigger); Erlöse immer aus Sub-Summe; Rechnungsnummern aus Sub-Liste; Master-vs-Sub-Inkonsistenz = Datenredundanz, kein Finding; Implementierung: reconstruct_ax_master() in src/tms/billing/aggregation.py; Validierung: GEZE Auftrag 7092010001835006 (Tonnage=361,9 Master, Erlöse=97,28 Sub-Summe) |
| 1.9.4 | 2026-04-24 | v1.9 | §2e Rule F neu: Vergleichs-Cluster-Format (nur Rule F, kein §2f/§2g/§3b/§3c/§8 enthalten) |
| 1.9.5 | 2026-04-25 | v1.9 | §2f neu: Pipeline-Integrations-Flow (7-Schritt-Ablauf, STOP-Kriterien); §2g neu: billing_axis-Tabelle per Kunde (GEZE/EBM/Fischer/HERMA/CHT/Sika); §3b neu: Empirische Master-Sub-Muster (Fallback-Relevanz-Tabelle GEZE/HERMA/Fischer/CHT); §3c neu: Orphan-Sub-Pattern (Definition, GEZE 28 Subs/3.247 EUR, Pflicht-Check-Code); §8 neu: Kunden-Report-Format Standard — Klärungsposten-Typen, Eintrag-Format, RN-Adj-Listenformat |
