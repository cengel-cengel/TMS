# Sika ATM — DLV Findings

## 1. Kunden-Entitäten (KNRs)

| KNR | Name | Abrechnungsstrecken Betrag | Anmerkung |
|---|---|---|---|
| **413276** | Sika ATM DE | 89 Zeilen, alle Betrag=0 | Sub-Entität; Abrechnung läuft wohl über 527406 oder ARA_Sika_DE+CH |
| **493163** | Sika ATM DE 2nd | 0 Zeilen in POST-Daten | Komplett absent in Abrechnungsstrecken |
| **527406** | Sika ATM CH | 387 non-zero Zeilen (EUR) | Aktive Abrechnung; Versand DE→IT/GB/ES/RS/PT |

Alle drei KNRs teilen sich **eine** Anlage 1 (kein KNR-spezifischer Tarifblock).

---

## 2. Carrier & Vertragseckdaten

- **Carrier**: ERKA GmbH, Motorstr. 8, DE-70499 Stuttgart
- **Auftraggeber**: Sika Automotive HH u. CH (Hamburg + Switzerland)  
- **Versendungsort**: D-70499 (Sika LSU M7 plant, Stuttgart/Leinfelden-Echterdingen)
- **DLV-Laufzeit**: 01.07.2024 – 30.06.2026
- **Währung**: EUR für alle dokumentierten Sendungen

---

## 3. Kanonische Rate-Datei

**Datei**: `2025/20250728_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_01.07.2024 bis 30.06.2026_KORRIGIERT.xlsx`  
**MD5**: `bb5301f98b28a90b44a726e9ecced05e`  
**Pfad (absolut)**: `/home/user/TMS/data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Automotive/2025/20250728_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_01.07.2024 bis 30.06.2026_KORRIGIERT.xlsx`

**Validierung** (4 unabhängige Fälle aus KNR 527406 Abrechnungsstrecken):

| PLZ-Zone | Gew. (kg) | Band | Anlage-1-Rate | Betrag ABR | Abw. |
|---|---|---|---|---|---|
| IT-10 (Torino) | 6 | 1–101 | 51.65 € | 51.65 € | 0.00% ✓ |
| IT-10 (Torino) | 530 | 502–601 | 71.90 € | 71.90 € | 0.00% ✓ |
| IT-10 (Torino) | 735 | 702–801 | 96.05 € | 96.05 € | 0.00% ✓ |
| IT-66 (Atessa) | 92 | 1–101 | 79.75 € | 79.75 € | 0.00% ✓ |

Die 2026-Upload-Dateien (`V_FRA_7042_O_IT_ALL_Sika_Automotive.xlsx` etc.) haben **abweichende Raten** (Bsp. IT-00 Band-0: 60.2 vs. 62.91) und stimmen **nicht** mit den Abrechnungsbeträgen überein → **nicht** für den Calculator verwenden.

---

## 4. Sheet-Struktur (Anlage 1 KORRIGIERT)

22 Sheets:

| # | Sheet-Name | Inhalt |
|---|---|---|
| 0 | `Sonderleistungen` | Nebenleistungszuschläge |
| 1 | `Dieselfloater` | Dieselzuschlag-Tabelle |
| 2 | `Tarif DE ex. Sika LSU M7` | Deutschland (alle Raten = 0) |
| 3 | `Tarif F ex. Sika LSU M7` | Frankreich |
| 4 | `Tarif GB ex. Sika LSU M7` | Großbritannien |
| 5 | `Tarif IT ex. Sika LSU M7 ` | Italien ✓ (geprüft) |
| 6 | `Tarif PL ex. Sika LSU M7` | Polen |
| 7 | `Tarif CZ ex. Sika LSU M7` | Tschechien |
| 8 | `Tarif ES ex. Sika LSU M7` | Spanien |
| 9 | `Tarif PT ex. Sika LSU M7 ` | Portugal |
| 10 | `Tarif SK ex. Sika LSU M7 ` | Slowakei |
| 11 | `Tarif RO ex. Sika LSU M7 ` | Rumänien |
| 12 | `Tarif HU ex. Sika LSU M7 ` | Ungarn |
| 13 | `Tarif Serb ex. Sika LSU M7 ` | Serbien (RS) |
| 14 | `Tarif BE ex. Sika LSU M7 ` | Belgien |
| 15 | `Tarif DK ex. Sika LSU M7 ` | Dänemark |
| 16 | `Tarif NL ex. Sika LSU M7 ` | Niederlande |
| 17 | `Tarif SE ex. Sika LSU M7 ` | Schweden |
| 18 | `Tarif A ex. Sika LSU M7  ` | Österreich |
| 19 | `Tarif CH ex. Sika LSU M7 ` | Schweiz (**alle Raten = 0**) |
| 20 | `Tarif SI ex. Sika LSU M7` | Slowenien |
| 21 | `Tarif LUX ex. Sika LSU M7` | Luxemburg |

---

## 5. Raten-Struktur (pro Tarif-Sheet)

### 5.1 Zeilen-Layout

```
Row 8:   Titel  (z.B. "Frachttarif für Transportdienstleistungen Italien")
Row 9:   Obere Bandgrenzen: [101, 201, 301, ..., 20501]   (60 Werte)
Row 10:  leer
Row 11:  ['PLZ / ab kg', 1, 102, 202, ..., 19902]          (60 Untergrenzen)
Row 12+: ['IT-00', rate0, rate1, ..., rate59]               (pro Zone)
```

### 5.2 Gewichtsbänder (60 Stück)

```
Band  0:    1 –   101 kg  (Mindestgewicht)
Band  1:  102 –   201 kg
Band  2:  202 –   301 kg
...
Band 30: 3002 – 3701 kg
Band 31: 3702 – 4301 kg   (Sprung: nicht immer 100 kg-Schritte)
...
Band 59: 19902 – 20501 kg
```

Bandgrenzen (upper bounds vollständig):
`[101, 201, 301, 401, 501, 601, 701, 801, 901, 1001, 1101, 1201, 1301, 1401, 1501, 1601, 1701, 1801, 1901, 2001, 2101, 2201, 2301, 2401, 2501, 2601, 2701, 2801, 2901, 3001, 3101, 3701, 4301, 4901, 5501, 6101, 6701, 7301, 7901, 8501, 9101, 9701, 10301, 10901, 11501, 12101, 12701, 13302, 13902, 14502, 15102, 15702, 16302, 16902, 17502, 18102, 18702, 19302, 19902, 20501]`

### 5.3 Raten-Formel

```
rate = tarif_sheet[zone][band_index(tonnage_kg)]
```

Rate ist **flat pro Sendung** (nicht per kg, nicht per 100 kg). Einheit: EUR/Sendung.

Bandsuche: erstes Band, dessen Obergrenze ≥ tonnage_kg.

Für tonnage_kg > 20501 kg: letztes Band (Band 59) verwenden.

### 5.4 Zonen-Format

| Land | Sheet-Name | Zonen-Label-Format | PLZ-Zuordnung |
|---|---|---|---|
| IT | `Tarif IT ex. Sika LSU M7 ` | `IT-{XX}` | erste 2 Ziffern der 5-stelligen PLZ |
| ES | `Tarif ES ex. Sika LSU M7` | `ES-{XX}` | erste 2 Ziffern der 5-stelligen PLZ |
| FR | `Tarif F ex. Sika LSU M7` | `FR-{XX}` | erste 2 Ziffern der 5-stelligen PLZ |
| GB | `Tarif GB ex. Sika LSU M7` | vermutlich `GB-{XX}` | erste 2 Zeichen der Postcode-Area |
| PT | `Tarif PT ex. Sika LSU M7 ` | vermutlich `PT-{X}` | erste Ziffer der 4-stelligen PLZ |
| BE | `Tarif BE ex. Sika LSU M7 ` | vermutlich `BE-{X}` | erste Ziffer |
| RS | `Tarif Serb ex. Sika LSU M7 ` | vermutlich `RS-{XX}` | erste 2 Ziffern |
| AT | `Tarif A ex. Sika LSU M7  ` | vermutlich `A-{X}` | erste Ziffer |
| CH | `Tarif CH ex. Sika LSU M7 ` | n/a | alle Raten = 0 |

**Spalten-Header (Row 11):** `'PLZ / ab kg'` → bestätigt 2-stellige PLZ-Präfix-Logik.

---

## 6. Schweiz (CH) — Spezifika

### 6.1 Befund

- Das Sheet `Tarif CH ex. Sika LSU M7` enthält in **allen 4 Anlage-1-Versionen** ausschließlich Nullraten.
- Es existiert **keine** `V_FRA_7042_O_CH_*` Upload-Datei.
- In den Abrechnungsstrecken-Daten für KNR 527406 gibt es **keine** Zeilen mit `Nach Land = CH`.
- Alle KNR 527406 Sendungen gehen von `Von Land = DE` nach IT/GB/ES/RS/PT — nicht nach CH.

### 6.2 Interpretation

KNR 527406 ist die **Schweizer Rechnungseinheit** (Sika Automotive AG, Sitz CH), aber die Sendungen gehen **vom deutschen Werk (D-70499)** zu europäischen Kunden. ERKA hat keine nominierten Raten für DE→CH-Destinationen. „CH" im KNR-Namen bezeichnet die Rechnungsstell-Entität, nicht das Lieferzielland.

### 6.3 Konsequenz für Calculator

- `empf_land == 'CH'` → `TariffResult(basispreis=None)` mit Hinweis „ERKA nicht für CH nominiert"
- Kein CHF-Handling erforderlich (alle Beträge in EUR)

---

## 7. Diesel-Floater

**Quelle**: Sheet `Dieselfloater` in Anlage 1 KORRIGIERT

| Diesel-Preis (Ct/L, brutto) | Diesel-Zuschlag |
|---|---|
| ≤ 130 | −8.75% |
| 135 | −7.50% |
| 140 | −6.25% |
| 145 | −5.00% |
| 150 | −3.75% |
| 155 | −2.50% |
| 160 | −1.25% |
| **165–190** | **0%** (Basisbereich) |
| 195 | +1.25% |
| 200 | +2.50% |
| 205 | +3.75% |
| 210 | +5.00% |
| 215 | +6.25% |
| 220 | +7.50% |
| 225 | +8.75% |

Basispreis: 165,00 – 190,00 Ct/L (brutto).  
Update: monatlich (Grundlage: Vorvormonats-Durchschnitt).  
Quelle: https://archiv.en2x.de/verbraucherpreise/  
Schrittweite: ±1.25% je 5 Ct/L Abweichung vom Basisbereich.

Calculator gibt `diesel_surcharge = None` zurück (wird extern angewendet wie bei Hornschuch).

---

## 8. Sonderleistungen

Sheet `Sonderleistungen` enthält Nebenleistungszuschläge (Expresslieferung, Liftgate, etc.). Nicht im Scope des LTL-Basispreisrechners.

---

## 9. Validierungs-Datenstatus

### POST-Period (≥ 2025-10-02): Abrechnungsstrecken

| KNR | Zeilen | Non-zero Betrag | Validierbar? |
|---|---|---|---|
| 413276 | 89 | **0** | Nein — alle Betrag=0 |
| 493163 | **0** | 0 | Nein — fehlt komplett |
| 527406 | 464 | 387 | **Ja** — 387 Zeilen mit Betrag |

KNR 527406 POST-Destinationen: IT (188), GB (98), ES (57), RS (28), PT (15).  
Wichtig: Abrechnungsstrecken enthält keine PLZ-Spalte → Auftragsnummer-Join mit BI/Dinas-Daten erforderlich.

### PRE-Period (≤ 26.9.2025): Dinas SSC PDFs

- **107 PDFs** in `sika_ssc/Dinas SSC/`, Datum 2025-01-06 bis 2025-08-27
- Diese sind die primäre Quelle für PRE-Period-Validierungsfälle (≤ 26.9.2025)
- Erfordern PDF-Parsing (kein strukturiertes Excel-Format)

### ARA_Sika_DE+CH

1,504 Zeilen, 807 non-zero Betrag (IE/PT/ES/GB/IT). Möglicherweise kombiniertes Konto für KNR 413276 + 527406 (oder Teilmenge). Nicht direkt auf einzelne KNR zugeordnet.

---

## 10. Shared-Parser-Analyse

Alle 3 ATM-KNRs nutzen **dieselbe** Anlage 1 KORRIGIERT. Ein einziger Parser und eine einzige `_CACHE`-Instanz genügen:

```python
# _CACHE[(cc_sheet_name, zone_label)] → tuple[float, ...] (60 Rates)
# Beispiel: ('Tarif IT ex. Sika LSU M7 ', 'IT-10') → (51.65, 58.25, ...)
```

Sheet-Name-Mapping (country_code → sheet_name):

```python
_SHEET_MAP = {
    'DE': 'Tarif DE ex. Sika LSU M7',
    'FR': 'Tarif F ex. Sika LSU M7',
    'GB': 'Tarif GB ex. Sika LSU M7',
    'IT': 'Tarif IT ex. Sika LSU M7 ',
    'PL': 'Tarif PL ex. Sika LSU M7',
    'CZ': 'Tarif CZ ex. Sika LSU M7',
    'ES': 'Tarif ES ex. Sika LSU M7',
    'PT': 'Tarif PT ex. Sika LSU M7 ',
    'SK': 'Tarif SK ex. Sika LSU M7 ',
    'RO': 'Tarif RO ex. Sika LSU M7 ',
    'HU': 'Tarif HU ex. Sika LSU M7 ',
    'RS': 'Tarif Serb ex. Sika LSU M7 ',
    'BE': 'Tarif BE ex. Sika LSU M7 ',
    'DK': 'Tarif DK ex. Sika LSU M7 ',
    'NL': 'Tarif NL ex. Sika LSU M7 ',
    'SE': 'Tarif SE ex. Sika LSU M7 ',
    'AT': 'Tarif A ex. Sika LSU M7  ',
    'CH': None,   # alle Raten = 0, nicht nominiert
    'SI': 'Tarif SI ex. Sika LSU M7',
    'LU': 'Tarif LUX ex. Sika LSU M7',
}
```

Zone-Label-Konstruktion: `f"{cc_prefix}-{plz[:2]}"` für IT/ES/FR/GB/RS; `f"{cc_prefix}-{plz[0]}"` für PT/AT/BE (noch zu verifizieren für nicht-IT-Länder).

---

## 11. Offene Punkte (vor Freigabe zu klären)

1. **Zone-Format für GB/PT/AT/BE/RS**: Nur für IT verifiziert (`IT-{PLZ2}`). Vor Implementierung per Stichprobe aus Abrechnungsstrecken + BI prüfen.
2. **KNR 413276 / 493163**: Da beide in Abrechnungsstrecken keine non-zero Beträge haben, ist unklar, ob ein eigenständiger Calculator-Aufruf für diese KNRs sinnvoll ist oder ob alle Sendungen über 527406 abgerechnet werden.
3. **PRE-Period-Validierung**: Erfordert PDF-Extraktion aus `sika_ssc/Dinas SSC/` — komplex. Alternative: POST-Period-Validierung (KNR 527406) als primäre Validierungsbasis verwenden, da 4 Fälle bereits mit 0.00% Abweichung bestätigt.
4. **CHF-Fälle**: In allen verfügbaren Daten keine CHF-denominierten Beträge gefunden. Anforderung „≥1 CHF-Fall" eventuell nicht erfüllbar mit vorhandenen Daten.
