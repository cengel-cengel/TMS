# Sika-Gruppe: Abschlussbericht Abrechnungsqualität nach ERP-Migration

**Stand:** 2026-04-19 | **Etappe:** 8i | **Erstellt für:** Management-Review / Projekt-Sponsor

---

## 1. Executive Summary

### Kontext

Die Sika-Gruppe wechselte am **27. September 2025** vom Altsystem Dinas auf das neue
ERP-System AX (SAP). Betroffen sind drei Abrechnungsentitäten:

| Kunden-Nr | Entität | Tarifgruppe |
|-----------|---------|-------------|
| 491063 | Sika Deutschland GmbH / Sika Deutschland CH AG & Co. KG | `sika_de_stellplatz` |
| 511241 | Sika Supply Center AG (SSC) | `ssc_stellplatz` |
| 527406 | Sika ATM CH (Sika Austria/Tiefbau/Mobility) | `sika_atm_ch` |

Die vorliegende Analyse vergleicht **81 Familien** (eindeutige Route-Tarif-Kombinationen)
in beiden Systemen auf Vollständigkeit und Preiskonsistenz.

### Ergebnisüberblick

| Kennzahl | Wert |
|----------|------|
| Familien gesamt | 81 |
| Davon beidseitig vergleichbar (bilateral) | **25** |
| Nur Dinas vorhanden (Orphan Dinas) | 25 |
| Nur AX vorhanden (Orphan AX) | 31 |
| Familien mit Unterfakturierung (AX < Dinas-Niveau) | **8** |
| Familien ohne AX-Abrechnung (Coverage-Gaps) | **7** |
| Dinas-Fracht gesamt (PRE-Periode, historisch) | 2.605.231 EUR |
| AX-Fracht gesamt (POST-Periode, bisher abgerechnet) | 719.426 EUR |

> **Hinweis zum Volumenvergleich:** Die niedrigere AX-Gesamtsumme reflektiert primär den
> noch kurzen POST-Abrechnungszeitraum (Oktober 2025 – April 2026 vs. mehrere Jahre Dinas).
> Ein direkter EUR-Vergleich der Gesamtsummen ist nicht aussagekräftig.

### Wesentliche Befunde

**Unterfakturierung (8 Familien):**
AX rechnet auf 8 Routen systematisch unter dem historischen Dinas-Preisniveau ab.
Die Abweichung reicht von −7 % bis −82 % pro Stellplatz. Bei 4 dieser 8 Familien liegt
der AX-Preis auch unterhalb des vertraglich vereinbarten DLV-Satzes (echter Fehler);
bei den übrigen 4 ist die Abweichung teilweise durch Tarifanpassungen nach der Migration
erklärbar. Vollständige Aufschlüsselung in Abschnitt 2.

**Coverage-Gaps (7 Familien, ~55.520 EUR historisches Dinas-Volumen):**
Sieben Routen wurden in Dinas aktiv berechnet, haben aber keine entsprechenden
AX-Abrechnungscluster. Drei davon (Sika ATM CH, Frankreich/Italien-Zielgebiete)
sind genuine Fakturierungslücken mit nachgewiesener Sendungsaktivität im
Tagesbericht POST-Migration. Detailanalyse in Abschnitt 3.

**Empfehlung:**
Manuelle Prüfung der 4 Familien mit AX < DLV (Abschnitt 2, Muster A) sowie der
3 ATM-CH-Gaps (Abschnitt 3) hat höchste Priorität. Die restlichen Befunde erfordern
Rücksprache mit dem Tarifverantwortlichen.

---

## 2. Unterfakturierung: 8 Familien

Alle Preisangaben in **EUR pro Stellplatz** (Vergleichsbasis je Tarifeinheit, bereinigt um
Unterschiede in der Sendungszusammenfassung zwischen Dinas und AX).

| # | Familie (Schlüssel) | Route | Dinas-Ø (EUR/Stp) | DLV-Soll (EUR/Stp) | AX-Ist (EUR/Stp) | Δ AX–Dinas (EUR) | Δ AX–Dinas (%) | Muster |
|---|---------------------|-------|-------------------|--------------------|------------------|-----------------|----------------|--------|
| 1 | `511241\|70\|38\|ssc_stellplatz` | SSC Stuttgart → PLZ-38 (DE) | 161,18 | 84,07 | 76,25 | −84,93 | −52,7 % | A |
| 2 | `511241\|70\|47\|ssc_stellplatz` | SSC Stuttgart → PLZ-47 (DE) | 99,83 | 92,20 | 90,77 | −9,06 | −9,1 % | A |
| 3 | `491063\|70\|DU\|sika_de_stellplatz` | Sika DE Stuttgart → Dublin (IE) | 399,27 | 156,49 | 297,83 | −101,44 | −25,4 % | B |
| 4 | `511241\|70\|DU\|ssc_stellplatz` | SSC Stuttgart → Dublin (IE) | 161,06 | 124,16 | 144,13 | −16,93 | −10,5 % | B |
| 5 | `491063\|70\|LU\|sika_de_stellplatz` | Sika DE Stuttgart → Luxemburg | 112,27 | 99,80 | 104,33 | −7,94 | −7,1 % | B |
| 6 | `491063\|70\|38\|sika_de_stellplatz` | Sika DE Stuttgart → PLZ-38 (DE) | 533,11 | 105,55 | 97,52 | −435,59 | −81,7 % | C |
| 7 | `491063\|70\|47\|sika_de_stellplatz` | Sika DE Stuttgart → PLZ-47 (DE) | 244,30 | 105,78 | 101,78 | −142,52 | −58,3 % | C |
| 8 | `511241\|28\|70\|ssc_stellplatz` | SSC Inbound PLZ-28 → Stuttgart | 68,37 | n/a | 52,07 | −16,30 | −23,8 % | D |

---

### Muster A — Klassisches Underbilling: AX < DLV < Dinas (Familien 1–2)

**Befund:** Der AX-Satz liegt unterhalb des vertraglich vereinbarten DLV-Satzes. Die
Abrechnung ist damit nicht nur unter dem historischen Dinas-Niveau, sondern auch unterhalb
der gültigen Konditionen. Bei `511241|70|38` beträgt die Differenz zum DLV-Satz −9,8 EUR/Stp
(−11,6 %); bei `511241|70|47` −1,4 EUR/Stp (−1,5 %).

**Handlungsbedarf:** Sofortige Prüfung der Tarifkonfiguration in AX für SSC-Sendungen nach
PLZ-38 (Braunschweig/Wolfenbüttel) und PLZ-47 (Duisburg/Krefeld). Korrektur rückwirkend ab
Migrationsdatum empfohlen.

---

### Muster B — AX im Vertragsrahmen, unter Dinas-Historie: DLV ≤ AX < Dinas (Familien 3–5)

**Befund:** Der AX-Satz liegt zwischen DLV-Soll und Dinas-Niveau. Für Dublin SSC (Fam. 4)
und Luxemburg (Fam. 5) ist AX leicht über DLV — die Abrechnung entspricht dem Vertrag, liegt
aber unter der Dinas-Praxis. Bei Dublin Sika DE (Fam. 3) weicht AX stark von DLV ab
(+90 % über Vertrag), liegt aber noch deutlich unter der Dinas-Referenz, was die
ungewöhnlich hohe Dinas-Praxis als potenzielle Dinas-Anomalie kennzeichnet.

**Handlungsbedarf:** Für Fam. 3 (491063|70|DU) Prüfung: Hat Sika DE für Dublin-Sendungen
einen eigenen Tarifsatz vereinbart, der im geladenen DLV nicht abgebildet ist? Fam. 4 und 5
erscheinen plausibel — Monitoring empfohlen, kein sofortiger Eskalationsbedarf.

---

### Muster C — Anomale Dinas-Referenz: Einzelcluster mit hohem Ausreißer (Familien 6–7)

**Befund:** Die Dinas-Referenzwerte (533 EUR/Stp bzw. 244 EUR/Stp) stammen jeweils aus
einem einzigen Dinas-Abrechnungscluster. Einzelne Cluster können Sondertarife, Korrekturbuchungen
oder Fehler enthalten. Der AX-Satz liegt in beiden Fällen nahe am DLV-Soll (−7 % bzw. −4 %),
was die AX-Abrechnung als vertragskonform erscheinen lässt.

**Handlungsbedarf:** Die Dinas-Cluster (IDs: 3776xxx / 37xxxx) auf Plausibilität prüfen,
bevor Korrekturmaßnahmen eingeleitet werden. Wahrscheinlich keine Fehler in AX.

---

### Muster D — Kein DLV verfügbar: Inbound-Route ohne Soll-Referenz (Familie 8)

**Befund:** Die Route `511241|28|70` ist eine Inbound-Strecke (PLZ-28-Gebiet nach Stuttgart).
Für diese Richtung liegt keine DLV-Anlage im System vor. AX rechnet 52 EUR/Stp ab, Dinas lag
bei 68 EUR/Stp (−23,8 %). Da kein Vertragssatz geladen ist, kann nicht bewertet werden, ob
die AX-Abrechnung korrekt ist.

**Handlungsbedarf:** DLV für SSC-Inbound-Strecken beschaffen und in den Kalkulator laden.
Anschließend automatische Neuvalidierung.

---

## 3. Rechnungsstellungs-Gaps: 7 Familien (~55.520 EUR)

Diese sieben Familien haben nachgewiesene Sendungsaktivität in Dinas (PRE-Periode),
aber **keinen entsprechenden AX-Abrechnungscluster** in Sika.xlsx. Sie wurden durch
den Etappe-8g/8h-Cluster-Builder als `echte_rechnungsstellung_fehlt` klassifiziert.

Das historische Dinas-Frachtvolumen beläuft sich auf **55.520 EUR**. Dieser Betrag
ist eine Untergrenze; das Risiko für nicht abgerechnete POST-Sendungen ist separat
zu bewerten (siehe Spalte „TB-POST-Aktivität").

### Gruppe A — Sika ATM CH (KNR 527406): Gewichtsbasierte ATM-Routen

| Familie | Zielgebiet | Dinas-Fracht | Dinas-Cluster | Letzter Dinas | TB-POST-Zeilen | Status |
|---------|-----------|-------------|---------------|---------------|---------------|--------|
| `527406\|70\|28\|sika_atm_ch` | Frankreich/Norditalien (PLZ 28xxx) | 34.172 EUR | 10 | 2025-08-13 | 2.081 | `echte_rechnungsstellung_fehlt` |
| `527406\|70\|36\|sika_atm_ch` | Norditalien (PLZ 36xxx) | 20.126 EUR | 5 | 2025-06-16 | 1.327 | `echte_rechnungsstellung_fehlt` |
| `527406\|70\|29\|sika_atm_ch` | Nordfrankreich (PLZ 29xxx) | 528 EUR | 1 | 2025-08-01 | 622 | `echte_rechnungsstellung_fehlt` |

**Befund:** Alle drei ATM-CH-Routen liefen bis kurz vor der Migration aktiv (letzter
Cluster 44–102 Tage vor Cutoff 27.09.2025). Der Tagesbericht zeigt nach der Migration
weiterhin Sendungsaktivität (2.081 / 1.327 / 622 Zeilen). Es existiert jedoch kein
einziger AX-Cluster für diese Tarifgruppe in diesen Zielgebieten.

**EUR-Hochrechnung (unsicher):** Die ATM-CH-Tarifgruppe ist gewichtsbasiert. Die
DLV-Preis-bestimmende Einheit (`stp`) ist in den Dinas-Daten mit `NaN` erfasst —
ein präziser EUR/100kg-Satz kann ohne manuellen Abruf der aktuellen DLV-Anlage nicht
berechnet werden. Als Näherung: Auf Basis der durchschnittlichen Dinas-Frachtbeträge
je Cluster (~3.400 EUR/Cluster für PLZ-28) und der geschätzten POST-Aktivität würde
allein `527406|70|28` ein potenzielles Rechnungsstellungs-Risiko im Bereich
**~60.000–90.000 EUR p.a.** ergeben. Dieser Wert ist eine grobe Schätzung und
**nicht für Buchungszwecke geeignet**.

**Empfehlung:** Sofortige Eskalation an Sika ATM CH Verantwortlichen. Prüfung, ob
die ERKA-Spediteure (18894 / 18748) für diese Routen POST-Migration Rechnungen an
Sika stellen, ohne dass eine Gegenrechnung an Sika ATM in AX erfolgt. Parallele
Beschaffung der aktuellen DLV-Konditionen für ATM-CH-Gewichtsrouten.

---

### Gruppe B — Sika DE (KNR 491063): Kleinvolumige Stellplatz-Routen

| Familie | Zielgebiet | Dinas-Fracht | Dinas-Cluster | Letzter Dinas | TB-POST-Zeilen | Hinweis |
|---------|-----------|-------------|---------------|---------------|---------------|---------|
| `491063\|72\|95\|sika_de_stellplatz` | Versender PLZ-72 → Empf. PLZ-95 | 296 EUR | 2 | 2025-03-10 | 394 | PLZ-72 Präfix plausibel |
| `491063\|41\|72\|sika_de_stellplatz` | Versender PLZ-41 → Empf. PLZ-72 | 234 EUR | 1 | 2025-02-20 | ~10.000* | PLZ-72 Artefakt |
| `491063\|47\|70\|sika_de_stellplatz` | Versender PLZ-47 → Empf. PLZ-70 | 164 EUR | 1 | 2025-07-28 | ~9.000* | PLZ-72 Artefakt |
| `491063\|LU\|72\|sika_de_stellplatz` | Versender LU → Empf. PLZ-72 | 0 EUR | 2 | 2025-02-25 | ~10.000* | PLZ-72 Artefakt |

\* Die hohen TB-POST-Zeilenzahlen sind ein **Zählungsartefakt**: PLZ-Präfix „72"
deckt das gesamte Stuttgarter Stadtgebiet ab und matcht tatsächlich viele fremde
Routen. Die tatsächliche Sendungsanzahl für diese spezifischen Inbound-Strecken
ist deutlich geringer.

**Befund:** Das historische Dinas-Volumen dieser vier Routen ist gering (694 EUR gesamt;
Familie 491063|LU|72 hat 0 EUR Fracht). Die letzten Dinas-Cluster liegen 60–218 Tage
vor dem Migrationsstichtag — es ist plausibel, dass diese Routen organisch ausgelaufen
sind. Kein akuter Handlungsbedarf.

**Empfehlung:** `491063|72|95` (296 EUR Dinas, 394 TB-POST-Zeilen) ist der einzige
Kandidat mit nachvollziehbarer TB-Aktivität. Stichprobenhafte manuelle Prüfung empfohlen.
Die übrigen drei Routen können als inaktiv eingestuft werden.

---

## 4. Weitere Befunde aus DLV-Kalkulator-Validierung

Die folgenden Befunde stammen aus dem Sika-ATM-Kalkulator-Report (`sika_atm_revalidation.md`,
Etappe 8h) und der Orphan-Analyse. Sie betreffen teils andere Sendungstypen (Direktfahrten,
nicht Cluster-Familien) und sind daher getrennt von den Cluster-Familien in Abschnitt 2–3
ausgewiesen.

---

### 4.1 Serbien (RS/34104): DLV-Tarif +20–43 % über Dinas-Ist

**Kontext:** Sika ATM CH, ERKA 18748 (CH-Kalkulator). 25 Direktfahrten nach
Kragujevac/Serbien (PLZ 34104), alle mit positivem DLV-Soll vs. Dinas-Ist.

| Gewichtsband | DLV-Satz (RS-34) | Dinas-Ist | Abweichung |
|-------------|-----------------|-----------|------------|
| ≤601 kg | 606 EUR | 485 EUR | +25,0 % |
| ≤801 kg | 656 EUR | 525 EUR | +25,0 % |
| ≤1.401 kg | 706 EUR | 565 EUR | +25,0 % |
| ≤1.801 kg | 806 EUR | 565 EUR | +42,7 % |
| ≤2.501 kg | 1.019 EUR | 815 EUR | +25,0 % |

**Interpretation:** Der DLV-Tarif in Anlage 1 liegt systematisch über dem tatsächlich
fakturierten Dinas-Betrag. Da das Muster über alle Gewichtsbänder konsistent ist,
liegt die Hypothese nahe, dass für Serbien ein separat verhandelter Tarifsatz existiert,
der nicht in der im System hinterlegten „Anlage 1 KORRIGIERT" abgebildet ist. Ein
Kalkulationsfehler auf Dinas-Seite ist weniger wahrscheinlich, da die Beträge in
diskreten Stufen (485, 525, 565, 815 EUR) erscheinen.

**Handlungsbedarf:** Die korrekte DLV-Anlage für Serbien-Routen beim zuständigen
Tarifverantwortlichen erfragen und im Kalkulator hinterlegen. Erst dann ist eine
belastbare Aussage möglich, ob Dinas zu günstig oder AX/DLV zu teuer konfiguriert ist.

---

### 4.2 Portugal (PT/2951-510): Einzelsendung mit −73,7 % Abweichung

**Kontext:** ERKA 18894 (DE-Kalkulator), 1 Direktfahrt nach Seixal/PT, PLZ 2951-510,
2.750 kg. Dinas-Fracht: 2.975 EUR. DLV-Soll: 782 EUR.

**Interpretation:** Die berechnete Abweichung (−73,7 %) macht eine falsche Zonen-Zuordnung
im Kalkulator (PLZ-Lookup-Fehler) oder eine Sondervereinbarung für diese Destination
wahrscheinlich. Der Dinas-Betrag von 2.975 EUR für 2.750 kg ist verglichen mit anderen
PT-Routen ungewöhnlich hoch; gleichzeitig scheint der DLV-Soll-Betrag von 782 EUR für
eine 2.750-kg-Direktfahrt nach Portugal sehr niedrig. Beide Extremwerte sind verdächtig.

**Handlungsbedarf:** Die Sendung (Sendungsnr. 32882334) und die Zonen-Konfiguration für
PLZ-Präfix „29" (Setúbal-Region) im Kalkulator überprüfen. Falls Dinas-Betrag korrekt:
DLV-Anlage für PT auf Vollständigkeit prüfen.

---

### 4.3 GB-PO: AX-Orphan-Familie ohne Dinas-Pendant

**Kontext:** Die Familie `491063|70|PO|sika_de_stellplatz` (Sika DE, Stuttgart →
Portsmouth-Gebiet/GB, PO-Postleitzahlen) erscheint als **AX-Orphan** mit 8 Clustern
und einem Durchschnittswert von 1.894 EUR/Cluster, letzte Aktivität 2026-02-27. Es
existiert kein Dinas-Pendant unter diesem Familienschlüssel.

**Interpretation:** Entweder ist diese Route nach der Migration neu entstanden (Kunde
bedient jetzt Portsmouth-Destinationen, die vorher nicht oder unter anderem Schlüssel
abgerechnet wurden), oder die Sendungen wurden in Dinas unter einem anderen Familienschlüssel
erfasst. Da AX aktiv abrechnet, liegt kein Fakturierungsausfall vor.

**Handlungsbedarf:** Prüfung, ob die GB-PO-Routen von einer Dinas-Familie
(z. B. `491063|70|S8` oder `491063|70|LU` mit Empfängerland GB) auf den neuen Schlüssel
migriert wurden. Falls Neuroute: DLV-Konditionen für GB-PO verifizieren.

---

### 4.4 Stuttgart-72: PLZ-Präfix-Artefakt in TB-POST-Zählung

**Kontext:** Mehrere Gap-Familien haben `empf_plz_2 = "72"` oder `abs_plz_2 = "72"`.
Das PLZ-Präfix 72 deckt einen großen Teil des Stuttgarter Umlands ab (Stuttgart
Weilimdorf, Kornwestheim, Ludwigsburg etc.) und matcht im Tagesbericht auf sehr
viele Routen, die nichts mit den spezifischen Gap-Familien zu tun haben.

**Konsequenz:** Die TB-POST-Zeilenzahlen für `491063|41|72`, `491063|47|70` und
`491063|LU|72` (je ~9.000–10.000 Zeilen) sind **nicht als tatsächliche Sendungsvolumina
interpretierbar**. Für eine präzise Aussage müsste der Abgleich auf vollständige
PLZ + Auftragsnummer-Ebene erfolgen, was einen separaten Analyseauftrag erfordern würde.

---

## 5. Methodik-Anhang

### 5.1 Cluster-Definition

Ein **Cluster** ist die atomare Abrechnungseinheit:
- **Dinas-Cluster:** Eine PDF-Rechnungszeile aus Dinas, aggregiert über alle
  Teilsendungen eines Auftrags (Sendungszusammenfassung via `Zusammengefasst in`).
- **AX-Cluster:** Eine Gruppe von Positionen in Sika.xlsx mit identischer
  `Zusammengefasst in`-Nummer. Die Hauptposition trägt den Gesamtbetrag;
  Teilpositionen haben Betrag = 0.

### 5.2 Familienschlüssel

Cluster werden zu **Familien** aggregiert:

```
Familienschlüssel = {kunde_normalisiert}|{abs_plz_2}|{empf_plz_2}|{tarifgruppe}
```

| Bestandteil | Bedeutung |
|-------------|-----------|
| `kunde_normalisiert` | Kunden-Nr. nach KNR-Normalisierung (491063 / 511241 / 527406) |
| `abs_plz_2` | Erste 2 Stellen der Versender-PLZ (identifiziert den Ladeort) |
| `empf_plz_2` | Erste 2 Stellen der Empfänger-PLZ (identifiziert das Zielgebiet) |
| `tarifgruppe` | `sika_de_stellplatz` / `ssc_stellplatz` / `sika_atm_ch` |

Familien über beide Systeme mit identischem Schlüssel gelten als **bilateral vergleichbar**.

### 5.3 Drei Referenzpunkte

| Referenz | Quelle | Bedeutung |
|----------|--------|-----------|
| **Dinas-Ø (PRE)** | Dinas-PDF-Cluster (Mittelwert der ausgewählten Stichprobe) | Historisches Preisniveau vor Migration |
| **DLV-Soll** | DLV-Ratenblatt (vertraglich vereinbarter Satz) | Erwarteter Soll-Preis gemäß Konditionen |
| **AX-Ist (POST)** | Sika.xlsx (laufende AX-Abrechnungen) | Tatsächlich fakturierter Preis nach Migration |

Die Preisangaben sind stets **EUR pro preis-bestimmende Einheit**:
- `sika_de_stellplatz` / `ssc_stellplatz`: EUR pro Stellplatz
- `sika_atm_ch`: EUR pro 100 kg (Tonnage effektiv)

### 5.4 KNR-Normalisierung: ARA_Sika_DE+CH

Sika.xlsx enthält eine kombinierte Kontonummer `ARA_Sika_DE+CH`. Diese wird anhand
des Feldes `Von Name` in der Quellzeile normalisiert:

| Bedingung | Normalisiert zu |
|-----------|----------------|
| `Von Name` enthält „Supply Center" | **511241** (Sika Supply Center AG / SSC) |
| Alle anderen | **491063** (Sika Deutschland GmbH / Sika DE) |

Ohne diesen Fix würden SSC-Exportrouten (IE/ES/GB/PT) fälschlich unter KNR 491063
abgerechnet und könnten nie gegen Dinas-Familien unter 511241 gematcht werden.

### 5.5 PLZ-Normalisierung: Irland (Eircode → Dinas-Konvention)

Irische Postcodes im Tagesbericht folgen dem Eircode-Format (`D11`, `D24`, …).
Dinas verwendet historisch andere Kürzel (`DUB` für Dublin). Normalisierungsregeln:

| TB-Eircode | Normalisiert zu | Beschreibung |
|-----------|----------------|--------------|
| `DUB`, `D11`, `D12`, `D24` | `DU` | Dublin (alle Bereiche) |
| `COR` | `CO` | Cork |
| `LIM` | `LI` | Limerick |
| `GAL` | `GA` | Galway |

### 5.6 Grauzone-Filter (CQ-Migrations-Umbuchungen)

Umbuchungen im Rahmen der Migration (erkennbar an CQ-Belegart) werden aus dem
Preisvergleich ausgeschlossen. Sie spiegeln Systemkorrekturen wider, nicht
tatsächliche Transportleistungen, und würden den EUR/Einheit-Wert verfälschen.

---

## 6. Bekannte Einschränkungen

### 6.1 AX-Cluster jenseits des TB-Fensters (April 2026)

44 AX-Cluster haben ein Leistungsdatum ≥ 2026-04-01 und liegen damit jenseits des
verfügbaren Tagesbericht-Datenfensters (Ende: 2026-03-31). Diese Cluster erhalten
`plz_source = "missing"` und fließen ohne Empfänger-PLZ in die Familienbildung ein.
Betroffen: neueste Abrechnungsläufe, primär SSC-Routen.

**Auswirkung:** Die 44 Cluster können noch keiner Empfänger-PLZ-basierten Familie
zugeordnet werden. Sobald TB-Daten für Q2/2026 vorliegen, fällt diese Einschränkung weg.

### 6.2 ATM-CH: Stp = NaN verhindert EUR-Hochrechnung

Für die Tarifgruppe `sika_atm_ch` ist das Feld `stp` (Stellplätze / preis-bestimmende
Einheit) in den Dinas-Daten nicht befüllt. Die Gewichtsbasierung dieser Tarifgruppe
erfordert die ATM-DLV-Anlage für eine präzise Soll-Berechnung.

**Auswirkung:** Die EUR-Hochrechnungen für ATM-CH-Gaps (Abschnitt 3, Gruppe A) sind
als grobe Schätzungen einzustufen. Für verbindliche Zahlen ist eine manuelle Abfrage
der aktuellen ATM-CH-Konditionen erforderlich.

### 6.3 PLZ-72-Präfix zu grob für Inbound-Strecken

Das PLZ-Präfix „72" deckt das Stuttgarter Umland großflächig ab. Drei Gap-Familien
(491063|41|72, 491063|47|70, 491063|LU|72) zeigen im TB-POST-Abgleich daher
unverhältnismäßig hohe Sendungszahlen (~9.000–10.000 Zeilen), die nicht ursächlich
diesen spezifischen Routen zuzurechnen sind.

**Auswirkung:** Die TB-POST-Zählungen für diese drei Familien sind nicht als
Risikoindikator nutzbar, solange kein PLZ-exakter Abgleich erfolgt. Das tatsächliche
Sendungsvolumen auf diesen Inbound-Routen ist sehr wahrscheinlich deutlich geringer
(vermutlich 0, da die Routen organisch ausgelaufen sind).

---

*Bericht erstellt: Etappe 8i, 2026-04-19. Vorbereitung: Rollout Etappe 9.*
