# Bitzer Calculator — Coverage-Diagnose v1

Stand: 2026-04-27  
DLV-Stand: IT=Upload 2026, AT/FR/ES/CH/PT/BE/NL/LU=2025

---

## Ergebnis

| Metrik | Wert |
|---|---|
| Gesamtzeilen (POST, Erlöse Fracht > 0) | 3 406 |
| Beurteilbar | 3 330 (97.8%) |
| Nicht beurteilbar | 76 (2.2%) |

---

## Nicht-beurteilbare Zeilen (76)

### 1. DE Inbound — 67 Zeilen, 33 969.72 EUR

**Ursache:** `Empfänger Land = DE` bezeichnet EINGEHENDE Sendungen an das Bitzer-Werk
Rottenburg (PLZ 72108, 71126, 71065, 75382) oder Schkeuditz (04435). Die Versender
kommen aus IT (57), FR (4), CH (2), NL (1), BE (1), PT (1), DE (1), PL (1), GB (1).

**Klassifikation:** Diese Zeilen sind **Rücktransporte / Importfracht** zur Bitzer-Anlage,
nicht Teil des Exportvertrags. Der BitzCalculator implementiert nur Ausfuhrrouten
(Bitzer → Ausland); für Einfuhrrouten sind separate Importtarife (oder ERKA) nötig.

**Scope-Entscheidung:** Nicht im v1-Scope. Separate Behandlung wenn Importtarife
verfügbar. Impact: ~500 EUR/Sendung (plausibel für schwere Maschinenteile aus IT).

### 2. FR PLZ 92000 (Nanterre, Hauts-de-Seine) — 7 Zeilen, 445.20 EUR

**Ursache:** PLZ-Prefix 92 fehlt in der FR Zoneneinteilung.  
**Status:** ERKA-Anfrage vorbereitet — `docs/operative_followups/bitzer_fr_92000_zone.md`.  
**Erwartete Zone:** Zone 4 (geografisch konsistent mit 91 und 95).

### 3. FR PLZ 77380 Combs La Ville >15 000 kg — 1 Zeile, 911.60 EUR

**Ursache:** Sonderziel-DLV für FR-77380 hat Maximalband 15 000 kg. Diese Sendung
hat billing_kg = 17 200 kg (Tonnage 17 172.9 kg).  
**BI-Wert:** 911.60 EUR. Inferred zone4-rate bei 20 000er-Band: 5.2 EUR/100kg →
17 200 × 5.2 / 100 = 894.40 EUR (Δ 17.20 EUR, wahrscheinlich ERKA-Zuschlag).  
**Status:** ERKA/Spotrate — kein DLV-Fix ohne aktualisiertes Sonderziel-DLV.

### 4. IT PLZ 09122 (Cagliari, Sardinien) — 1 Zeile, 95.00 EUR

**Ursache:** PLZ-Prefix 09 (Cagliari/Sardinien) fehlt in der IT Zoneneinteilung.
IT Upload-DLV deckt 00–06 als Zone 4 ab; 07–09 (Sardinien/Sassari) fehlen.  
**Status:** Sardinische PLZ haben oft Inselzuschläge und separate Raten — ERKA-Anfrage
sinnvoll. Impact: 1 Zeile, 95 EUR.

---

## Länderstatus

| Land | Zeilen | Beurteilbar | Fehler | Ursache |
|---|---|---|---|---|
| IT | 1 715 | 1 714 | 1 | PLZ 09 (Sardinien) fehlt |
| FR | 527 | 519 | 8 | 7 × PLZ 92000, 1 × 77380 >15t |
| ES | 325 | 325 | 0 | — |
| AT | 290 | 290 | 0 | — |
| CH | 189 | 189 | 0 | — |
| NL | 171 | 171 | 0 | — |
| DE | 67 | 0 | 67 | Inbound (scope-out) |
| BE | 59 | 59 | 0 | — |
| PT | 40 | 40 | 0 | — |
| LU | 23 | 23 | 0 | — |

---

## Nächste Schritte

1. **ERKA FR 92000:** Noerpel-Anfrage stellen → PLZ 92, 93, 94 Zonenzuordnung.
2. **ERKA FR 77380 >15t:** Prüfen ob Sonderziel-DLV erweitert werden kann.
3. **IT 09xxx:** ERKA-Anfrage Sardinien-Routen oder Inselzuschlag-Dokumentation.
4. **DE Inbound:** Entscheiden ob und welche Importtarife zu implementieren sind.
5. **Ziel v2:** ≥ 99.5% Beurteilbarkeit durch Schließen der Lücken 1–3.
