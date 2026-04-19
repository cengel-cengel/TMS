# Etappe 8h — PLZ-Extraktor IE/ES/GB: Pattern-Dokumentation, Coverage-Statistik, verbleibende Gaps

**Stand:** 2026-04-19  
**Scope:** Fix für `fehlt_in_ax_clusters`-Familien aus Etappe 8g  
**Betroffene Dateien:**
- `src/tms/clustering/plz_extractor.py` (neu)
- `src/tms/clustering/ax_cluster.py` (erweitert)
- `src/tms/matching/cluster_matcher.py` (KNR-Normalisierung)

---

## 1. Root-Cause-Analyse

Etappe 8g identifizierte 17 `ax_coverage_gap`-Familien (827.784 €). Davon wurden 10 als
`fehlt_in_ax_clusters` klassifiziert — die Sendungen existierten in Sika.xlsx und TB, aber
der Cluster-Builder erzeugte keine passenden Familien.

Zwei unabhängige Bugs lagen vor:

### Bug 1: Falsche KNR-Normalisierung für `ARA_Sika_DE+CH`

Die kombinierte AX-Kontonummer `ARA_Sika_DE+CH` wurde bisher normalisiert:
- `empf_land == "CH"` → KNR `511241` (Sika Supply Center AG)
- alle anderen → KNR `491063` (Sika Deutschland GmbH)

**Problem:** SSC (KNR 511241) bedient auch IE/ES/GB/PT/LU-Ziele — nicht nur CH.
In Sika.xlsx unterscheiden sich SSC- und Sika-DE-Touren durch das Feld `Von Name`:
- `"Sika Supply Center AG"` → SSC (511241)
- `"Sika Deutschland GmbH"` / `"SIKA Deutschland GmbH"` etc. → Sika DE (491063)

**Folge:** 153 SSC-Export-Cluster (IE/ES/GB/PT) wurden fälschlich als `491063`-Familien
angelegt und matchten nie die Dinas-Familien unter `511241`.

**Fix:** `_normalize_ax_knr(knr, empf_land, von_name)` prüft jetzt:
```python
if "supply center" in von_name.lower():
    return "511241"   # SSC route
```

### Bug 2: Irische PLZ-Kodierung (Eircode vs. Dinas-Konvention)

Dinas: Alle Irland-Sendungen mit `empf_plz = "DUB"` → `empf_plz_2 = "DU"`.

TB (Tagesbericht): Irische Eircodes wie `"D11"`, `"D12"`, `"D24"` → `_plz2("D11") = "D1"`.

**Folge:** AX-Cluster für SSC-IE-Touren hatten `empf_plz_2 = "D1"` statt `"DU"` — kein Match.

**Fix:** `normalize_empf_plz(plz, land)` normalisiert für `land = "IE"`:
- `"DUB"`, `"D11"`, `"D12"`, `"D24"` etc. → `"DU"` (alle Dublin-Codes → Dinas-Konvention)
- Cork (`"COR"`) → `"CO"`, Limerick (`"LIM"`) → `"LI"`, etc.

---

## 2. Pattern-Dokumentation

### Irische PLZ in TB (Eircode-Formate)

| TB-Wert | `_plz2` (alt) | `normalize_empf_plz` (neu) | Beschreibung |
|---------|--------------|---------------------------|--------------|
| `DUB`   | `DU`         | `DU`                      | Dublin legacy |
| `D11`   | `D1`         | `DU`                      | Dublin 11 (Ballymun) |
| `D12`   | `D1`         | `DU`                      | Dublin 12 |
| `D24`   | `D2`         | `DU`                      | Dublin 24 |
| `COR`   | `CO`         | `CO`                      | Cork |
| `LIM`   | `LI`         | `LI`                      | Limerick |
| `GAL`   | `GA`         | `GA`                      | Galway |

### `Von Name`-Muster in Sika.xlsx

| Von Name                             | Zeilen | Normalisiert zu |
|--------------------------------------|--------|----------------|
| Sika Supply Center AG                | 721    | 511241 (SSC)   |
| Sika Deutschland GmbH                | 364    | 491063 (Sika DE) |
| SIKA Deutschland GmbH               | 348    | 491063 (Sika DE) |
| DSV Solutions GmbH C/O Sika          | 24     | 491063 (Sika DE) |
| SIKA Deutschland CH AG KG            | 17     | 491063 (Sika DE) |
| Sika Automotive AG c/o LSU Schäberl  | 11     | 491063 (Sika DE) |
| ERKA Internationale Spedition GmbH   | 8      | 491063 (Sika DE) |
| andere                               | 9      | 491063 (Sika DE) |

### `Nach Ort`-Parsing (fallback)

`extract_plz_from_nach_ort()` wird nur als Fallback aktiviert wenn TB keine PLZ liefert.
In den aktuellen Daten haben alle IE/ES-Cluster TB-Matches mit befüllter PLZ — kein echter
Fallback-Einsatz. Die Funktion ist für zukünftige Datenlücken vorbereitet:

| Beispiel `Nach Ort`      | Land | Ergebnis |
|--------------------------|------|---------|
| `"Dublin 17"`            | IE   | `"17"` |
| `"Dublin IP"`            | IE   | `"IP"` |
| `"Barcelona 08021"`      | ES   | `"08"` |
| `"LU-1471 Luxembourg"`   | LU   | `"14"` |
| `"Wien 1010"`            | AT   | `"10"` |
| `"London EC1A"`          | GB   | `"EC"` |
| `"Dublin (Ballymun)"`    | IE   | `None` (kein PLZ erkannt, TB-Wert verwendet) |

---

## 3. Coverage-Statistik: `plz_source`

Nach dem Fix, über alle 502 AX-Cluster:

| `plz_source`       | Cluster | Bedeutung |
|--------------------|---------|-----------|
| `field`            | 458 (91.2%) | PLZ aus TB `Empfänger PLZ` (normalisiert) |
| `missing`          | 44 (8.8%)  | Kein TB-Match + kein `Nach Ort` PLZ — April 2026 beyond TB |
| `parsed_nach_ort`  | 0          | Kein Fallback-Einsatz nötig |

Die 44 `missing`-Cluster haben Leistungsdatum ≥ 2026-03-31 (jenseits TB-Fenster) und
erhalten daher `empfaenger_plz_distinct = []` → family_key-Anteil leer.

---

## 4. Vergleichstabelle: Etappe 8f vs. Etappe 8h

| Kennzahl                  | Etappe 8f | Etappe 8h | Δ   |
|---------------------------|-----------|-----------|-----|
| Familien gesamt           | 81        | 81        | 0   |
| davon mit Dinas-Seite     | 50        | 50        | 0   |
| davon mit AX-Seite        | 49        | 56        | +7  |
| **davon beidseitig**      | **18**    | **25**    | **+7** |
| Mit Unterfakturierung     | 5         | 8         | +3  |
| Orphan Dinas (kein AX)    | 32        | 25        | −7  |
| Orphan AX (kein Dinas)    | 37        | 39        | +2  |
| ax_coverage_gap (Familien)| 17        | 7         | −10 |
| ax_coverage_gap (€)       | 827.784 € | 55.520 €  | −772.264 € |

**7 neue bilaterale Matches** — alle durch den KNR-Fix (SSC-Routen zu IE/ES/GB
jetzt korrekt unter 511241 angelegt).

**3 neue Unterfakturierungs-Familien** entdeckt (SSC-Routen jetzt vergleichbar):
- `511241|70|38|ssc_stellplatz` (1.820 €)
- `511241|70|47|ssc_stellplatz` (1.153 €)  
- `511241|70|DU|ssc_stellplatz` (878 €)

### Wiederhergestellte Familien (10 von 10 `fehlt_in_ax_clusters`)

| Familie (Dinas) | Ursache | Status nach Fix |
|-----------------|---------|----------------|
| `511241\|70\|17\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|19\|ssc_stellplatz` | KNR-Bug | AX-Orphan (kein Dinas-Pendant mehr) |
| `511241\|70\|20\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|IP\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|LS\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|AL\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|DU\|ssc_stellplatz` | KNR-Bug + IE-PLZ-Bug | ✓ bilateral |
| `511241\|70\|28\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|41\|ssc_stellplatz` | KNR-Bug | ✓ bilateral |
| `511241\|70\|LU\|ssc_stellplatz` | KNR-Bug | AX-Orphan |

*Hinweis: `511241|70|19` und `511241|70|LU` haben AX-Cluster aber kein aktuelles Dinas-Pendant
mehr → erscheinen als AX-Orphan, nicht mehr als Gap.*

---

## 5. Verbleibende `ax_coverage_gap`-Familien (7) — EUR-Hochrechnung

Diese Familien haben TB-Sendungen POST-Migration, aber **keine Entsprechung in Sika.xlsx** —
echte Fakturierungslücken.

| Familie | Dinas-Fracht | Letzter Dinas | Clusters | TB POST* | Klassifikation |
|---------|-------------|---------------|----------|---------|----------------|
| `527406\|70\|28\|sika_atm_ch` | 34.172 € | 2025-08-13 | 10 | 2.081 | `echte_rechnungsstellung_fehlt` |
| `527406\|70\|36\|sika_atm_ch` | 20.126 € | 2025-06-16 | 5 | 1.327 | `echte_rechnungsstellung_fehlt` |
| `527406\|70\|29\|sika_atm_ch` | 528 € | 2025-08-01 | 1 | 622 | `echte_rechnungsstellung_fehlt` |
| `491063\|72\|95\|sika_de_stellplatz` | 296 € | 2025-03-10 | 2 | 394 | `echte_rechnungsstellung_fehlt` |
| `491063\|41\|72\|sika_de_stellplatz` | 234 € | 2025-02-20 | 1 | ~10.000** | `echte_rechnungsstellung_fehlt` |
| `491063\|47\|70\|sika_de_stellplatz` | 164 € | 2025-07-28 | 1 | ~9.000** | `echte_rechnungsstellung_fehlt` |
| `491063\|LU\|72\|sika_de_stellplatz` | 0 € | 2025-02-25 | 2 | ~10.000** | `echte_rechnungsstellung_fehlt` |

\* TB-Rows POST-Migration mit entsprechendem PLZ-Präfix  
\*\* Hohe Zahl: PLZ-Präfix „72" (Stuttgart) matcht viele Routen; tatsächliche Fahrten
dieser spezifischen inbound-Route deutlich geringer (kein Dinas-Pendant vorhanden)

### EUR-Hochrechnung für ATM-CH-Gaps

Die ATM-CH-Familien (527406) haben keine DLV-Sätze und `stp = NaN` in Dinas (Tarifgruppe
`sika_atm_ch` — gewichtsbasiert). Daher kein EUR/Einheit verfügbar. Als Näherung:

- **`527406|70|28`** (28xxx = Frankreich/Italien): ~3.400 €/Cluster × 2.081 TB-Rows / 
  (~10 Rows pro Cluster) ≈ **~70.000 € potentielle Fehlbuchung** p.a. (sehr grob)
- **`527406|70|36`** (36xxx = Italien): ähnliche Größenordnung, weniger Volumen

Die genannten Beträge sind **Annäherungswerte**. Für eine präzise Hochrechnung sind die
aktuellen DLV-Sätze für ATM-CH-Routen (527406) und der Sendungsvergleich gegen Tagesbericht
erforderlich.

---

## 6. Known Issues

1. **44 Cluster mit `plz_source = "missing"`**: Leistungsdatum 2026-03-31 bis 2026-04-16,
   jenseits des TB-Fensters (Ende 2026-03-31). Diese Cluster sind korrekt identifiziert;
   kein Fix nötig — TB-Daten werden für Q2/2026 erwartet.

2. **`511241|70|19|ssc_stellplatz` jetzt AX-Orphan** (nicht mehr Gap): 6 AX-Cluster vorhanden,
   aber kein aktives Dinas-Pendant. Die Dinas-Aktivität endete 2025-07-01 — Lane möglicherweise
   nach Migration gewechselt oder auf anderen Cluster konsolidiert.

3. **ATM-CH-Gaps (527406)** bleiben ungelöst: 3 Familien, 54.826 € Dinas-Fracht.
   Diese sind genuine Fakturierungslücken — nicht durch PLZ/KNR-Fix lösbar.
   Empfehlung: manuelle Prüfung der betroffenen Sendungen (28xxx / 36xxx / 29xxx Zielgebiete).

---

*Bericht generiert von Etappe 8h, 2026-04-19.*
