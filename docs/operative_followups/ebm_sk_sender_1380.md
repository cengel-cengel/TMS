# OBSOLET — EBM SK Sender-PLZ 1380

**Stand:** 2026-04-26 | **Status:** OBSOLET — Calculator-Bug, kein operatives Thema

---

## Begründung der Obsoleszenz

Dieses Memo wurde ursprünglich erstellt unter der Annahme, dass AX für Sendungen
ab Sender-PLZ 1380 nach SK-905 einen höheren Satz (1.100 EUR) fakturiert als der
bekannte Mulfingen-DLV (960 EUR) vorsieht.

**Nachträgliche Analyse (2026-04-26)** hat ergeben:

Die 2026-DLV-Datei enthält **zwei Einträge** für SK-905 01 im Cap-Band (stp31-33):
- Eintrag 1: 960 EUR (74673-Mulfingen-Standardsatz)
- Eintrag 2: 1.100 EUR (Override für Sender-PLZ 1380)

**AX fakturiert korrekt** — der Override-Eintrag (1.100 EUR) ist in der DLV-Datei
dokumentiert und wird von AX für Sender-1380-Sendungen korrekt angewendet.

**Der Calculator-Bug** ist `EBMCalculator._lookup()` first-match-wins: die Methode
gibt immer den ersten Treffer (960 EUR) zurück, ohne den Sender-Kontext zu prüfen.
Dies erzeugt eine scheinbare Abweichung von +2.021 EUR im Audit — in Wirklichkeit
ein Audit-Artefakt.

## Kein operativer Handlungsbedarf

- Keine Anfrage an Noerpel erforderlich
- Keine Anfrage an EBM erforderlich
- Kein Rückforderungsanspruch gegenüber Noerpel
- Calculator-Bug ist im Backlog erfasst: `docs/backlog/calculator_known_issues.md`
- Audit-Report korrigiert: `docs/v1_9_4_ebm_cluster_report.md` Anhang F

## Historische Daten (zur Dokumentation)

| Merkmal | Wert |
|---------|------|
| Sender-PLZ in AX | 1380 |
| Empfänger-PLZ | SK 905 01 |
| Anzahl Sendungen | 12 |
| Zeitraum | 2026-02-10 bis 2026-03-24 |
| AX-fakturierter Preis (stp33) | 1.100,00 EUR/Sendung (korrekt) |
| DLV Override-Eintrag | 1.100,00 EUR/Sendung (bestätigt) |
| Calculator-Soll (fehlerhaft) | 960,00 EUR/Sendung (Bug: first-match) |
| Scheinbare Differenz (Artefakt) | +2.021,00 EUR |
