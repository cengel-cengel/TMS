# B2M AT-Rechnungen — Befund ERSATZKARTE 2

## Entscheidung (Carlos, 2026-05-22)

ERSATZKARTE 2 ist in ALLEN B2M-AT-Rechnungen ein **echter Einzelposten**,
keine Kostenstellen-Überschrift. Die extrahierten Beträge sind korrekt.

Die Δ-Werte in B2M_3 und B2M_4 AT sind **echte Abrechnungsunterschiede**,
keine Extraktionsfehler.

---

## Befund pro RN

| PDF   | RN           | Ist (EUR) | Soll (EUR) | Δ (EUR)  | Befund            |
|-------|--------------|----------:|----------:|---------:|-------------------|
| B2M_1 | 3603006105   | 2155.50   | 2155.50   |    0.00  | ✓ korrekt         |
| B2M_2 | 3603014114   | 1734.83   | 1734.83   |    0.00  | ✓ korrekt         |
| B2M_3 | 3603022414   | 2163.17   | 1459.74   | +703.43  | ✗ echte Differenz |
| B2M_4 | 3603030499   | 2699.91   | 1880.30   | +819.61  | ✗ echte Differenz |

---

## Struktur AT-Format

Das AT-Format (Österreich) verwendet Kostenstellen-Blöcke mit:
- `KARTEN: <Kartennummer>` / `LENKER: <Name>` als Block-Header
- `KARTEN TOTAL` als Abschlusssumme pro Karte (wird geskippt, nicht als Position extrahiert)
- ERSATZKARTE 2 und RV LE 6002 sind reguläre Fahrzeug-/Kartenpositionen mit EETS-Austria-Beträgen

In B2M_1/2: ERSATZKARTE 2 erscheint als regulärer Posten, Summe stimmt mit Manifest überein.

In B2M_3/4: ERSATZKARTE 2 erscheint ebenfalls als regulärer Posten.
Der Manifest-Soll-Wert weicht ab — dies ist eine echte Abrechnungsdifferenz
zwischen extrahiertem Betrag und dem auf dem Deckblatt ausgewiesenen Betrag.

---

## Recovery-Mechanismus (3rd-pass)

Für null-KZ-Positionen (SUMME KARTE/KFZ nicht sichtbar) wird `recover_split_kz()`
aufgerufen. Für AT-Positionen (ERSATZKARTE 2, RV LE 6002) wird der EETS-Betrag
aus den Einzelzeilen summiert.

In B2M_3/4 führt diese Recovery zu Werten, die vom Manifest abweichen.
Dies ist die Extraktion der tatsächlich aufgeführten Transaktionen —
die Abweichung zum Manifest ist der dokumentierte Befund.

---

## Konsequenz für Excel-Output

Die Δ-Spalte in den Excel-Dateien zeigt für AT B2M_3/4:
- `B2M_3 AT 3603022414: Δ = +70343 Cent (+703.43 EUR)` — echter Befund
- `B2M_4 AT 3603030499: Δ = +81961 Cent (+819.61 EUR)` — echter Befund

Diese Werte sind **korrekt ausgewiesen** und **nicht zu korrigieren**.
