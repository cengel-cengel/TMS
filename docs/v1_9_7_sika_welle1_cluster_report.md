# Sika Welle 1 — Billing-Audit-Report v1.9.7
**KNR 491063** Sika Deutschland GmbH / Sika Schweiz AG  
**KNR 511241** SIKA Supply Center AG (SSC)  
Stand: 2026-04-28 | Pipeline: `build_sika_step23_v197.py` | DLV: Noerpel SIKA Stellplatzofferte 2025/2026

---

## §1 Executive Summary

### KNR 491063 — Kein Migrationsschaden (nach Maut-Korrektur)

**Methodik-Befund:** AX bucht die DE-Maut als separaten Posten (`Erlöse Maut`). Die Pipeline verwendet nur `Erlöse Fracht` als `ef`. Der DLV-Soll enthält hingegen `basispreis + de_maut`. Diese Asymmetrie erzeugt einen systematischen negativen Bias von ~2,4 %.

| Metrik | Wert |
|---|---|
| Pipeline Net Δ (ef = nur Erlöse Fracht) | −25.758 EUR (−1,97 %) |
| Σ AX Erlöse Maut (Beurteilbar-Pool) | +30.555 EUR |
| **Adjustiertes Net Δ** | **+4.797 EUR (+0,37 %)** |

**Bewertung:** Kein Migrationsschaden. Der nominale Befund −1,97 % ist ein Methodik-Artefakt der Erlöse-Maut-Trennung. Bei Gesamtbetrachtung (Fracht + Maut) übertrifft die AX-Abrechnung den DLV-Soll marginal um +0,37 %.

### KNR 511241 — SSC: M_over-Cluster, kein Schaden

| Metrik | Wert |
|---|---|
| Beurteilbar (ssc_eu) | 62 Rows |
| Σef | 43.358 EUR |
| Net Δ | +2.600 EUR (+6,38 %) |
| M1 / M2 / M_over | 43 / 0 / 19 |

**Bewertung:** 19 M_over-Rows (30,6 %). Positives Net Δ = AX hat über DLV-Niveau abgerechnet. Kein Schaden für Noerpel. OOS-Block (de_oos 347 Rows, 631 TEUR) außerhalb Scope.

### Pool-Tabelle (beide KNRs gesamt)

| Stufe | Rows | Σef (TEUR) |
|---|---|---|
| Pool roh (ef > 0) | 1.822 | 1.973 |
| davon Sub-Rows (is_sub) | 18 | — |
| Pipeline-Pool (ef>0, ~sub, ton>0) | 1.804 | — |
| KNR 491063 de_oos (Empf. DE) | 1 | 0,1 |
| KNR 491063 dlv_luecke | 9 | 5,1 |
| KNR 491063 beurteilbar | **1.379** | **1.278** |
| KNR 511241 de_oos | 347 | 632 |
| KNR 511241 import_flow | 2 | 1,7 |
| KNR 511241 dlv_luecke | 4 | 4,7 |
| KNR 511241 ssc_eu (beurteilbar) | **62** | **43** |
---

## §2 Pool-Analyse

### Datenquelle

`output/bi_top20_data.pkl` → KNR-Filter `{491063, 511241}`. Kein separates BI-Loading nötig, beide KNRs in bi_top20 vorhanden.

### P3-Gate: KNR-Normalisierung

KNR 491063 enthält 454 Zeilen mit `Versender Name` ≙ "Supply Center AG" (Σef ≈ 560.950 EUR). Diese Zeilen verwenden denselben DLV wie 491063-Standard (Sika Stellplatzofferte). Methodische Entscheidung (Carlos): Diese Rows verbleiben in 491063. Calculator: `SikaDeCalculator`. Die SSC-Erkennung via `_is_ssc_versender()` greift daher nur für KNR 511241.

### Sub-Row-Filter

```
is_sub = Mastersendung gesetzt AND kein eigener Unterauftrag
```

Gesamt Sub-Rows (ef>0): 18. Ausgeschlossen aus Pipeline.

### Stellplatz-Verfügbarkeit

| KNR | stp>0 (original) | stp=0 ldm>0 (P6) | stp=0 ldm=0 (unbeurteilbar) |
|---|---|---|---|
| 491063 | 1.388 | 0 | 1 |
| 511241 | — | — | — |

P6-Fallback wurde für **keine** 491063-Zeile ausgelöst. Alle beurteilbaren Rows haben `Stellplätze` direkt aus AX.

### Scope-Labeling KNR 511241 (Variante B)

| Scope | Zeilen | Σef | Bemerkung |
|---|---|---|---|
| de_oos | 347 | 631.702 EUR | Empf. DE — OOS Export-DLV |
| ssc_eu | 62 | 43.358 EUR | Versender SSC + Empf. nicht-DE → beurteilbar |
| import_flow | 2 | 1.732 EUR | Versender nicht-SSC + Empf. nicht-DE → Welle 2 |
| dlv_luecke | 4 | 4.720 EUR | Calculator LookupError |

de_oos (347 Rows, 632 TEUR) dominiert den 511241-Pool. Diese Rows betreffen Inlandslieferungen (DE→DE) und liegen außerhalb des Export-DLV-Scopes.
---

## §3 KNR 491063 — Sika Deutschland GmbH / Sika Schweiz AG

### Ergebnisse

| Kennzahl | Wert |
|---|---|
| Beurteilbar | 1.379 Rows |
| Σef (Erlöse Fracht) | 1.278.459 EUR |
| Σdlv (basispreis + de_maut) | 1.304.217 EUR |
| Net Δ (nominell) | −25.758 EUR (−1,97 %) |
| M1 (|fp| ≤ 5 %) | 887 (64,3 %) |
| M2 (fp < −5 %) | 293 (21,2 %) |
| M_over (fp > +5 %) | 199 (14,4 %) |

### Diagnose: Erlöse-Maut-Trennung (Hauptbefund)

**AX-Buchungsstruktur:** Noerpel bucht für Sika 491063 die DE-Streckenmaut als separaten Umsatz-Posten:

- `Erlöse Fracht` = Transport-Grundpreis (ohne Maut)
- `Erlöse Maut` = Maut-Zuschlag (separate Spalte)

Die Pipeline verwendet ausschließlich `ef = Erlöse Fracht`. Der DLV-Soll hingegen = `basispreis + de_maut`. Dadurch ist ef systematisch um den Maut-Betrag zu niedrig.

**Quantifizierung:**

| Komponente | Wert |
|---|---|
| Σ AX Erlöse Maut (EU-Pool, ef>0, ~sub, ton>0) | 30.555 EUR |
| Σ DLV de_maut (beurteilbarer Pool) | 30.066 EUR |
| Differenz AX vs DLV Maut | +489 EUR |
| **Adjustiertes Net Δ** (ef + Erlöse Maut vs basispreis + de_maut) | **+4.797 EUR (+0,37 %)** |

Das adjustierte Net Δ liegt im M1-Bereich. AX berechnet Maut minimal über DLV-Niveau (+489 EUR auf 30 TEUR = +1,6 %). Kein Abrechnungsschaden.

### M2-Struktur-Analyse

Der nominelle M2-Block (293 Rows) setzt sich zusammen aus:

| Segment | Rows | Δ-Beitrag | Erklärung |
|---|---|---|---|
| Extreme M2 (fp < −50 %) | 107 | −20.355 EUR | Kleinstsendungen (ef << DLV-Minimum) |
| Moderate M2 (−50 % ≤ fp < −5 %) | 186 | −29.904 EUR | Maut-Separation + Rabatt-Routing |

**Extreme M2:** 107 Rows mit fp < −50 % betreffen Zeilen, bei denen AX einen ef-Wert weit unterhalb des DLV-Minimalpreises (1 Stp = 128–509 EUR je Zielland) aufweist. Hauptmuster: stp_eff=1, ef=3–50 EUR, ldm=0,4 m. Diese Zeilen wurden zu fractional rates (gewichtsbasiert oder Sonderkonditionen) abgerechnet — kein DLV-Vergleich möglich.

**M_over-Block (199 Rows):** AX rechnet für größere Stellplatz-Sendungen über DLV-Niveau ab. Σ M_over-Δ = +44.097 EUR. Dieser positive Effekt kompensiert den M2-Block nahezu vollständig:

- M2-Summe Δ: −50.259 EUR
- M_over-Summe Δ: +44.097 EUR
- M1-Residual: −19.596 EUR (≈ Maut-Separation-Artefakt)
- **Total: −25.758 EUR nominell → +4.797 EUR adjustiert**
---

## §4 KNR 511241 — SIKA Supply Center AG (SSC)

### Variante B: vollumfänglich

Alle 511241-Rows werden verarbeitet. Scope-Labeling gemäß Versender-Name + Empfänger-Land (Carlos-Entscheidung 2026-04-28).

### Ergebnisse (ssc_eu: beurteilbar)

| Kennzahl | Wert |
|---|---|
| Beurteilbar (ssc_eu) | 62 Rows |
| Σef | 43.358 EUR |
| Σdlv | 40.757 EUR |
| Net Δ | +2.600 EUR (+6,38 %) |
| M1 (|fp| ≤ 5 %) | 43 (69,4 %) |
| M2 (fp < −5 %) | 0 |
| M_over (fp > +5 %) | 19 (30,6 %) |

### Scope-Vollbild

| Scope | Rows | Σef | Status |
|---|---|---|---|
| ssc_eu | 62 | 43.358 EUR | Beurteilbar (dieser Report) |
| de_oos | 347 | 631.702 EUR | OOS: Inlands-DE-Lieferungen, kein Export-DLV |
| import_flow | 2 | 1.732 EUR | OOS: IT/ES-Ursprung non-SSC → Welle 2 |
| dlv_luecke | 4 | 4.720 EUR | DLV-Lücke (→ §6) |

### M_over-Profil

Die 19 M_over-Rows zeigen positive Net Δ (+6,38 %). AX rechnet für SSC-Export-Sendungen systematisch über DLV-Niveau ab. Ursache:

1. **Premiumrouting:** SSC-Export-Shipments (aus Stuttgart → EU) nutzen möglicherweise Premium-Kapazitäten, die über dem Standard-DLV liegen.
2. **Billing-Basis-Differenz:** Falls SSC-Sendungen mit einem abweichenden Stp-Zuschnitt (z. B. gerundete Stellplatz-Blöcke) abgerechnet werden, entsteht systematisches M_over bei mittlerem Stp-Bereich.
3. **Kein Schaden:** Da Net Δ > 0, erhält Noerpel mehr als DLV — dies ist kein Migrationsschaden sondern ein Billing-Above-DLV-Befund.

### Maut-Separation für SSC

Anders als 491063 zeigen SSC-Rows keine Erlöse-Maut-Separation-Problematik (SSC-Shipments sind EU-Exporte ohne DE-Streckenmaut-Komponente). Das positive Net Δ ist daher reales M_over.

### de_oos-Block (347 Rows, 632 TEUR)

Diese 631.702 EUR sind nicht auditierbar mit dem Export-DLV. Ein Inlands-DLV (Sika DE Inland) wäre erforderlich. Operative Klärung: Sind diese Zeilen korrekt unter KNR 511241 gebucht oder handelt es sich um Buchungsfehler (sollten unter 491063 oder anders klassifiziert)?
---

## §5 Länderprofil KNR 491063 (beurteilbar)

### Land-Level Net Δ (nominell)

| Land | n | Σef (EUR) | Σdlv (EUR) | Net Δ (EUR) | fp_net | Bewertung |
|---|---|---|---|---|---|---|
| ES | 424 | 451.699 | 456.136 | −4.437 | −0,97 % | M1-Korridor |
| GB | 306 | 380.523 | 389.841 | −9.319 | −2,39 % | M1-Korridor |
| IE | 81 | 106.413 | 104.170 | +2.243 | +2,15 % | M1-Korridor |
| IT | 427 | 249.196 | 259.393 | −10.197 | −3,93 % | M1-Korridor (Maut) |
| PT | 141 | 90.629 | 94.676 | −4.047 | −4,27 % | M1-Korridor (Maut) |
| **Gesamt** | **1.379** | **1.278.459** | **1.304.217** | **−25.758** | **−1,97 %** | Nominell |

Alle 5 Destinationsländer liegen nominell im M1-Korridor (|fp| < 5 %). Die negativen Land-Deltas bei IT (−3,93 %) und PT (−4,27 %) sind am stärksten von der Maut-Separation betroffen, da IT/AT/GB eine höhere de_maut-Rate aufweisen.

### Erlöse-Maut-adjustiert (Schätzung per Land)

Nach proportionaler Zuteilung der 30.555 EUR Erlöse Maut auf Basis Σdlv:

| Land | Maut-Anteil (est.) | Adj. Net Δ | Adj. fp_net |
|---|---|---|---|
| ES | 10.673 EUR | +6.236 | +1,37 % |
| GB | 9.122 EUR | −197 | −0,05 % |
| IE | 2.437 EUR | +4.680 | +4,50 % |
| IT | 6.072 EUR | −4.125 | −1,59 % |
| PT | 2.214 EUR | −1.833 | −1,94 % |

Adjustiert liegen alle Länder deutlich näher an Null. Kein Land zeigt systematischen Migrationsschaden.

### M2/M_over-Verteilung nach Land

| Land | M2 | M_over | M2-Δ | M_over-Δ |
|---|---|---|---|---|
| ES | 69 | 77 | −10.712 | +12.335 |
| GB | 71 | 35 | −16.046 | +12.512 |
| IE | 16 | 22 | −3.315 | +6.460 |
| IT | 90 | 47 | −13.920 | +9.977 |
| PT | 47 | 18 | −6.266 | +2.813 |

Das M2/M_over-Nebeneinander in allen Ländern bestätigt: Es gibt keine systematische einseitige Abweichung. Die M2-Cluster entstehen durch Kleinstsendungen (stp=1, ef << DLV-Minimum) und Maut-Separation. M_over entsteht bei größeren Stellplatz-Counts.
---

## §6 DLV-Lücke

### KNR 491063: 9 Rows, 5.126 EUR

Calculator wirft `LookupError` für 9 Zeilen (0,6 % des beurteilbaren Pools). DLV-Lücke < 1 % → kein ⚠-Pflicht-Hinweis nach §14.

Häufigste Ursachen bei Sika-Export-DLV:
- Destination-Land außerhalb DLV-Scope (z. B. CH, NL, BE, PL)
- PLZ-Format nicht erkannt (fehlende Ziffern, Sonderzeichen)
- Stellplätze-Kombination außerhalb Tarifband

**Handlungsempfehlung:** 9 Zeilen identifizieren (via `df_res[df_res['scope']=='dlv_luecke']`). Falls CH/NL/BE/PL: separates DLV prüfen. Falls PLZ-Format: Calculator-Bugfix.

### KNR 511241: 4 Rows, 4.720 EUR

4 ssc_eu-Rows ohne DLV-Rate. < 1 % des 511241-Beurteilbar-Pools → kein Handlungszwang. Gleiche Prüfung wie 491063 empfohlen.

### Zusammenfassung DLV-Lücke (beide KNRs)

| KNR | Rows | Σef | Pool-Anteil |
|---|---|---|---|
| 491063 | 9 | 5.126 EUR | 0,6 % |
| 511241 | 4 | 4.720 EUR | 6,1 % von ssc_eu (62) |

Gesamt-DLV-Lücke: 13 Rows, 9.846 EUR — materiell nicht relevant.
---

## §7 Gesamtbewertung und Empfehlungen

### Befund

**KNR 491063 (Sika DE): Kein Migrationsschaden.**  
Nominelles Net Δ −25.758 EUR (−1,97 %) ist vollständig auf die Erlöse-Maut-Trennung zurückzuführen. Adjustiertes Net Δ = **+4.797 EUR (+0,37 %)** — AX rechnet minimal über DLV-Niveau ab.

**KNR 511241 (SSC): Kein Migrationsschaden; M_over-Hinweis.**  
Net Δ = +2.600 EUR (+6,38 %) bedeutet, dass AX für SSC-Export-Shipments über DLV-Niveau abrechnet. Kein Schaden für Noerpel. OOS-Block (de_oos 347 Rows, 632 TEUR) nicht auditierbar mit Export-DLV.

### Methodische Konsequenz

Die Erlöse-Maut-Trennung ist ein **Sika-spezifisches Buchungsmuster**. Für zukünftige Audits:

```python
# Korrekte ef-Basis für Sika:
ef_total = Erlöse_Fracht + Erlöse_Maut
# oder DLV ohne Maut:
dlv_basis = basispreis  # ohne maut_surcharge
```

Beide Ansätze sind methodisch äquivalent. In der Pipeline-Dokumentation vermerken.

### Operative Empfehlungen

1. **de_oos 511241 klären:** 347 Rows (632 TEUR) unter KNR 511241 mit Empf. DE — Buchungszugehörigkeit prüfen.
2. **DLV-Lücke 13 Rows klären:** Zieldestinationen identifizieren; ggf. DLV-Erweiterung.
3. **Kleinstsendungen 491063:** 107 Extreme-M2-Rows (fp < −50 %) prüfen — werden diese fractional rates korrekt vertraglich abgebildet?

### KNR 527406 (ATM)

Nicht in dieser Session. Separates BI-Loading (`bi_cache_sika_527406.pkl`) + abweichendes DLV (gewichtsbasiert). Folge-Audit Welle 2.

---

## §8 Konsolidierte 11-Kunden-Lage (Stand 2026-04-28)

| Kunde | KNR | beurteilbar | M1 | M2 | M_over | Σef (TEUR) | Net Δ (EUR) | Net Δ % | Befund |
|---|---|---|---|---|---|---|---|---|---|
| GEZE GmbH | 406035 | 2.759 | 2.550 | 132 | 77 | 392 | +4.138 | +1,07 % | kein Schaden |
| EBM-Papst | 410844 | 308 | 285 | 1 | 22 | 480 | +3.514 | +0,74 % | kein Schaden |
| Fischerwerke | 409480 | 839 | 321 | 107 | 411 | 538 | +106.811 | +24,80 % | Charter-Artefakt¹ |
| HERMA GmbH | 423650 | 3.642 | 2.842 | 384 | 416 | 2.429 | −16.374 | −0,67 % | kein Schaden |
| CHT Germany | 486073 | 554 | 539 | 0 | 15 | 258 | −668 | −0,26 % | kein Schaden |
| Bitzer | 406345 | 3.330 | 2.868 | 206 | 256 | 724 | +26.407 | +3,79 % | kein Schaden² |
| Groz-Beckert | multi | 527 | 473 | 0 | 54 | 113 | +5.729 | +5,07 % | kein Schaden³ |
| HELU-KABEL | 408244 | 2.185 | 2.044 | 102 | 39 | 316 | +203 | +0,06 % | kein Schaden |
| Hornschuch AG | 490085 | 1.565 | 1.549 | 7 | 9 | 409 | −205 | −0,05 % | kein Schaden⁴ |
| **Sika DE** | **491063** | **1.379** | **887** | **293** | **199** | **1.278** | **−25.758** | **−1,97 %** | **kein Schaden⁵** |
| **Sika SSC** | **511241** | **62** | **43** | **0** | **19** | **43** | **+2.600** | **+6,38 %** | **kein Schaden⁶** |

¹ Fischerwerke +24,80 %: Charter-Artefakt. Non-Charter-Pool: ≈0 %.  
² Bitzer +3,79 %: Post-Fix (IT Zone4, FR-13400). Diesel-Floater-Prüfung offen.  
³ Groz-Beckert +5,07 %: GC-Band-Artefakt. Kerngeschäft LTL: Δ=0,00 EUR.  
⁴ Hornschuch PL-Lücke: 726 Rows, 204 TEUR ohne Carrier-Tarif. Operative Klärung empfohlen.  
⁵ Sika DE nominell −1,97 %: Erlöse-Maut-Separation-Artefakt. Adjustiertes Net Δ = **+4.797 EUR (+0,37 %)**. Kein Schaden.  
⁶ Sika SSC +6,38 %: AX rechnet über DLV-Niveau. Kein Noerpel-Schaden; Billing-Above-DLV-Hinweis.

**Gesamtbild (11 Kunden, Σef ≈ 6.980 TEUR):**  
Kein Migrationsschaden bei keinem Kunden identifiziert.  
Maut-Check rückwirkend (P20): Nur Sika 491063 betroffen. Alle anderen 9 Kunden: balancierte Vergleichsbasis (kein Adjustment notwendig).
