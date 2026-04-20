# Fischerwerke — Billing Accuracy Findings (Zwischenstand)

**Status: Vorläufig — Rückfragen an Fischerwerke/ERKA offen (siehe Abschnitt 7)**
**Stand: 2026-04-20 | Etappe 9a.3.1–9a.3.2**

---

## 1. Executive Summary

### Methodik

Für Fischerwerke (KNR 409480) wurden die tatsächlichen Abrechnungsbeträge aus den
**Abrechnungsstrecken** (AX-System, 2.195 Zeilen, Sep 2025–Apr 2026) gegen die
**kundengerichteten DLV-Tarife** geprüft. Basis: EUR pro Stellplatz (Flat-Rate per
Sendung aus Lookup-Tabelle), keine Gewichtsformel.

Die Prüfung ist **phasen-bewusst**: Jede Zeile wird einem von drei Zeitfenstern
zugeordnet — `pre_dlv` (vor DLV-Gültigkeit), `in_dlv` (innerhalb), `post_dlv`
(nach Ablauf). Der Calculator-Check erfolgt **ausschließlich** auf `in_dlv`-Zeilen.

Wichtig: Der `Kern`-Unterfrachtführer-Tarif (günstigere Einkaufspreise) wurde
bewusst **nicht** verwendet. Nur die kundengerichteten Offerten (ERKA an Fischerwerke)
dienen als Referenz.

### Ergebnis auf einen Blick

| Lane | DLV gültig | n in_dlv | Muster-A (+7%) | Muster-B (Unter) |
|---|---|---|---|---|
| IT-Padova | 01.01–31.12.2026 | 89 | 20 (+574 EUR) | 0 |
| IT-Copiano | 12.01–31.12.2026 | 41 | 11 (+709 EUR) | 3 (−339 EUR) |
| BE-Willebroek | 01.01–31.12.2026 | 14 | 5 (+245 EUR) | 2 (−240 EUR) |
| DK-Koge | 01.01–31.12.2026 | 56 | 10 (+1.068 EUR) | 0 |
| IE-Dublin | 01.01–31.12.2026 | 35 | 4 (+30 EUR) | **2 (−759 EUR)** |
| ES-MontRoig | 01.01–31.12.2026 | 99 | 12 (+431 EUR) | 3 (−532 EUR) |
| GR-Athen | 01.05–31.12.2025 | 245 | 0 | 21 (−920 EUR) |
| GB-Wallingford | 01.05–31.12.2025 | 39 | 0 | 10 (−2.035 EUR) ⚠️ |

**Zwei Befund-Typen:**
- **Muster-A** (+7%, lane-übergreifend): Auf allen 6 aktuellen 2026-Lanes vorhanden.
  Höchstwahrscheinlich ein nicht archiviertes ERKA-Indexschreiben. Pending Klärung.
- **Muster-B** (in_dlv-Unterfakturierung): Auf IE, ES, BE, IT-Copiano, GR, GB.
  Belastbar als Befund, unabhängig von der Muster-A-Frage.

**Drei Lanes unbeurteilbar:**
- GR: 360 Zeilen Jan–Apr 2026 ohne 2026-Stückgut-DLV (168 kEUR offen)
- GB: 2025-DLV abgelaufen Dez 2025, kein 2026-Nachfolger gefunden
- IT-Verona: 21 Zeilen ohne dediziertes DLV

---

## 2. Muster-A: +7% lane-übergreifend

### Befundbeschreibung

Bei 62 von 618 `in_dlv`-Zeilen (10%) entspricht der abgerechnete Betrag
**exakt DLV-Rate × 1.0700** (Ratio-Streuung < 0.00002 Std.abw. — nicht zufällig).

| Lane | n Muster-A | EUR-Summe | Ratio-Std |
|---|---|---|---|
| IT-Padova | 20 | +574 EUR | 0.000019 |
| IT-Copiano | 11 | +709 EUR | 0.000004 |
| DK-Koge | 10 | +1.068 EUR | 0.000001 |
| ES-MontRoig | 12 | +431 EUR | 0.000009 |
| BE-Willebroek | 5 | +245 EUR | 0.000002 |
| IE-Dublin | 4 | +30 EUR | 0.000000 |
| **Gesamt** | **62** | **+3.057 EUR** | |

### Zeitliches Muster (Pilotlane IT-Padova)

Drei klar abgegrenzte Phasen auf der Padova-Lane:

| Periode | exact_match | muster_a | muster_b |
|---|---|---|---|
| Sep–Dez 2025 (pre_dlv) | — | 3 | 29 |
| Jan–Feb 2026 (in_dlv) | 13 | 0 | 0 |
| Mrz–Apr 2026 (in_dlv) | 2 | 20 | 0 |

Der Aufschlag erscheint nach einem kurzen Korrekt-Abrechnungs-Fenster (Jan 2026)
und trifft alle Lanes synchron ab ca. Mrz 2026.

### Befund und offene Frage

Der 7%-Aufschlag ist **nicht im DLV dokumentiert**. Das DLV 2026
(gültig 01.01.–31.12.2026, ausgestellt 19.12.2025 von ERKA) enthält alle
Zuschläge explizit als „inklusive" (Diesel, DE-Maut, AT-Maut, Mobility Package).
Keine Floater-Klausel, kein Indexierungsmechanismus.

**Hypothese:** Separates ERKA-Tariferhöhungs-Anschreiben mit Wirkung Feb/Mrz 2026,
das lokal nicht archiviert wurde — bei Speditionen ein übliches Instrument neben
dem DLV-Dokument.

Bis zur Klärung gilt Muster-A als **nicht eindeutig zuordenbar** (rechtmäßige
Tariferhöhung vs. unberechtigter Aufschlag).

---

## 3. Muster-B: Echte Unterfakturierungen (in_dlv)

### Befundbeschreibung

41 Zeilen (6,6% aller in_dlv-Zeilen) zeigen `Betrag < DLV-Rate − 10 EUR`.
Diese sind unabhängig von der Muster-A-Frage belastbar, da der DLV die
vereinbarte Untergrenze darstellt.

### IE-Dublin — dichteste Abweichung

| Stpl | Betrag (IST) | DLV-Soll | Delta | Datum |
|---|---|---|---|---|
| 10 | 497,13 EUR | 1.018,67 EUR | **−521,54 EUR** | 28.01.2026 |
| 7 | 415,95 EUR | 653,14 EUR | −237,19 EUR | 27.03.2026 |

Summe: −759 EUR auf 2 Zeilen. Relativer Abstand −48% bis −36%.
IE-DLV ist gültig 01.01.2026–31.12.2026 → diese Zeilen liegen klar in der
Gültigkeitsperiode.

### Weitere Muster-B-Lanes

| Lane | n | EUR gesamt | Schlechteste Einzelzeile |
|---|---|---|---|
| ES-MontRoig | 3 | −532 EUR | 33 Stpl: 1.403 vs. 1.627 EUR (−224 EUR) |
| IT-Copiano | 3 | −339 EUR | 13 Stpl: 477 vs. 600 EUR (−123 EUR) |
| BE-Willebroek | 2 | −240 EUR | 20,5 Stpl: 561 vs. 714 EUR (−153 EUR) |
| GR-Athen (in_dlv) | 21 | −920 EUR | 4 Stpl: 294 vs. 440 EUR (−146 EUR) |
| GB-Wallingford ⚠️ | 10 | −2.035 EUR | 24 Stpl: 1.075 vs. 1.965 EUR (−890 EUR) |

**Muster-B Gesamt:** 41 Zeilen, −4.825 EUR (ohne GB-Caveat: −2.790 EUR).

### GB-Wallingford — Caveat

Das verwendete DLV für GB gilt 01.05.–31.12.2025. Alle 39 GB-Zeilen in den
Abrechnungsstrecken fallen in diesen Zeitraum. Ein 2026-Nachfolge-DLV wurde im
Archiv nicht gefunden. Die Muster-B-Zeilen (10×) könnten auf einem veralteten
Referenztarif beruhen, falls eine zwischenzeitliche Tarifanpassung erfolgte.

---

## 4. Unbeurteilbare Zeilen

### GR-Athen: 360 Zeilen Jan–Apr 2026 ohne 2026-DLV

Das archivierte GR-Stückgut-DLV (ERKA an Fischerwerke) gilt bis 31.12.2025.
Das einzige 2026-GR-Dokument im Archiv (`20260206_Export GR_Paketlieferungen.xlsx`,
gültig ab 01.02.2026) deckt ausschließlich Paketware (per Karton, Zonen 1–6) —
eine strukturell andere Leistungsart als die Stückgut-Sendungen in den
Abrechnungsstrecken.

**Offenes Volumen:** 360 Zeilen, 167.638 EUR (Jan–Apr 2026) ohne Tarif-Referenz.

### GB-Wallingford: Kein 2026-DLV

Letztes archiviertes GB-DLV: `20250422_…GB-OX Wallingford.xlsx`, gültig bis
31.12.2025. GB-Zeilen in den Abrechnungsstrecken enden am 14.01.2026 — entweder
wurde die Route eingestellt oder das 2026-DLV fehlt im Archiv.

### IT-Verona: Kein dediziertes DLV

21 Zeilen (5.498 EUR, Okt 2025–Apr 2026) mit `Nach Ort = Verona`. Im Archiv
vorhanden: `20250428_Fischerwerke_DE-72 Waldachtal nach IT-37139 Verona.xlsx`
(2025), kein 2026-Nachfolger. Nicht in den Calculator-Check einbezogen.

---

## 5. Methodik

### Phasen-Konzept

Jede Abrechnungsstrecken-Zeile wird gegen das DLV-Gültigkeitsfenster geprüft:

```
pre_dlv:  Leistungsdatum < DLV-Gültigkeitsbeginn
in_dlv:   Leistungsdatum innerhalb DLV-Gültigkeit
post_dlv: Leistungsdatum > DLV-Gültigkeitsende
```

Calculator-Check (expected = dlv_table\[round(Stpl)\]) nur auf `in_dlv`-Zeilen,
um Tarif-Mismatch durch veraltete Referenzen zu vermeiden.

### parse_dlv_auto — Zweigeteiltes Raten-Layout

Alle Fischerwerke-DLV-Dateien teilen die Raten-Tabelle auf zwei Spaltenbereiche:

| Layout | Linker Block | Rechter Block | Lanes |
|---|---|---|---|
| A | col 0/1 (Stpl 1–17) | col 4/5 (Stpl 18–34) | DK, GR, GB, IT-Padova, IT-Copiano, ES |
| B | col 2/3 (Stpl 1–15) | col 7/8 oder 6/7 | BE, IE |

Der Autodetekt wählt Layout A wenn col 0/1 Treffer liefert, sonst Layout B.
Stpl-Bereiche wie „30–33" (Flat-Cap) werden als Range expandiert.

### Kern- vs. Kundengerichtetes DLV

Für IT-Padova existieren zwei Dateien:
- `20251219_Kern_Fischerwerke…` — Unterfrachtführer-Einkaufspreise (z.B. 9 Stpl = 333,13 EUR)
- `20251219_Fischerwerke_DE-72…` — Kundengerichtete Offerte (9 Stpl = 384,38 EUR)

Verwendet wird ausschließlich die kundengerichtete Datei. Der Preisunterschied
(ca. 13–15%) ist die Marge von ERKA — kein Analysebefund.

---

## 6. Einschränkungen

**Kein Dinas × AX-Migrationsvergleich möglich.**
Das Dinas-Parquet für Fischerwerke enthält ausschließlich GR-Zeilen aus dem
Zeitraum Feb–Aug 2025 (PRE-Periode). Die AX-Abrechnungsstrecken starten Sep 2025
(POST-Periode). Es gibt keinen zeitlichen Überlappungsbereich für einen
direkten Sendungs-Vergleich.

**Keine Positions-Taxonomie angewendet.**
Die Abrechnungsstrecken enthalten nur `Betrag` (Gesamtbetrag), keine Dekomposition
in Fracht/Diesel/Maut-Komponenten. Ein Taxonomie-Check (wie für EBM/Dinas in
Etappe 9a.1.F) ist hier strukturell nicht möglich — und nicht erforderlich, da
der DLV alle Zuschläge als inklusive ausweist.

**Stpl-Fraktionen und Teillasten.**
Abrechnungsstellplätze < 1 (z.B. 0.85, 0.90) treffen auf DLV-Minimum von 1 Stpl.
Die tatsächliche Abrechnung weicht hier systematisch ab (Betrag 75–105 EUR vs.
DLV-Minimum 51–56 EUR je nach Lane). Diese Zeilen sind in der Analyse als
`muster_c_over` oder `other` klassifiziert, nicht als Befund.

**DLV-Archiv-Vollständigkeit nicht verifiziert.**
Der Report basiert auf den im lokalen Archiv unter
`Fischerwerke/DLVs & Tarife/2025/` und `2026/` verfügbaren Dateien.
Nachträge, Korrekturofferten oder kurzfristige Sondervereinbarungen, die nicht
abgelegt wurden, sind nicht berücksichtigt.

---

## 7. Offene Rückfragen an Fischerwerke / ERKA

### RF-1: Tariferhöhungs-Indexschreiben 2026 (kritisch)

> *„Gibt es ein Tariferhöhungs-Anschreiben oder einen Nachtrag zum DLV 2026
> (alle Exportlanes) mit Wirkung Februar/März 2026? Die Abrechnungsstrecken
> zeigen ab März 2026 auf sämtlichen 6 aktiven Lanes einen systematischen
> Aufschlag von exakt +7,0% auf die vereinbarten DLV-Sätze."*

Betroffene Lanes: IT-Padova, IT-Copiano, DK, ES, BE, IE. Gesamtvolumen Muster-A:
3.057 EUR (beobachtet, wahrscheinlich unvollständig da Datenstand Apr 2026).

### RF-2: GB-Wallingford DLV 2026

> *„Liegt für die Route DE-72 Waldachtal → GB-OX Wallingford ein DLV für 2026 vor?
> Das Archiv enthält nur die Offerte vom 22.04.2025 (gültig bis 31.12.2025)."*

### RF-3: GR-Stückgut DLV 2026

> *„Liegt für Griechenland-Stückgut-Sendungen (Europallet-Basis) ein DLV für
> 2026 vor? Das vorhandene Dokument vom 06.02.2026 deckt nur Paketware."*

360 Zeilen Jan–Apr 2026, Betrag-Summe 167.638 EUR ohne Referenz-Tarif.

### RF-4: IT-Verona DLV-Zuordnung

> *„Gilt für IT-37139 Verona die Padova-Offerte (IT-35127) oder eine separate
> Vereinbarung? Im Archiv gibt es nur eine 2025-Offerte für Verona."*

---

## 8. Nächste Schritte

### Nach Kundenantwort

- **RF-1 beantwortet:** Muster-A entweder als dokumentierte Erhöhung abhaken
  oder als Fehlabrechnungs-Finding in den Final-Report übernehmen
- **RF-2/3 beantwortet:** GB und GR in den Calculator-Check einbeziehen
- **RF-4 beantwortet:** IT-Verona korrekt zuordnen
- Dann: `docs/fischerwerke_findings_final.md` (9a.3.3b)

### Parallel: Weitere Kunden

Nächster Kandidat: EBM-Papst (KNR 410844, LDM/Stellplatz-Basis, 9a.4).
Alternativ: HERMA oder CHT (beide bereits mit DLV-Infrastruktur in
`src/top20_abw_s5_tariff_check.py` vorhanden).

### Retroaktive Sika-Implikationen

Die in 9a.3 entwickelten Methoden sind rückwirkend auf frühere Analysen anwendbar:

1. **parse_dlv_auto auf GEZE-CH:** GEZE-DLV hat möglicherweise auch zweigeteiltes
   Layout — neu parsen und gegen 9a.1.E-Ergebnisse verifizieren
2. **Kern- vs. Kundengerichtet-Prüfung:** Für alle 5 DLV-Kunden sicherstellen,
   dass die richtigen Offerten verwendet werden (keine Unterfrachtführer-Tarife)
3. **Phasen-Logik rückwirkend:** Die Gültigkeitsfenster-Prüfung kann die
   Qualität der 9a.1.D-Routen-Validierung verbessern (dort keine Phaseneinteilung)

---

*Erstellt: 2026-04-20 | Script: `src/build_9a32_phases_per_lane.py`*
*Datenquellen: `data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Fischerwerke.xlsx`,
`Fischerwerke/DLVs & Tarife/2026/` (6 Lanes), `Fischerwerke/DLVs & Tarife/2025/` (GR, GB)*
*Outputs: `data/reports/9a32_phases_per_lane.csv`, `data/reports/9a32_findings_raw.csv`*
