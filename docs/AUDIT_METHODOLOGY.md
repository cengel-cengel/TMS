# TMS Billing Audit — Methodik-Referenz

**Projekt:** Migration Dinas → AX (ERP-Wechsel)
**Scope:** Billing-Accuracy-Audit für Kundentarife (Etappe 9a.x)
**Stand:** 2026-04-20

---

## §1 Grundprinzip

Jede Abrechnungszeile aus den **Abrechnungsstrecken** (AX-System) wird gegen den
**kundengerichteten DLV-Tarif** geprüft — nicht gegen den Einkaufstarif des
Unterfrachtführers (z. B. Kern). Ziel: Nachweis von Über- oder Unterfakturierung
gegenüber der vertraglich vereinbarten Offerte.

Die Prüfung ist **phasen-bewusst**: Jede Zeile wird einem Zeitfenster zugeordnet:
- `pre_dlv` — vor DLV-Gültigkeitsbeginn
- `in_dlv` / `in_dlv_2025` / `in_dlv_2026` — innerhalb eines Gültigkeitsfensters
- `post_dlv` — nach DLV-Ablauf

Calculator-Checks laufen **ausschließlich** auf `in_dlv`-Zeilen.

---

## §2 DLV-Tarif-Formate

### Fischerwerke (Stellplatz-basiert)
- Lookup-Tabelle: Anzahl Stellplätze → Flat-Rate per Sendung
- Per-Route-Dateien (eine Datei pro Abrechnungsrelation)
- Quelle: `Fischerwerke/DLVs & Tarife/`

### EBM-Papst (Palletspace-Matrix, LDM-basiert)
- Breite Matrix: Zeile = Route (PLZ-Key), Spalte = Stellplätze 1–33 + FTL
- Zwei Sheets pro DLV-Datei: `Tariffs_DE_EU` (Frachtpreis) + `Toll_DE_EU` (Maut)
- Abrechnung: `betrag = tariff[route][n_stpl] × (1 + floater) + toll[route][n_stpl]`
- Quelle: `EBM-Papst, Mulfingen/`

### Route-Key-Extraktion (EBM)
- **IE/GB** (Eircode-Länder): 3-stelliger Alpha-Code — `'IE-A92 FY90'` → `'A92'`
- **PLZ-Länder** (PL/SK/SI/HR/EE): Vollständiger PLZ-String — `'PL-03-236'` → `'PL-03-236'`
- **Merged-Einträge**: Pipe-separated → nimm erstes — `'EE-75301|EE-75306'` → `'EE-75301'`

---

## §3 Muster-A-Erkennung

### Definition
Muster-A = **Fester ERKA-Indexaufschlag** von exakt 7,00 % auf den DLV-Basistarif
(nicht Teil des DLV, sondern separates Rider-Dokument / Email-Vereinbarung).

### Erkennungsformel
```
floater_pct = (betrag - toll) / tariff - 1
muster_a    = abs(floater_pct - 0.07) < 0.0015
```

**Begründung für floater_pct-Basis (nicht Ratio-Basis):**

Die nahe liegende Alternative — `ratio = betrag / (tariff + toll)` mit Fenster
`[1.0645, 1.0755]` — ist **zu breit** und erzeugt Falsch-Positive:
- PL-Zeilen März 2026 haben einen variablen Diesel-Floater von ~8,1 %
- Deren Ratio fällt ebenfalls in das Fenster, obwohl es sich um regulären
  Dieselzuschlag (kein ERKA-Indexaufschlag) handelt
- Der floater_pct-Ansatz trennt sauber: 7,00 % ± 0,15 % = ERKA-Indexaufschlag;
  8,1 % = normaler Dieselzuschlag

**Kreuzvalidierung:** Alle 50 bestätigten Muster-A-Zeilen liegen im Januar 2026
und stammen aus 5 Lanes (IE/PL/EE/SK/HR) — konsistent mit einem systemweiten
Aktivierungsdatum.

### Kundenbelegte Muster-A-Funde (Stand 9a.4.2)

| Kunde | KNR | Aktivierungsmonat | n Zeilen | Lanes |
|---|---|---|---|---|
| Fischerwerke | 409480 | März 2026 | ~31 | IT-Padova, IT-Copiano, FR, GB |
| EBM-Papst | 410844 | Januar 2026 | 50 | IE, PL, EE, SK, HR |

Unterschiedliche Aktivierungszeitpunkte pro Kunde deuten auf kundenspezifische
Vereinbarungen hin — gleicher Mechanismus, unterschiedliches Roll-out-Datum.

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

## §5 Stellplatz-Ermittlung

### Direkt aus Abrechnungsstrecken
Bevorzugte Quelle: Spalte `Abrechnungsstellplätze` (integer).

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

## §7 Altzahl-Validierung

Bekannte Altzahl aus Vorgänger-Analyse 9a.1.b: **−18.517 EUR** (scheinbare Unter-
fakturierung EBM gesamt).

Ursache des Artefakts:
1. IE Eircode-PLZ-Matching-Lücke → viele Zeilen als `no_dlv` geführt → fehlende
   Delta-Einträge → negative Gesamtsumme
2. Kein Floater-Treatment → Erwartet > Ist auf allen Zeilen mit positivem Floater

Korrekte Gesamt-Delta (9a.4.2, 339 beurteilbare Zeilen): **+41.283 EUR** — alle
positiv, erklärt durch Floater-Aufschlag auf DLV-Tarif. Keine systematische
Unterfakturierung auf Lane-Ebene außer Muster-B (1 Zeile, −100,40 EUR).

---

## Changelog

| Version | Datum | Etappe | Änderung |
|---|---|---|---|
| 1.0 | 2026-04-20 | 9a.4.2 | Initiale Erstellung; §3 floater_pct-Basis für Muster-A; §5a LDM-Fallback |
